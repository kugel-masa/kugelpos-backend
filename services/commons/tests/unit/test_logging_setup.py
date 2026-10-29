"""
Tests for kugel_common.utils.logging_setup and the services' logging.conf files.

Anything that loads a logging configuration runs in a child process: changing
the global logging state here would break caplog in every test that runs after.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kugel_common.utils.logging_setup import rotated_log_name

REPO_ROOT = Path(__file__).resolve().parents[4]
SERVICES_DIR = REPO_ROOT / "services"
COMMONS_SRC = SERVICES_DIR / "commons" / "src"
SERVICES = ["account", "terminal", "master-data", "cart", "report", "journal", "stock"]

needs_repo = pytest.mark.skipif(not SERVICES_DIR.is_dir(), reason="repository layout not available")

# Prints, as JSON, the loggers and file handlers the child process ended up with.
DESCRIBE = """
import json, logging
from logging.handlers import RotatingFileHandler

def handlers(name):
    out = []
    for h in logging.getLogger(name).handlers:
        item = {"class": type(h).__name__, "level": logging.getLevelName(h.level)}
        if isinstance(h, RotatingFileHandler):
            item.update(file=h.baseFilename.rsplit("/", 1)[-1], max_bytes=h.maxBytes,
                        backup_count=h.backupCount, namer=getattr(h.namer, "__name__", None))
        out.append(item)
    return out

print(json.dumps({
    name or "root": {"level": logging.getLevelName(logging.getLogger(name).level), "handlers": handlers(name)}
    for name in (None, "requestLogger", "audit")
} | {"early_disabled": logging.getLogger("uvicorn.error").disabled}))
"""


def _run(script: str, cwd: Path, env_extra: dict | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LOG_")}
    env["PYTHONPATH"] = os.pathsep.join([str(COMMONS_SRC), env.get("PYTHONPATH", "")])
    env.update(env_extra or {})
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=cwd, env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _load(conf: Path, cwd: Path, env_extra: dict | None = None, standalone: bool = False) -> dict:
    if standalone:
        load = f"import logging.config\nlogging.config.fileConfig({str(conf)!r})\n"
    else:
        load = (
            "from kugel_common.utils.logging_setup import configure_logging\n"
            f"configure_logging({str(conf)!r})\n"
        )
    script = "import logging\nlogging.getLogger('uvicorn.error')\n" + load + DESCRIBE
    return json.loads(_run(script, cwd, env_extra).strip().splitlines()[-1])


def _file_handlers(described: dict) -> list[dict]:
    return [
        h
        for name in ("root", "requestLogger", "audit")
        for h in described[name]["handlers"]
        if "file" in h
    ]


@pytest.mark.parametrize(
    "default_name, expected",
    [
        ("/app/app.log.1", "/app/app.1.log"),
        ("/app/request.log.12", "/app/request.12.log"),
        ("/app/audit.log", "/app/audit.log"),
        ("/app/app.txt.1", "/app/app.txt.1"),
    ],
)
def test_rotated_segments_keep_the_log_extension(default_name, expected):
    assert rotated_log_name(default_name) == expected


@needs_repo
@pytest.mark.parametrize("service", SERVICES)
def test_conf_is_bounded_when_loaded_on_its_own(service, tmp_path):
    """tests/conftest.py loads the conf without configure_logging, so it must be safe as written."""
    described = _load(SERVICES_DIR / service / "app" / "logging.conf", tmp_path, standalone=True)

    files = _file_handlers(described)
    assert sorted(h["file"] for h in files) == ["app.log", "audit.log", "request.log"]
    for handler in files:
        assert handler["class"] == "MultiProcessRotatingFileHandler"
        assert handler["max_bytes"] > 0 and handler["backup_count"] > 0
    assert described["root"]["level"] == "INFO"
    assert described["requestLogger"]["level"] == "INFO"


@needs_repo
@pytest.mark.parametrize("service", SERVICES)
def test_main_loads_logging_through_configure_logging(service):
    source = (SERVICES_DIR / service / "app" / "main.py").read_text()
    assert "configure_logging(logging_conf_path)" in source
    assert "fileConfig(" not in source


@needs_repo
def test_loggers_created_before_configuration_stay_enabled(tmp_path):
    """uvicorn creates its loggers before importing the app; fileConfig's default disabled them."""
    conf = SERVICES_DIR / "cart" / "app" / "logging.conf"

    assert _load(conf, tmp_path)["early_disabled"] is False


@needs_repo
def test_environment_overrides_level_and_rotation(tmp_path):
    described = _load(
        SERVICES_DIR / "cart" / "app" / "logging.conf",
        tmp_path,
        {
            "LOG_LEVEL": "debug",
            "LOG_MAX_BYTES": "1000",
            "LOG_BACKUP_COUNT": "2",
            "LOG_AUDIT_MAX_BYTES": "3000",
            "LOG_AUDIT_BACKUP_COUNT": "7",
        },
    )

    assert described["root"]["level"] == "DEBUG"
    assert described["requestLogger"]["level"] == "DEBUG"
    assert all(h["level"] == "DEBUG" for h in described["root"]["handlers"])
    by_file = {h["file"]: h for h in _file_handlers(described)}
    assert (by_file["app.log"]["max_bytes"], by_file["app.log"]["backup_count"]) == (1000, 2)
    assert (by_file["request.log"]["max_bytes"], by_file["request.log"]["backup_count"]) == (1000, 2)
    assert (by_file["audit.log"]["max_bytes"], by_file["audit.log"]["backup_count"]) == (3000, 7)
    assert all(h["namer"] == "rotated_log_name" for h in by_file.values())


@needs_repo
def test_log_level_cannot_silence_the_audit_log(tmp_path):
    described = _load(SERVICES_DIR / "cart" / "app" / "logging.conf", tmp_path, {"LOG_LEVEL": "WARNING"})

    assert described["root"]["level"] == "WARNING"
    audit_file = next(h for h in described["audit"]["handlers"] if h.get("file") == "audit.log")
    assert audit_file["level"] == "INFO"
    assert described["audit"]["level"] == "INFO"


@needs_repo
@pytest.mark.parametrize("name", ["pymongo", "httpcore"])
def test_quieted_loggers_write_a_warning_once(name, tmp_path):
    conf = SERVICES_DIR / "cart" / "app" / "logging.conf"
    script = (
        "import logging\n"
        "from kugel_common.utils.logging_setup import configure_logging\n"
        f"configure_logging({str(conf)!r})\n"
        f"logging.getLogger({name!r}).warning('quieted-marker')\n"
        "logging.getLogger('app.sample').warning('app-marker')\n"
        "logging.shutdown()\n"
    )
    _run(script, tmp_path)

    app_log = (tmp_path / "app.log").read_text()
    assert app_log.count("quieted-marker") == 1
    assert app_log.count("app-marker") == 1



# Each worker writes numbered lines through its own handler on the same app.log,
# as uvicorn workers do.
WORKER = """
import logging, sys
from kugel_common.utils.logging_setup import MultiProcessRotatingFileHandler

handler = MultiProcessRotatingFileHandler("app.log", "a", {max_bytes}, {backups}, "utf-8")
logger = logging.getLogger("worker")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
for n in range({lines}):
    logger.info("worker=%s line=%05d %s", sys.argv[1], n, "x" * 40)
handler.close()
"""


def _run_workers(cwd: Path, workers: int, script: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LOG_")}
    env["PYTHONPATH"] = os.pathsep.join([str(COMMONS_SRC), env.get("PYTHONPATH", "")])
    processes = [
        subprocess.Popen([sys.executable, "-c", script, str(w)], cwd=cwd, env=env, stderr=subprocess.PIPE, text=True)
        for w in range(workers)
    ]
    for process in processes:
        assert process.wait(timeout=60) == 0, process.stderr.read()


def test_workers_sharing_a_file_rotate_it_once_per_fill_and_lose_nothing(tmp_path):
    """
    With one handler per worker on a plain RotatingFileHandler, every worker
    rotates on its own, so segments are rotated long before they are full and
    the retention that backupCount promises shrinks accordingly; once a shifted
    segment passes backupCount, lines still being written to it are deleted.
    """
    workers, lines, max_bytes = 4, 600, 2000
    _run_workers(tmp_path, workers, WORKER.format(max_bytes=max_bytes, backups=1000, lines=lines))

    kept = [line for p in tmp_path.glob("app*.log") for line in p.read_text().splitlines()]
    assert sorted(kept) == sorted(
        f"worker={w} line={n:05d} {'x' * 40}" for w in range(workers) for n in range(lines)
    )
    rotated = [p.stat().st_size for p in tmp_path.glob("app.*.log")]
    assert rotated and all(max_bytes / 2 <= size < max_bytes * 2 for size in rotated), sorted(rotated)


def test_workers_never_write_into_a_segment_rotation_has_deleted(tmp_path):
    """
    With few backups the oldest segments are dropped, as designed; what is left
    must then be the newest stretch of each worker's output with no hole in it.
    A hole means a worker kept writing into a file another worker had deleted.
    """
    workers, lines = 4, 600
    _run_workers(tmp_path, workers, WORKER.format(max_bytes=1000, backups=2, lines=lines))

    kept = [line for p in tmp_path.glob("app*.log") for line in p.read_text().splitlines()]
    for w in range(workers):
        numbers = sorted(int(line.split("line=")[1][:5]) for line in kept if line.startswith(f"worker={w} "))
        if numbers:
            assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"worker {w} has a hole"
