import os
import pickle
import sys
from hashlib import md5
from subprocess import Popen, TimeoutExpired
from time import sleep
from typing import Optional

from filetype import is_video
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit
from redis import Redis
from terminalcast import FileMetadata, create_tmp_video_file, AudioMetadata
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


class WfcInfo:
    def __init__(self):
        self.orig_file_path: str = ''
        self.file_path: str = ''
        self.audio_stream: Optional[AudioMetadata] = None
        self.audio_ready = False
        self.playing_process: Optional[Popen] = None

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

        if self.playing_process:
            print('Already playing')
            return False

        return True


wfc_info = WfcInfo()


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


update_redis_file_cache()


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


@socketio.on('is_ready')
def is_ready():
    emit('ready', wfc_info.ready)
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
    wfc_info.orig_file_path = wfc_info.file_path = filepath
    emit('show_file_details', wfc_info.file_metadata.details())
    if len(wfc_info.file_metadata.audio_streams) > 1:
        emit('lang_options', [
            (stream_id, stream.title)
            for stream_id, stream
            in enumerate(wfc_info.file_metadata.audio_streams)
        ])
    else:
        wfc_info.audio_ready = True

    return 'OK, 200'


@socketio.on('select_lang')
def select_lang(lang_id: str):
    LOG.info('WS: select_lang')
    wfc_info.audio_stream = wfc_info.file_metadata.audio_streams[int(lang_id)]
    if int(lang_id) != 0:
        wfc_info.audio_ready = False
        emit('audio_conversion_required')
    else:
        wfc_info.audio_ready = True
        is_ready()


@socketio.on('convert_for_audio_stream')
def convert_for_audio_stream():
    LOG.info('WS: convert audio stream')
    emit('audio_conversion_started')
    wfc_info.file_path = create_tmp_video_file(
        filepath=wfc_info.file_path,
        audio_index=wfc_info.audio_stream.index[-1:],
    )
    wfc_info.audio_ready = True
    emit('audio_conversion_finished')
    sleep(2)
    is_ready()


@socketio.on('play')
def play():
    if wfc_info.ready:
        wfc_info.playing_process = Popen(
            f'{sys.exec_prefix}/bin/terminalcast {wfc_info.file_path} --non-interactive',
            stdout=sys.stdout,
            stderr=sys.stderr,
            shell=True,
        )
        emit('playing')
    else:
        is_ready()


@socketio.on('stop')
def stop():
    emit('stopping')
    wfc_info.playing_process.terminate()
    try:
        wfc_info.playing_process.wait(10)
    except TimeoutExpired:
        wfc_info.playing_process.kill()
        wfc_info.playing_process.wait(10)
    wfc_info.playing_process = None
    emit('stopped')


if __name__ == '__main__':
    socketio.run(app)
