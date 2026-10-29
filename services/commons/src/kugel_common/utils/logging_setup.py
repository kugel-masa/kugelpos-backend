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

import os
from logging import config, getLogger
from logging.handlers import BaseRotatingHandler

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
            # ConcurrentRotatingFileHandler derives from BaseRotatingHandler, not
            # from RotatingFileHandler, so testing for the latter would skip it
            # and silently drop every override. The maxBytes probe keeps out
            # TimedRotatingFileHandler, which has no size to override.
            if not isinstance(handler, BaseRotatingHandler) or not hasattr(handler, "maxBytes"):
                continue
            handler.namer = rotated_log_name
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
