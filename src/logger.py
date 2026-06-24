"""
Centralized logging for the Gmail NOC Agent.

Writes structured log entries to logs/agent.log with automatic daily rotation.
Each log line includes a UTC timestamp, log level, and message.
"""

import logging
import logging.handlers
import os
import sys


# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOGS_DIR, "agent.log")

os.makedirs(LOGS_DIR, exist_ok=True)


# ── Formatter ──────────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"


class _UTCFormatter(logging.Formatter):
    """Always format timestamps in UTC regardless of the local timezone."""
    import time as _time
    converter = _time.gmtime


# ── Handler: rotating file (10 MB max, keep 7 backups) ────────────────────────
def _build_file_handler() -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(_UTCFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.setLevel(logging.DEBUG)
    return handler


# ── Handler: console (stdout) ──────────────────────────────────────────────────
def _build_console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_UTCFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.setLevel(logging.INFO)
    return handler


# ── Root logger setup ──────────────────────────────────────────────────────────
def setup_logging(level: int = logging.DEBUG) -> None:
    """
    Call once at program startup (in main.py) to configure the root logger.

    After this call every module can do:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("...")
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured — avoid duplicate handlers on re-import
        return

    root.setLevel(level)
    root.addHandler(_build_file_handler())
    root.addHandler(_build_console_handler())

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "google.auth", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Convenience getter ─────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call setup_logging() first."""
    return logging.getLogger(name)
