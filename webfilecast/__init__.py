import os
import pickle
from hashlib import md5
from time import sleep
from typing import Optional

from filetype import is_video
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit
from redis import Redis
from rq import Queue
from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation
from rq.job import Job
from terminalcast import FileMetadata, create_tmp_video_file, AudioMetadata, TerminalCast, run_http_server

from webfilecast.logger import init_logger

MOVIE_DIRECTORY = os.getenv('MOVIE_DIRECTORY')

app = Flask(__name__)
app.config['APPLICATION_ROOT'] = os.getenv('APPLICATION_ROOT', '/')
socketio = SocketIO(
    app=app,
    message_queue='redis://',
    logger=False,
    engineio_logger=False,
    cors_allowed_origin=[os.getenv('CORS_ORIGIN')],
)

redis = Redis()

LOG = init_logger('webfilecast')


class WebfileCast:
    def __init__(self):
        self.orig_file_path: str = ''
        self.file_path: str = ''
        self.audio_stream: Optional[AudioMetadata] = None
        self.audio_ready = False
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


def update_redis_file_cache() -> dict:
    movie_files = {}
    for root, dirs, files in os.walk(MOVIE_DIRECTORY):
        for file in files:
            path = os.path.join(root, file)
            try:
                if not is_video(path):
                    continue
            except PermissionError:
                continue
            path_store_id = 'fm_' + md5(path.encode('utf-8')).hexdigest()
            if r_data := redis.get(path_store_id):
                movie_files[path] = pickle.loads(r_data)
                continue

            metadata = FileMetadata(path)
            _ = metadata.ffoutput  # Just to have it called
            redis.set(path_store_id, pickle.dumps(metadata))
            movie_files[path] = metadata
    return movie_files


wfc = WebfileCast()
update_redis_file_cache()
queue = Queue(connection=redis)


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


@socketio.on('is_ready')
def is_ready():
    emit('ready', wfc.ready)
    return 'OK, 200'


@socketio.on('get_files')
def get_files():
    LOG.info('WS: get_files')
    movie_files = update_redis_file_cache()
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


@socketio.on('play')
def play():
    if wfc.ready:
        emit('start_playing')
        wfc.tcast = TerminalCast(filepath=wfc.file_path, select_ip=False)
        LOG.info(wfc.tcast.cast.status)
        wfc.job = queue.enqueue(run_http_server, kwargs={
            'filepath': wfc.file_path,
            'ip': wfc.tcast.ip,
            'port': wfc.tcast.port,
        })
        LOG.info('Wait some time for server to start...')
        sleep(5)
        LOG.info(wfc.tcast.get_video_url())
        wfc.tcast.play_video()
        LOG.info(wfc.tcast.cast.media_controller.status)
        emit('playing')
    else:
        is_ready()


@socketio.on('stop')
def stop():
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
