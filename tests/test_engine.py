"""Automation engine tests — matching, cooldown, first_time_only, blacklist, rate limit."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils
from src.automation_engine import AutomationEngine
from src.storage import Storage


def make_msg(msg_id, body, phone="919876543210", chat_id=None, direction="incoming"):
    return {
        "id": msg_id,
        "chatId": chat_id or f"{phone}@c.us",
        "from": f"{phone}@c.us",
        "body": body,
        "type": "text",
        "direction": direction,
        "timestamp": time.time(),
    }


class FakeOpenWA:
    def __init__(self):
        self.session_id = "sess-1"
        self.sent = []

    def send_text(self, session_id, chat_id, text):
        self.sent.append((chat_id, text))
        return "msg-x"


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wta-test-")
        self.storage = Storage(data_dir=self.tmp)
        self.openwa = FakeOpenWA()
        self.config = {
            "cooldown_seconds": 300,
            "rate_limit_per_minute": 20,
            "allow_group_automation": False,
        }
        self.engine = AutomationEngine(self.storage, self.config, self.openwa)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add_auto(self, trigger, reply="Reply!", **kw):
        auto = {
            "id": "a1",
            "trigger": trigger,
            "reply": reply,
            "match": "contains",
            "enabled": True,
            "first_time_only": True,
            "cooldown": None,
        }
        auto.update(kw)
        self.storage.add_automation(auto)
        return auto

    # ---------- matching ----------
    def test_match_contains(self):
        self.assertTrue(AutomationEngine.match_trigger("price", "what is the price?", "contains"))
        self.assertTrue(AutomationEngine.match_trigger("price", "Bhai PRICE kya hai", "contains"))

    def test_match_exact(self):
        self.assertTrue(AutomationEngine.match_trigger("hello", "Hello", "exact"))
        self.assertFalse(AutomationEngine.match_trigger("hello", "Hello there", "exact"))

    def test_match_starts(self):
        self.assertTrue(AutomationEngine.match_trigger("hel", "Hello there", "starts"))
        self.assertFalse(AutomationEngine.match_trigger("hel", "Say hi", "starts"))

    def test_match_regex(self):
        self.assertTrue(AutomationEngine.match_trigger(r"price \d+", "price 100", "regex"))
        self.assertFalse(AutomationEngine.match_trigger(r"price \d+", "price", "regex"))

    # ---------- first_time_only (default) ----------
    def test_first_message_fires(self):
        self.add_auto("price")
        self.engine.process_message(make_msg("1", "what is the price?"))
        self.assertEqual(len(self.openwa.sent), 1)
        self.assertEqual(self.openwa.sent[0][0], "919876543210@c.us")

    def test_second_message_blocked_by_first_time_only(self):
        self.add_auto("price")
        self.engine.process_message(make_msg("1", "price?"))
        self.engine.process_message(make_msg("2", "price?"))
        self.assertEqual(len(self.openwa.sent), 1)

    # ---------- cooldown ----------
    def test_cooldown_blocks_refire(self):
        self.add_auto("hi", first_time_only=False)
        self.engine.process_message(make_msg("1", "hi"))
        self.engine.process_message(make_msg("2", "hi"))
        self.assertEqual(len(self.openwa.sent), 1)

    def test_cooldown_expires(self):
        self.add_auto("hi", first_time_only=False, cooldown=1)
        self.engine.process_message(make_msg("1", "hi"))
        time.sleep(1.1)
        self.engine.process_message(make_msg("2", "hi"))
        self.assertEqual(len(self.openwa.sent), 2)

    def test_cooldown_zero_means_no_cooldown(self):
        self.add_auto("hi", first_time_only=False, cooldown=0)
        self.engine.process_message(make_msg("1", "hi"))
        self.engine.process_message(make_msg("2", "hi"))
        self.assertEqual(len(self.openwa.sent), 2)

    # ---------- safety guards ----------
    def test_blacklist_blocks(self):
        self.add_auto("price")
        self.storage.add_blacklist("919876543210")
        self.engine.process_message(make_msg("1", "price?"))
        self.assertEqual(len(self.openwa.sent), 0)

    def test_own_number_skipped(self):
        self.add_auto("price")
        self.storage.set_own_phone("919876543210")
        self.engine.process_message(make_msg("1", "price?"))
        self.assertEqual(len(self.openwa.sent), 0)

    def test_group_skipped_by_default(self):
        self.add_auto("price")
        self.engine.process_message(make_msg("1", "price?", chat_id="120363000000000000@g.us"))
        self.assertEqual(len(self.openwa.sent), 0)

    def test_group_allowed_when_enabled(self):
        self.config["allow_group_automation"] = True
        self.add_auto("price")
        self.engine.process_message(make_msg("1", "price?", chat_id="120363000000000000@g.us"))
        self.assertEqual(len(self.openwa.sent), 1)

    def test_outgoing_ignored(self):
        self.add_auto("price")
        self.engine.process_message(make_msg("1", "price?", direction="outgoing"))
        self.assertEqual(len(self.openwa.sent), 0)

    def test_non_text_body_ignored(self):
        self.add_auto("price")
        self.engine.process_message(make_msg("1", ""))
        self.assertEqual(len(self.openwa.sent), 0)

    # ---------- rate limit ----------
    def test_rate_limit_blocks_excess(self):
        self.config["rate_limit_per_minute"] = 2
        self.add_auto("hi", first_time_only=False, cooldown=0)
        for i in range(5):
            self.engine.process_message(make_msg(str(i), "hi"))
        self.assertEqual(len(self.openwa.sent), 2)

    # ---------- rule parsing ----------
    def test_parse_rule(self):
        from src.telegram_bot import TelegramAdminBot

        self.assertEqual(
            TelegramAdminBot._parse_rule("price => Humara rate..."),
            ("price", "Humara rate...", "contains"),
        )
        self.assertEqual(
            TelegramAdminBot._parse_rule("exact:hello => Welcome"),
            ("hello", "Welcome", "exact"),
        )
        self.assertEqual(
            TelegramAdminBot._parse_rule("starts:hi => Hi!"),
            ("hi", "Hi!", "starts"),
        )
        self.assertEqual(
            TelegramAdminBot._parse_rule("regex:price|cost => Rate..."),
            ("price|cost", "Rate...", "regex"),
        )
        self.assertIsNone(TelegramAdminBot._parse_rule("no separator"))
        self.assertIsNone(TelegramAdminBot._parse_rule("=> empty trigger"))

    def test_is_termux_detection(self):
        from src.config import is_termux

        old_prefix = os.environ.get("PREFIX", "")
        try:
            os.environ["PREFIX"] = "/data/data/com.termux/files/usr"
            self.assertTrue(is_termux())
            os.environ["PREFIX"] = "/usr/local"
            self.assertFalse(is_termux())
        finally:
            if old_prefix:
                os.environ["PREFIX"] = old_prefix
            else:
                os.environ.pop("PREFIX", None)


if __name__ == "__main__":
    unittest.main()
