import logging
import os
from datetime import datetime

# ── Log file location ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "app.log")

# ── Log format ────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Setup logger ──────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger that writes to app.log file only.
    Usage:
        from logger import get_logger
        logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File handler — writes all logs to app.log
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    logger.addHandler(file_handler)
    logger.propagate = False

    return logger


# ── Convenience loggers ───────────────────────────────────────
api_logger   = get_logger("api")        # for API requests/responses
sql_logger   = get_logger("sql")        # for SQL queries
error_logger = get_logger("error")      # for errors and exceptions