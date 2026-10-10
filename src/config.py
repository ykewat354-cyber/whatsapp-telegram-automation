"""Configuration management + interactive setup screen."""
from __future__ import annotations

import json
import os
import re
import sys

import requests

from . import utils

DEFAULT_CONFIG = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "openwa_port": 2785,
    "openwa_api_key": "",
    "openwa_session_name": "business-bot",
    "openwa_engine": "whatsapp-web.js",  # real browser — sab platforms pe stable
    "poll_interval": 30,
    "cooldown_seconds": 300,
    "rate_limit_per_minute": 20,
    "allow_group_automation": False,
    "broadcast_delay_seconds": 1.0,
}

ENV_TEMPLATE = os.path.join(utils.PROJECT_ROOT, "openwa.env.template")


def config_path() -> str:
    return os.path.join(utils.DATA_DIR, "config.json")


def load_config() -> dict:
    """config.json ko defaults ke saath merge karke lao."""
    cfg = dict(DEFAULT_CONFIG)
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            for key in DEFAULT_CONFIG:
                if key in saved and saved[key] not in (None, ""):
                    cfg[key] = saved[key]
        except (OSError, json.JSONDecodeError):
            pass
    # OpenWA API key auto-read (agar user ne abhi tak daali nahi)
    if not cfg.get("openwa_api_key"):
        key = detect_openwa_api_key()
        if key:
            cfg["openwa_api_key"] = key
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(config_path()), exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def is_configured(cfg: dict) -> bool:
    return bool(cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"))


def is_termux() -> bool:
    """Termux environment detect karo."""
    return "com.termux" in os.environ.get("PREFIX", "")


def detect_chromium_path() -> "str | None":
    """Termux pe installed Chromium ka path dhundo."""
    from .chromium import detect_chromium
    return detect_chromium()


def detect_openwa_api_key() -> "str | None":
    """OpenWA first boot ke baad yahan admin API key save hoti hai."""
    path = os.path.join(utils.OPENWA_DIR, "data", ".api-key")
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        return key or None
    except OSError:
        return None


def detect_chat_id(token: str) -> "str | None":
    """Bot pe last message se admin chat ID nikaalo."""
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=15
        )
        data = r.json()
        if data.get("ok") and data.get("result"):
            return str(data["result"][-1]["message"]["chat"]["id"])
    except Exception:
        pass
    return None


def write_openwa_env(cfg: dict) -> None:
    """openwa/.env ko hamare config (port + engine + chromium) ke sync mein rakho."""
    if not os.path.exists(ENV_TEMPLATE):
        return
    with open(ENV_TEMPLATE, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("__PORT__", str(cfg.get("openwa_port", 2785)))
    content = content.replace(
        "__ENGINE__", cfg.get("openwa_engine", "whatsapp-web.js")
    )
    # Chromium path — Termux pe installed Chromium use karo
    # Desktop/Codespaces pe puppeteer ka Chrome use hoga (path empty = default)
    chromium_path = detect_chromium_path() or ""
    if chromium_path:
        content = content.replace("__CHROMIUM_PATH__", chromium_path)
    else:
        # Path empty — puppeteer default Chrome use karega
        content = content.replace("PUPPETEER_EXECUTABLE_PATH=__CHROMIUM_PATH__", "# PUPPETEER_EXECUTABLE_PATH=puppeteer-default")
    env_path = os.path.join(utils.OPENWA_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            if f.read() == content:
                return
    os.makedirs(utils.OPENWA_DIR, exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)


# ----------------------------------------------------------------------
# Interactive setup screen
# ----------------------------------------------------------------------

BANNER = r"""
╔══════════════════════════════════════════════════╗
║   WhatsApp Business Automation — Setup Screen     ║
║   Telegram Admin Panel + OpenWA Gateway           ║
╚══════════════════════════════════════════════════╝
"""


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        print(
            "\n⚠️  Interactive terminal nahi hai. Manual config ke liye "
            "data/config.json edit karein."
        )
        sys.exit(1)
    return value or default


def run_setup_screen() -> dict:
    print(BANNER)
    if is_termux():
        print("⚠️  Termux detected! Engine ke liye baileys (option 2) choose karein —")
        print("    whatsapp-web.js ko Chrome chahiye hota hai jo Termux pe nahi chalta.\n")
    cfg = load_config()

    print("=== Telegram Bot Setup ===")
    token = _input("Telegram Bot Token (@BotFather se)", cfg["telegram_bot_token"])
    while not re.match(r"^\d{6,}:[A-Za-z0-9_-]{20,}$", token):
        print("  ⚠️  Token format galat lag raha hai. Dobara try karein.")
        token = _input("Telegram Bot Token")
    cfg["telegram_bot_token"] = token

    chat_id = cfg.get("telegram_chat_id") or ""
    if not chat_id:
        print("\n👉 Ab apne Telegram bot pe koi bhi message bhejein (e.g. /start).")
        input("   Message bhejne ke baad yahan Enter dabayein...")
        detected = detect_chat_id(token)
        if detected:
            print(f"   ✅ Chat ID auto-detect ho gaya: {detected}")
            chat_id = detected
        else:
            print("   ⚠️  Chat ID nahi mila. Manual enter karein (apna Telegram user ID):")
            chat_id = _input("   Telegram Chat ID")
    cfg["telegram_chat_id"] = chat_id

    print("\n=== OpenWA (WhatsApp Gateway) Setup ===")
    port = _input("OpenWA Port", str(cfg["openwa_port"]))
    cfg["openwa_port"] = int(port) if port.isdigit() else 2785

    api_key = detect_openwa_api_key() or cfg.get("openwa_api_key") or ""
    if api_key:
        print(f"   ✅ OpenWA API key auto-read ho gaya ({api_key[:8]}...)")
    else:
        api_key = _input("OpenWA API Key (openwa/data/.api-key file se)")
    cfg["openwa_api_key"] = api_key

    cfg["openwa_session_name"] = (
        _input("WhatsApp Session Name", cfg["openwa_session_name"]) or "business-bot"
    )

    print("\n=== WhatsApp Engine ===")
    if is_termux():
        chromium = detect_chromium_path()
        if chromium:
            print(f"  ✅ Chromium mila: {chromium}")
            print("  1) whatsapp-web.js  — recommended (real browser, stable)")
            print("  2) baileys          — lightweight (Termux pe reject ho sakta hai)")
            eng = _input("Engine (1/2)", "1")
        else:
            print("  ⚠️  Chromium nahi mila. Pehle install karein: pkg install chromium")
            print("  1) whatsapp-web.js  — needs Chromium")
            print("  2) baileys          — no browser needed")
            eng = _input("Engine (1/2)", "2")
    else:
        print("  1) whatsapp-web.js  — recommended, low ban risk (Chrome ~500MB RAM)")
        print("  2) baileys          — lightweight (~80MB RAM), low-RAM devices ke liye")
        eng = _input("Engine (1/2)", "1")
    cfg["openwa_engine"] = "baileys" if eng == "2" else "whatsapp-web.js"

    print("\n=== Safety Settings ===")
    cd = _input("Automation cooldown per contact (seconds)", str(cfg["cooldown_seconds"]))
    cfg["cooldown_seconds"] = int(cd) if cd.isdigit() else 300
    rl = _input("Max outgoing messages per minute", str(cfg["rate_limit_per_minute"]))
    cfg["rate_limit_per_minute"] = int(rl) if rl.isdigit() else 20
    grp = _input("Group messages pe automation allow karein? (haan/na)", "na")
    cfg["allow_group_automation"] = grp.lower() in ("haan", "yes", "y", "1")

    save_config(cfg)
    write_openwa_env(cfg)
    print("\n✅ Config save ho gaya!")
    print("\nAb WhatsApp connect karne ke liye:")
    print("   python3 run.py")
    print("Phir Telegram bot pe /connect bhejein — QR Telegram pe bheja jayega.")
    return cfg
