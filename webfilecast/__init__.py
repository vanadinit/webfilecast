import sys
from functools import cached_property
from os import getenv, listdir
from subprocess import Popen, TimeoutExpired
from typing import Optional

from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit
from terminalcast import FileMetadata, create_tmp_video_file, AudioMetadata

from webfilecast.logger import init_logger

MOVIE_DIRECTORY = getenv('MOVIE_DIRECTORY')

app = Flask(__name__)
socketio = SocketIO(
    app=app,
    message_queue='redis://',
    logger=False,
    engineio_logger=False,
    cors_allowed_origin=[getenv('BASE_URL')],
)

LOG = init_logger('webfilecast')


class WfcInfo:
    def __int__(self):
        self.orig_file_path: str = ''
        self.file_path: str = ''
        self.audio_stream: Optional[AudioMetadata] = None
        self.audio_ready = False
        self.playing_process: Optional[Popen] = None

    @cached_property
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


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


@socketio.on('get_files')
def get_files():
    LOG.info('WS: get_files')
    emit('movie_files', listdir(MOVIE_DIRECTORY))
    return 'OK, 200'


@socketio.on('select_file')
def select_file(filename: str):
    LOG.info('WS: select_file')
    wfc_info.orig_file_path = wfc_info.file_path = f'{MOVIE_DIRECTORY}/{filename}'
    emit('show_file_details', wfc_info.file_metadata.details())
    if len(wfc_info.file_metadata.audio_streams) > 1:
        emit('lang_options', [
            (stream_id, stream.title)
            for stream_id, stream
            in enumerate(wfc_info.file_metadata.audio_streams)
        ])

    return 'OK, 200'


@socketio.on('select_lang')
def select_lang(lang_id: int):
    LOG.info('WS: select_lang')
    wfc_info.audio_stream = wfc_info.file_metadata.audio_streams[lang_id]
    if lang_id != 0:
        wfc_info.audio_ready = False
        emit('audio_conversion_required')
    else:
        wfc_info.audio_ready = True
        emit('audio_conversion_needless')


@socketio.on('convert_for_audio_stream')
def convert_for_audio_stream():
    emit('audio_conversion_started')
    wfc_info.file_path = create_tmp_video_file(
        filepath=wfc_info.file_path,
        audio_index=wfc_info.audio_stream.index[-1:],
    )
    del wfc_info.file_metadata  # Clear cached property
    wfc_info.audio_ready = True
    emit('audio_conversion_finished')


@socketio.on('play')
def play():
    if wfc_info.ready:
        wfc_info.playing_process = Popen(
            f'{sys.exec_prefix}/bin/terminalcast {wfc_info.file_path}',
            stdout=sys.stdout,
            stderr=sys.stderr,
            shell=True,
        )
        emit('playing')


@socketio.on('stop')
def stop():
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

