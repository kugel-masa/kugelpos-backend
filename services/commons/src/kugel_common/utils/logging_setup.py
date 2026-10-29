"""
Load a service's logging.conf and apply the LOG_* environment overrides.

logging.conf carries literal, already-bounded values so that any caller can
load it on its own (each service's tests/conftest.py calls fileConfig() itself).
The overrides therefore live here, in the process that wants them, not in the
file.

Environment variables:

- ``LOG_LEVEL``: level of the root and request loggers and their handlers.
- ``LOG_MAX_BYTES`` / ``LOG_BACKUP_COUNT``: rotation of app.log and request.log.
- ``LOG_AUDIT_MAX_BYTES`` / ``LOG_AUDIT_BACKUP_COUNT``: rotation of audit.log.

The audit handler's level is left alone on purpose: it is a security record, so
LOG_LEVEL=WARNING must not be able to silence it.
"""

import fcntl
import os
from logging import FileHandler, config, getLogger
from logging.handlers import RotatingFileHandler

AUDIT_LOGGER_NAME = "audit"
REQUEST_LOGGER_NAME = "requestLogger"


def rotated_log_name(default_name: str) -> str:
    """
    Name a rotated segment ``app.1.log`` instead of ``app.log.1``.

    The default name stops matching ``*.log``, so the segments would fall out of
    anything that selects log files by that pattern (collection, .gitignore).
    """
    base, _, index = default_name.rpartition(".")
    if index.isdigit() and base.endswith(".log"):
        return f"{base[:-4]}.{index}.log"
    return default_name


class MultiProcessRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that several processes can share one file through.

    uvicorn runs ``UVICORN_WORKERS`` processes, each with its own handler on the
    same app.log. With the plain handler each worker rotates on its own: one
    renames the file another is still writing, and later rotations shift that
    file past ``backupCount`` and delete it while it is being written, so lines
    (audit ones included) are lost.

    Here each record is written under a lock file shared by all processes: the
    handler reopens the file if another process rotated it, rotates if it is
    full, and writes, with no other process able to rotate in between.
    """

    def __init__(self, filename, mode="a", maxBytes=0, backupCount=0, encoding=None, delay=False, errors=None):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay, errors)
        self.namer = rotated_log_name
        self._lock_file = open(self.baseFilename + ".lock", "a")

    def _stream_is_current(self) -> bool:
        if self.stream is None:
            return False
        try:
            on_disk = os.stat(self.baseFilename)
        except FileNotFoundError:
            return False
        opened = os.fstat(self.stream.fileno())
        return (on_disk.st_dev, on_disk.st_ino) == (opened.st_dev, opened.st_ino)

    def emit(self, record) -> None:
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX)
            try:
                if not self._stream_is_current():
                    if self.stream is not None:
                        self.stream.close()
                    self.stream = self._open()
                if self.shouldRollover(record):
                    self.doRollover()
                FileHandler.emit(self, record)
            finally:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._lock_file.close()


def apply_log_env_overrides() -> None:
    """Apply the LOG_* environment variables on top of the loaded configuration."""
    level = os.environ.get("LOG_LEVEL")
    if level:
        for name in (None, REQUEST_LOGGER_NAME):
            logger = getLogger(name)
            logger.setLevel(level.upper())
            for handler in logger.handlers:
                handler.setLevel(level.upper())

    rotation = (
        (None, "LOG_MAX_BYTES", "LOG_BACKUP_COUNT"),
        (REQUEST_LOGGER_NAME, "LOG_MAX_BYTES", "LOG_BACKUP_COUNT"),
        (AUDIT_LOGGER_NAME, "LOG_AUDIT_MAX_BYTES", "LOG_AUDIT_BACKUP_COUNT"),
    )
    for name, size_var, count_var in rotation:
        size = os.environ.get(size_var)
        count = os.environ.get(count_var)
        for handler in getLogger(name).handlers:
            if not isinstance(handler, RotatingFileHandler):
                continue
            if size:
                handler.maxBytes = int(size)
            if count:
                handler.backupCount = int(count)


def configure_logging(conf_path: str) -> None:
    """
    Load ``conf_path`` and apply the environment overrides.

    ``disable_existing_loggers`` is False because uvicorn creates its loggers
    before the application is imported; the default True silenced
    ``uvicorn.error``, so startup and protocol failures were logged nowhere.
    """
    config.fileConfig(conf_path, disable_existing_loggers=False)
    apply_log_env_overrides()
