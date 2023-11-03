import logging
import sys
from logging import StreamHandler, getLogger, INFO, DEBUG

from flask_socketio import emit

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class LoggerWriter:
    # From https://stackoverflow.com/questions/19425736/how-to-redirect-stdout-and-stderr-to-logger-in-python
    def __init__(self, logfct):
        self.logfct = logfct
        self.buf = []

    def write(self, msg):
        if msg.endswith('\n'):
            self.buf.append(msg.removesuffix('\n'))
            self.logfct(''.join(self.buf))
            self.buf = []
        else:
            self.buf.append(msg)

    def flush(self):
        pass


class WebSocketHandler(StreamHandler):
    def __init__(self, cmd_id: str = ''):
        StreamHandler.__init__(self)
        self.cmd_id = cmd_id

    def emit(self, record):
        try:
            msg = self.format(record)
            # use https://pypi.org/project/ansi2html/ for nice converted and colored messages
            emit('logmessage', msg)
            self.flush()
        except Exception:
            self.handleError(record)


def init_logger(name: str) -> logging.Logger:
    log = getLogger(name)
    log.setLevel(DEBUG)

    formatter = logging.Formatter(LOG_FORMAT)

    ws_handler = WebSocketHandler()
    ws_handler.setLevel(INFO)
    ws_handler.setFormatter(formatter)

    journal_handler = StreamHandler(sys.__stdout__)
    journal_handler.setLevel(INFO)
    journal_handler.setFormatter(formatter)

    log.addHandler(ws_handler)
    log.addHandler(journal_handler)

    return log
