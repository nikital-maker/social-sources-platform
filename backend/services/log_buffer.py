import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock

_BUFFER_SIZE = 500
_buffer: deque = deque(maxlen=_BUFFER_SIZE)
_lock = Lock()


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
        }
        with _lock:
            _buffer.append(entry)


def install(level: int = logging.INFO):
    handler = BufferHandler(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)


def get_logs(n: int = 200) -> list[dict]:
    with _lock:
        entries = list(_buffer)
    return entries[-n:]
