"""Application bootstrap — sab services ko jodta hai."""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import threading

from . import utils
from .automation_engine import AutomationEngine
from .config import is_configured, load_config, run_setup_screen, write_openwa_env
from .openwa_client import OpenWAClient, OpenWAService
from .storage import Storage
from .telegram_bot import TelegramAdminBot


class AsyncBridge:
    """Doosre threads se bot ke event loop mein coroutine schedule karta hai."""

    def __init__(self):
        self.loop = None

    def set_loop(self, loop) -> None:
        self.loop = loop

    def run_async(self, coro):
        if self.loop is not None and self.loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None


def poller_loop(openwa, engine, storage, config, stop_event, start_event, logger) -> None:
    """Background thread: incoming WhatsApp messages poll karke engine ko deta hai."""
    logger.info("Message poller ready")
    start_event.wait(timeout=120)
    while not stop_event.is_set():
        try:
            if openwa.session_id:
                session = openwa.get_session(openwa.session_id)
                if session.get("status") == "ready":
                    msgs = openwa.get_messages(openwa.session_id, direction="incoming", limit=50)
                    fresh = [m for m in msgs if not storage.is_message_processed(m.get("id"))]
                    for m in sorted(fresh, key=lambda x: x.get("timestamp") or 0):
                        engine.process_message(m)
                        storage.mark_message_processed(m.get("id"))
        except Exception as e:
            logger.error("Poller error: %s", e)
        stop_event.wait(config.get("poll_interval", 5))
    logger.info("Poller stopped")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WhatsApp Business Automation + Telegram Admin Panel"
    )
    parser.add_argument("--setup", action="store_true", help="Configuration screen chalayein")
    parser.add_argument("--version", action="store_true", help="Version dikha kar band ho")
    args = parser.parse_args()

    if args.version:
        from . import __version__

        print(f"whatsapp-telegram-automation v{__version__}")
        return

    utils.setup_logging()
    logger = utils.logger
    os.makedirs(utils.DATA_DIR, exist_ok=True)

    # ---- single-instance guard ----
    # Purana instance background mein chal raha ho to naya start nahi hoga
    # (Telegram pe "Conflict: terminated by other getUpdates request" error aata hai)
    lock_file = os.path.join(utils.DATA_DIR, "app.lock")
    if os.path.exists(lock_file):
        try:
            old_pid = int(open(lock_file).read().strip())
            os.kill(old_pid, 0)  # process check
            logger.error(
                "Ek instance pehle se chal raha hai (pid %s).\n"
                "Pehle use band karein: kill %s\n"
                "Ya lock delete karein: rm %s",
                old_pid, old_pid, lock_file,
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            pass  # purana lock stale hai
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    config = load_config()
    if args.setup or not is_configured(config):
        config = run_setup_screen()
    else:
        write_openwa_env(config)

    storage = Storage()
    service = OpenWAService(utils.OPENWA_DIR, config.get("openwa_port", 2785), logger)
    client = OpenWAClient(
        config.get("openwa_port", 2785),
        config.get("openwa_api_key", ""),
        config.get("openwa_session_name", "business-bot"),
        logger,
    )
    engine = AutomationEngine(storage, config, client, logger)
    bridge = AsyncBridge()
    bot = TelegramAdminBot(config, storage, client, engine, bridge, service, logger)

    # Engine alerts ko Telegram admin tak pohchata hai
    engine.notify = lambda text: bridge.run_async(bot.send_admin(text))

    # ---- OpenWA service ----
    if not service.is_built():
        logger.error(
            "OpenWA built nahi hai. Pehle installer chalayein:\n"
            "  curl -sSL https://raw.githubusercontent.com/ykewat354-cyber/"
            "whatsapp-telegram-automation/main/install.sh | bash"
        )
        sys.exit(1)
    if not service.is_running():
        logger.info("OpenWA service start ho rahi hai...")
        service.start()
    if not service.wait_for_health(120):
        logger.error("OpenWA service healthy nahi hui. Log: data/openwa.log")
        sys.exit(1)

    try:
        client.session_id = client.ensure_session()
    except Exception as e:
        logger.error("Session create failed: %s", e)
        sys.exit(1)

    # ---- background threads ----
    stop_event = threading.Event()
    start_event = threading.Event()
    poller = threading.Thread(
        target=poller_loop,
        args=(client, engine, storage, config, stop_event, start_event, logger),
        daemon=True,
    )
    poller.start()

    def shutdown(*_):
        logger.info("Shutdown ho raha hai...")
        stop_event.set()
        start_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        asyncio.run(bot.start(client.session_id, stop_event, start_event))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Bot error: %s", e)
    finally:
        stop_event.set()
        start_event.set()
        poller.join(timeout=10)
        service.stop()
        try:
            os.remove(lock_file)
        except OSError:
            pass
        logger.info("Khatam. Phir se chalane ke liye: python3 run.py")


if __name__ == "__main__":
    main()
