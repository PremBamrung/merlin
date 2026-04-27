"""
Shared logger for the backend package.
"""

import logging
from pathlib import Path
import sys

from backend.config import settings

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_handler_console = logging.StreamHandler(sys.stdout)
_handler_console.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

_handler_file = logging.FileHandler(_LOG_DIR / "merlin_backend.log", encoding="utf-8")
_handler_file.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logger = logging.getLogger("merlin.backend")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
logger.addHandler(_handler_console)
logger.addHandler(_handler_file)
logger.propagate = False
