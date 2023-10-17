import logging
import sys
from functools import cached_property
from logging import StreamHandler, getLogger, INFO

from flask_socketio import SocketIO

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class WebSocketHandler(StreamHandler):
    @cached_property
    def websocket(self) -> SocketIO:
        return SocketIO(message_queue='redis://')

    def emit(self, record):
        try:
            msg = self.format(record)
            # use https://pypi.org/project/ansi2html/ for nice converted and colored messages
            self.websocket.emit('logmessage', msg, broadcast=True)
            self.flush()
        except Exception:
            self.handleError(record)


def init_logger(name: str) -> logging.Logger:
    log = getLogger(name)

    formatter = logging.Formatter(LOG_FORMAT)

    ws_handler = WebSocketHandler()
    ws_handler.setLevel(INFO)
    ws_handler.setFormatter(formatter)

    journal_handler = StreamHandler(sys.stdout)
    journal_handler.setLevel(INFO)
    journal_handler.setFormatter(formatter)

    log.addHandler(ws_handler)
    log.addHandler(journal_handler)
    return log
