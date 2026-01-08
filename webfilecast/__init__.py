import os
import pickle
import re
from hashlib import md5
from time import sleep
from typing import Optional

from filetype import is_video
from flask import Flask, send_from_directory, send_file, url_for
from flask_socketio import SocketIO, emit
from redis import Redis
from terminalcast import FileMetadata, create_tmp_video_file, AudioMetadata, TerminalCast, NoChromecastAvailable
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


def natural_sort_key(s):
    """Key for natural sorting."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


class WebfileCast:
    def __init__(self):
        self.orig_file_path: str = ''
        self.file_path: str = ''
        self.audio_stream: Optional[AudioMetadata] = None
        self.audio_ready = False
        self.movie_files = {}
        self.tcast: Optional[TerminalCast] = None

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


@app.route('/')
def main():
    return send_from_directory(directory='static', path='main.html')


@app.route('/video')
def video():
    if not wfc.file_path or not os.path.exists(wfc.file_path):
        return "No video selected or file not found", 404
    return send_file(wfc.file_path, conditional=True)


def _emit_status(msg: str, msg_type: str, ready: bool = None):
    payload = {'msg': msg, 'type': msg_type}
    if ready is not None:
        payload['ready'] = ready
    try:
        emit('player_status_update', payload)
    except RuntimeError as e:
        LOG.warning(f"Could not emit status: {e}")


@socketio.on('is_ready')
def is_ready():
    if wfc.ready:
        _emit_status('Ready to play', 'success', ready=True)
    else:
        _emit_status('Player not ready', 'warning', ready=False)
    return 'OK, 200'


@socketio.on('get_files')
def get_files(force: bool = False):
    LOG.info('WS: get_files')
    movie_files = wfc.update_redis_file_cache(force=force)

    file_list = [
        (movie.filepath, movie.ffoutput['format'].get('tags', {}).get('title', movie.filepath.split('/')[-1]))
        for movie in movie_files.values()
    ]

    sorted_files = sorted(file_list, key=lambda item: natural_sort_key(item[1]))

    emit('movie_files', sorted_files)
    return 'OK, 200'


@socketio.on('select_file')
def select_file(filepath: str):
    LOG.info('WS: select_file')
    wfc.orig_file_path = wfc.file_path = filepath
    wfc.audio_ready = False
    _emit_status('File selected. Please select audio.', 'info', ready=False)
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
            'warning', ready=False)
    else:
        wfc.audio_ready = True
        is_ready()


@socketio.on('convert_for_audio_stream')
def convert_for_audio_stream():
    LOG.info('WS: convert audio stream')

    def progress_callback(progress: float):
        try:
            emit('conversion_progress', {'progress': round(progress, 2)})
        except RuntimeError:
            pass

    _emit_status('Audio conversion started...', 'info', ready=False)
    new_file_path = create_tmp_video_file(
        filepath=wfc.file_path,
        audio_index=wfc.audio_stream.index[-1:],
        duration=float(wfc.file_metadata.ffoutput['format']['duration']),
        progress_callback=progress_callback,
    )

    if os.path.exists(new_file_path):
        wfc.file_path = new_file_path
        wfc.audio_ready = True
        _emit_status('Audio conversion finished', 'success', ready=True)
        sleep(2)
        is_ready()
    else:
        LOG.error(f"Conversion failed. File not found: {new_file_path}")
        _emit_status('Conversion failed. Please check logs.', 'error', ready=False)


@socketio.on('play_on_chromecast')
def play_on_chromecast():
    if not wfc.ready:
        is_ready()
        return

    _emit_status('Connecting to Chromecast ...', 'info', ready=False)
    video_url = url_for('video', _external=True)
    wfc.tcast = TerminalCast(filepath=wfc.file_path, video_url=video_url, select_ip=False)
    LOG.info(f'Video URL: {video_url}')
    
    try:
        LOG.info(wfc.tcast.cast.status)
        _emit_status('Connected to Chromecast. Starting playback...', 'success', ready=False)
        wfc.tcast.play_video()
        LOG.info(wfc.tcast.cast.media_controller.status)
        _emit_status('Playing ...', 'success', ready=False)
        emit('playback_started')
    except NoChromecastAvailable as exc:
        LOG.warning(f'No Chromecast found: {exc}')
        _emit_status('No Chromecast found.', 'error', ready=True)


@socketio.on('stop_playback')
def stop_playback():
    if wfc.tcast:
        wfc.tcast.stop_cast()
        wfc.tcast = None
        _emit_status('Playback stopped.', 'info', ready=True)
        emit('playback_stopped')
    else:
        _emit_status('Nothing to stop.', 'warning', ready=True)


if __name__ == '__main__':
    socketio.run(app)
