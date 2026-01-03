import os
import pickle
from hashlib import md5
from time import sleep
from typing import Optional

from filetype import is_video
from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit
from redis import Redis
from rq import Queue
from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation
from rq.job import Job
from terminalcast import FileMetadata, create_tmp_video_file, AudioMetadata, TerminalCast, run_http_server
from terminalcast.tc import NoChromecastAvailable
from werkzeug.middleware.proxy_fix import ProxyFix

from webfilecast.logger import init_logger

MOVIE_DIRECTORY = os.getenv('MOVIE_DIRECTORY')

app = Flask(__name__)
app.config['APPLICATION_ROOT'] = os.getenv('APPLICATION_ROOT', '/')
socketio = SocketIO(
    app=app,
    message_queue='redis://',
    logger=False,
    engineio_logger=False,
    cors_allowed_origins=os.getenv('CORS_ORIGINS').split(';'),
)

# For having the correct client/host IP behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

redis = Redis()

LOG = init_logger('webfilecast')


class WebfileCast:
    def __init__(self):
        self.orig_file_path: str = ''
        self.file_path: str = ''
        self.audio_stream: Optional[AudioMetadata] = None
        self.audio_ready = False
        self.movie_files = {}
        self.tcast: Optional[TerminalCast] = None
        self.job: Optional[Job] = None

    @property
    def file_metadata(self) -> FileMetadata:
        return FileMetadata(self.file_path)

    @property
    def ready(self) -> bool:
        if not self.file_path:
            LOG.warning('No file selected')
            return False

        if not self.audio_ready:
            LOG.warning('Audio not ready')
            return False

        if self.job is not None and self.job.get_status() == 'started':
            LOG.warning('Already playing')
            return False

        return True

    def update_redis_file_cache(self, force: bool = False) -> dict:
        if force:
            self.movie_files = {}
        elif pckl_movie_files := redis.get('wfc_movie_files'):
            self.movie_files = pickle.loads(pckl_movie_files)

        try:
            emit('scan_started')
        except RuntimeError:
            pass

        for root, dirs, files in os.walk(MOVIE_DIRECTORY):
            for file in files:
                path = os.path.join(root, file)
                if self.movie_files.get(path):
                    continue
                try:
                    if not is_video(path):
                        continue
                except (PermissionError, OSError) as exc:
                    LOG.warning(f'Skip {path}: {exc}')
                    continue
                try:
                    emit('scan_progress', {'count': len(self.movie_files)})
                except RuntimeError:
                    pass
                path_store_id = 'fm_' + md5(path.encode('utf-8')).hexdigest()
                if r_data := redis.get(path_store_id):
                    self.movie_files[path] = pickle.loads(r_data)
                    continue

                metadata = FileMetadata(path)
                _ = metadata.ffoutput  # Just to have it called
                redis.set(path_store_id, pickle.dumps(metadata))
                self.movie_files[path] = metadata

        try:
            emit('scan_finished', {'count': len(self.movie_files)})
        except RuntimeError:
            pass

        redis.set('wfc_movie_files', pickle.dumps(self.movie_files))
        return self.movie_files


wfc = WebfileCast()
wfc.update_redis_file_cache()
queue = Queue(connection=redis)


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


def _emit_status(msg: str, msg_type: str):
    try:
        emit('player_status_update', {'msg': msg, 'type': msg_type})
    except RuntimeError as e:
        LOG.warning(f"Could not emit status: {e}")


@socketio.on('is_ready')
def is_ready():
    if wfc.ready:
        _emit_status('Ready to play', 'success')
    else:
        _emit_status('Player not ready', 'warning')
    return 'OK, 200'


@socketio.on('get_files')
def get_files(force: bool = False):
    LOG.info('WS: get_files')
    movie_files = wfc.update_redis_file_cache(force=force)
    emit('movie_files', sorted([
        (movie.filepath, movie.ffoutput['format']['tags'].get('title', movie.filepath.split('/')[-1]))
        for movie in movie_files.values()
    ]))
    return 'OK, 200'


@socketio.on('select_file')
def select_file(filepath: str):
    LOG.info('WS: select_file')
    wfc.orig_file_path = wfc.file_path = filepath
    emit('show_file_details', wfc.file_metadata.details())
    
    lang_options = []
    for stream_id, stream in enumerate(wfc.file_metadata.audio_streams):
        title = "Undefined" if stream.title == "und" else stream.title
        lang_options.append((stream_id, title))
        
    emit('lang_options', lang_options)
    return 'OK, 200'


@socketio.on('select_lang')
def select_lang(lang_id: str):
    LOG.info('WS: select_lang')
    wfc.audio_stream = wfc.file_metadata.audio_streams[int(lang_id)]
    if int(lang_id) != 0:
        wfc.audio_ready = False
        _emit_status(
            'Audio conversion required! <button onclick="window.socket.emit(\'convert_for_audio_stream\')">Convert</button>',
            'warning')
    else:
        wfc.audio_ready = True
        is_ready()


@socketio.on('convert_for_audio_stream')
def convert_for_audio_stream():
    LOG.info('WS: convert audio stream')
    _emit_status('Audio conversion started...', 'info')
    wfc.file_path = create_tmp_video_file(
        filepath=wfc.file_path,
        audio_index=int(wfc.audio_stream.index.split(':')[-1]),
    )
    wfc.audio_ready = True
    _emit_status('Audio conversion finished', 'success')
    sleep(2)
    is_ready()


@socketio.on('start_server')
def start_server():
    if wfc.ready:
        _emit_status('Starting Server ...', 'info')
        wfc.tcast = TerminalCast(filepath=wfc.file_path, select_ip=request.host.split(':')[0])
        wfc.job = queue.enqueue(
            run_http_server,
            kwargs={
                'filepath': wfc.file_path,
                'ip': wfc.tcast.ip,
                'port': wfc.tcast.port,
            },
            job_timeout='5h',
            failure_ttl='7d',
        )
        LOG.info('Wait some time for server to start...')
        sleep(5)
        LOG.info(wfc.tcast.get_video_url())
        emit('video_link', wfc.tcast.get_video_url())
        try:
            LOG.info(wfc.tcast.cast.status)
            _emit_status('Server started. Ready to play.', 'success')
        except NoChromecastAvailable as exc:
            LOG.warning(f'No Chromecast found: {exc}\n The video might be available direct via URL anyway.')
            _emit_status('No Chromecast found. Video might be available via URL.', 'warning')
    else:
        is_ready()


@socketio.on('play')
def play():
    if wfc.job is None or wfc.job.get_status() != 'started':
        LOG.error('Server is not running. Please start it first.')
        _emit_status('Server not running. Please start it first.', 'error')
        return

    wfc.tcast.play_video()
    LOG.info(wfc.tcast.cast.media_controller.status)
    _emit_status('Playing ...', 'success')


@socketio.on('stop_server')
def stop_server():
    if wfc.job is None:
        LOG.warning('Nothing to stop.')
        return
    _emit_status('Stopping ...', 'info')
    try:
        send_stop_job_command(connection=redis, job_id=wfc.job.get_id())
        sleep(1)
    except InvalidJobOperation as exc:
        LOG.warning(str(exc))
    LOG.info(wfc.job.get_status())
    if wfc.job.get_status() in ['finished', 'stopped', 'failed', 'cancelled']:
        _emit_status('Stopped', 'error')


if __name__ == '__main__':
    socketio.run(app)
