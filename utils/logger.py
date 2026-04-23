"""
utils/logger.py
---------------
Dual-file structured logger.
  • sent_emails.log   — every successfully dispatched email
  • failed_emails.log — every failure with error detail
Also streams INFO+ to stdout for real-time CLI feedback.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from config import settings


def _ensure_dirs() -> None:
    Path(settings.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)


_ensure_dirs()


# ── Formatters ────────────────────────────────────────────────────────────────
_FMT = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _file_handler(path: str, level: int) -> logging.FileHandler:
    h = logging.FileHandler(path, encoding="utf-8")
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    return h


def _stream_handler() -> logging.StreamHandler:
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    return h


# ── Root logger (all messages) ────────────────────────────────────────────────
root_logger = logging.getLogger("email_automation")
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(_stream_handler())
root_logger.addHandler(_file_handler(settings.SENT_LOG, logging.DEBUG))

# ── Failed-email logger ────────────────────────────────────────────────────────
failed_logger = logging.getLogger("email_automation.failed")
failed_logger.setLevel(logging.WARNING)
failed_logger.addHandler(_file_handler(settings.FAILED_LOG, logging.WARNING))
failed_logger.propagate = True   # also goes to root (and stdout)


# ── Public helpers ─────────────────────────────────────────────────────────────
def log_sent(email: str, name: str, company: str) -> None:
    root_logger.info(
        "SENT | to=%s | name=%s | company=%s",
        email, name, company
    )


def log_skipped(email: str, reason: str) -> None:
    root_logger.info("SKIP | to=%s | reason=%s", email, reason)


def log_failed(email: str, error: str) -> None:
    msg = "FAIL | to=%s | error=%s"
    root_logger.error(msg, email, error)
    failed_logger.error(msg, email, error)


def log_invalid_row(row_num: int, data: dict, reason: str) -> None:
    root_logger.warning(
        "INVALID_ROW | row=%d | data=%s | reason=%s",
        row_num, data, reason
    )


def log_info(msg: str, *args) -> None:
    root_logger.info(msg, *args)


def log_error(msg: str, *args) -> None:
    root_logger.error(msg, *args)
