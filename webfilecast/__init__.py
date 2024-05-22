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
            print('No file selected')
            return False

        if not self.audio_ready:
            print('Audio not ready')
            return False

        if self.job is not None and self.job.get_status() == 'started':
            print('Already playing')
            return False

        return True

    def update_redis_file_cache(self, force: bool = False) -> dict:
        if force:
            self.movie_files = {}
        for root, dirs, files in os.walk(MOVIE_DIRECTORY):
            for file in files:
                path = os.path.join(root, file)
                if self.movie_files.get(path):
                    continue
                try:
                    if not is_video(path):
                        continue
                except (PermissionError, OSError) as exc:
                    print(f'Skip {path}: {exc}')
                    continue
                try:
                    emit('show_file_details', f'{len(self.movie_files)} files collected')
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
        return self.movie_files


wfc = WebfileCast()
queue = Queue(connection=redis)


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


@socketio.on('is_ready')
def is_ready():
    emit('ready', wfc.ready)
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
    emit('lang_options', [
        (stream_id, stream.title)
        for stream_id, stream
        in enumerate(wfc.file_metadata.audio_streams)
    ])

    return 'OK, 200'


@socketio.on('select_lang')
def select_lang(lang_id: str):
    LOG.info('WS: select_lang')
    wfc.audio_stream = wfc.file_metadata.audio_streams[int(lang_id)]
    if int(lang_id) != 0:
        wfc.audio_ready = False
        emit('audio_conversion_required')
    else:
        wfc.audio_ready = True
        is_ready()


@socketio.on('convert_for_audio_stream')
def convert_for_audio_stream():
    LOG.info('WS: convert audio stream')
    emit('audio_conversion_started')
    wfc.file_path = create_tmp_video_file(
        filepath=wfc.file_path,
        audio_index=wfc.audio_stream.index[-1:],
    )
    wfc.audio_ready = True
    emit('audio_conversion_finished')
    sleep(2)
    is_ready()


@socketio.on('start_server')
def start_server():
    if wfc.ready:
        emit('starting_server')
        wfc.tcast = TerminalCast(filepath=wfc.file_path, select_ip=request.host)
        LOG.info(wfc.tcast.cast.status)
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
    else:
        is_ready()


@socketio.on('play')
def play():
    if wfc.job is None or wfc.job.get_status() != 'started':
        start_server()
    if wfc.job.get_status() == 'started':
        wfc.tcast.play_video()
        LOG.info(wfc.tcast.cast.media_controller.status)
        emit('playing')
    else:
        LOG.error('Server has not been started successfully')


@socketio.on('stop_server')
def stop_server():
    if wfc.job is None:
        LOG.warning('Nothing to stop.')
        return
    emit('stopping')
    try:
        send_stop_job_command(connection=redis, job_id=wfc.job.get_id())
        sleep(1)
    except InvalidJobOperation as exc:
        LOG.warning(str(exc))
    LOG.info(wfc.job.get_status())
    if wfc.job.get_status() in ['finished', 'stopped', 'failed', 'cancelled']:
        emit('stopped')


if __name__ == '__main__':
    socketio.run(app)
