"""Shared helper utilities."""
from __future__ import annotations

import logging
import os
import re
import sys
import time

# Project layout (all runtime paths are relative to the project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OPENWA_DIR = os.path.join(PROJECT_ROOT, "openwa")

# Default module-level logger (setup_logging() ise configure karta hai)
logger = logging.getLogger("wta")


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Console logging for the whole app."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    )
    root = logging.getLogger("wta")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    return root


def normalize_phone(raw) -> "str | None":
    """'+91 98765-43210' -> '919876543210'. Invalid -> None."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 8 or len(digits) > 15:
        return None
    return digits


def phone_to_chat_id(digits: str) -> str:
    """'919876543210' -> '919876543210@c.us' (WhatsApp chat id)."""
    return f"{digits}@c.us"


def chat_id_to_phone(chat_id) -> "str | None":
    """'919876543210@c.us' -> '919876543210'."""
    if not chat_id:
        return None
    return normalize_phone(str(chat_id).split("@")[0])


def is_group_chat(chat_id) -> bool:
    return bool(chat_id) and str(chat_id).endswith("@g.us")


def now_ts() -> float:
    return time.time()
