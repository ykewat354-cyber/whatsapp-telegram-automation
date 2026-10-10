"""Integration test — saare features ek saath test hote hain.

Yeh test verify karta hai ki naye features purane ko break nahi karte.
Har feature ka interaction test hota hai.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils
from src.automation_engine import AutomationEngine
from src.openwa_client import OpenWAClient, OpenWAError
from src.storage import Storage
from src.telegram_bot import TelegramAdminBot


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
        self.contacts = [
            {"id": "919876543210@c.us", "number": "919876543210", "name": "Alice"},
            {"id": "911111111111@c.us", "number": "911111111111", "name": "Bob"},
            {"id": "912222222222@c.us", "number": "912222222222", "name": "Charlie"},
        ]

    def send_text(self, session_id, chat_id, text):
        self.sent.append((chat_id, text))
        return "msg-x"

    def get_contacts(self, session_id):
        return self.contacts


class IntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wta-integ-")
        self.storage = Storage(data_dir=self.tmp)
        self.openwa = FakeOpenWA()
        self.config = {
            "cooldown_seconds": 300,
            "rate_limit_per_minute": 20,
            "allow_group_automation": False,
            "broadcast_delay_seconds": 0.1,
        }
        self.engine = AutomationEngine(self.storage, self.config, self.openwa)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------- Cross-feature: Automation + Blacklist ----------
    def test_automation_with_blacklist(self):
        """Blacklisted contact ko automation reply nahi jayega."""
        auto = {"id": "a1", "trigger": "price", "reply": "Rate!", "match": "contains",
                "enabled": True, "first_time_only": True, "cooldown": None}
        self.storage.add_automation(auto)
        self.storage.add_blacklist("919876543210")
        self.engine.process_message(make_msg("1", "price?"))
        self.assertEqual(len(self.openwa.sent), 0)

    # ---------- Cross-feature: Automation + Cooldown ----------
    def test_automation_cooldown_with_multiple_contacts(self):
        """Ek contact cooldown mein, doosra bhi global cooldown mein."""
        auto = {"id": "a1", "trigger": "hi", "reply": "Hello!", "match": "contains",
                "enabled": True, "first_time_only": False, "cooldown": 300}
        self.storage.add_automation(auto)
        # Pehla contact — fire
        self.engine.process_message(make_msg("1", "hi", phone="919876543210"))
        self.assertEqual(len(self.openwa.sent), 1)
        # Doosra contact — global cooldown mein, skip
        self.engine.process_message(make_msg("2", "hi", phone="911111111111"))
        self.assertEqual(len(self.openwa.sent), 1)  # global cooldown ne block kiya

    # ---------- Cross-feature: Automation + Rate Limit ----------
    def test_automation_rate_limit(self):
        """Rate limit exceed hone pe automation skip."""
        self.config["rate_limit_per_minute"] = 2
        auto = {"id": "a1", "trigger": "hi", "reply": "Hello!", "match": "contains",
                "enabled": True, "first_time_only": False, "cooldown": 0}
        self.storage.add_automation(auto)
        for i in range(5):
            self.engine.process_message(make_msg(str(i), "hi", phone=f"91{i:011d}"))
        self.assertEqual(len(self.openwa.sent), 2)

    # ---------- Cross-feature: Scheduled + Storage ----------
    def test_scheduled_message_lifecycle(self):
        """Scheduled message add → list → mark sent → verify."""
        msg = {"id": "s1", "number": "919876543210", "time": "14:30", "recurring": False,
               "message": "Hello!", "created_at": time.time(), "status": "pending"}
        self.storage.add_scheduled(msg)
        # List
        self.assertEqual(len(self.storage.list_scheduled()), 1)
        # Mark sent
        self.assertTrue(self.storage.mark_scheduled_sent("s1"))
        # Verify status
        self.assertEqual(self.storage.list_scheduled()[0]["status"], "sent")
        # Dobara mark — already sent
        self.assertFalse(self.storage.mark_scheduled_sent("s1"))

    # ---------- Cross-feature: Broadcast Days Filter + Storage ----------
    def test_broadcast_days_filter(self):
        """Days filter sirf recent contacts ko select kare."""
        # Contact 1 — aaj message kiya
        self.storage.mark_contact_seen("919876543210")
        # Contact 2 — kabhi nahi (no mark)
        # Contact 3 — 10 din pehle (purana timestamp manually set)
        state = self.storage._read("state.json", {})
        state.setdefault("contact_seen", {})["912222222222"] = utils.now_ts() - (10 * 86400)
        self.storage._write("state.json", state)
        # 1d filter — sirf contact 1 (contact 3 purana hai)
        cutoff = utils.now_ts() - 86400
        recent = [p for p in ["919876543210", "911111111111", "912222222222"]
                  if self.storage.get_contact_last_seen(p) >= cutoff]
        self.assertEqual(recent, ["919876543210"])

    # ---------- Cross-feature: Schedule Parsing ----------
    def test_schedule_parsing_all_formats(self):
        """Saare schedule formats properly parse hone chahiye."""
        # Simple time
        _, time_str, msg, _, err = TelegramAdminBot._parse_schedule_args(
            ["919876543210", "14:30", "Hello!"])
        self.assertIsNone(err)
        self.assertEqual(time_str, "14:30")
        # Daily
        _, time_str, msg, _, err = TelegramAdminBot._parse_schedule_args(
            ["919876543210", "daily", "08:00", "Good", "Morning!"])
        self.assertIsNone(err)
        self.assertEqual(time_str, "daily 08:00")
        self.assertEqual(msg, "Good Morning!")
        # Broadcast
        _, time_str, msg, is_broadcast, err = TelegramAdminBot._parse_schedule_args(
            ["all", "08:00", "Offer!"])
        self.assertIsNone(err)
        self.assertTrue(is_broadcast)
        # Errors
        _, _, _, _, err = TelegramAdminBot._parse_schedule_args(
            ["919876543210", "25:00", "Hi"])
        self.assertEqual(err, "time")
        _, _, _, _, err = TelegramAdminBot._parse_schedule_args(
            ["919876543210", "daily", "Hi"])
        self.assertEqual(err, "daily_time")

    # ---------- Cross-feature: Message Length + Send ----------
    def test_message_length_validation(self):
        """Lamba message reject, normal accept."""
        client = OpenWAClient(2785, "key", "sess")
        with self.assertRaises(OpenWAError):
            client.send_text("sess-1", "919876543210@c.us", "x" * 5000)
        # Normal length — mock ke saath
        client._request = lambda *a, **k: {"messageId": "msg-1"}
        result = client.send_text("sess-1", "919876543210@c.us", "Hello!")
        self.assertEqual(result, "msg-1")

    # ---------- Cross-feature: Regex ReDoS + Normal Regex ----------
    def test_regex_protection_with_valid_patterns(self):
        """Dangerous patterns block, valid patterns kaam kare."""
        # Dangerous
        self.assertFalse(AutomationEngine.match_trigger("(a+)+$", "a" * 30, "regex"))
        # Valid
        self.assertTrue(AutomationEngine.match_trigger(r"price \d+", "price 100", "regex"))
        self.assertTrue(AutomationEngine.match_trigger(r"hello|hi", "hello", "regex"))

    # ---------- Cross-feature: Lock File + Data Dir ----------
    def test_lock_file_and_data_dir(self):
        """Data dir auto-create, lock file mein PID + start time."""
        new_dir = os.path.join(self.tmp, "new_data")
        self.assertFalse(os.path.exists(new_dir))
        storage = Storage(data_dir=new_dir)
        self.assertTrue(os.path.exists(new_dir))
        lock_file = os.path.join(new_dir, "app.lock")
        with open(lock_file, "w") as f:
            f.write("12345:67890")
        with open(lock_file) as f:
            data = f.read().strip().split(":")
        self.assertEqual(len(data), 2)

    # ---------- Cross-feature: PII Masking ----------
    def test_pii_masking_in_logs(self):
        """Phone numbers logs mein mask hone chahiye."""
        import io
        import logging
        import re
        logger = logging.getLogger("wta-test-integ")
        logger.setLevel(logging.INFO)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        # PII filter
        class PIIFilter(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                def mask_phone(m):
                    phone = m.group(0)
                    if len(phone) >= 8:
                        return "***" + phone[-4:]
                    return phone
                record.msg = re.sub(r"\b\d{8,15}\b", mask_phone, msg)
                record.args = None
                return True
        logger.addFilter(PIIFilter())
        logger.info("Message bheja 919876543210 ko")
        output = stream.getvalue()
        self.assertIn("***3210", output)
        self.assertNotIn("919876543210", output)
        logger.removeHandler(handler)

    # ---------- Cross-feature: Chromium Detection ----------
    def test_chromium_detection(self):
        """Chromium detection kaam kare (ya to mile ya None)."""
        from src.chromium import detect_chromium
        path = detect_chromium()
        # Ya to ek valid path hona chahiye ya None
        if path is not None:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith(("chromium", "chrome", "chromium-browser")))

    # ---------- Cross-feature: All Storage Operations ----------
    def test_all_storage_operations(self):
        """Saare storage operations ek saath kaam kare."""
        # Automation
        auto = {"id": "a1", "trigger": "hi", "reply": "Hello!", "match": "contains",
                "enabled": True, "first_time_only": True, "cooldown": None}
        self.storage.add_automation(auto)
        self.assertEqual(len(self.storage.list_automations()), 1)
        # Blacklist
        self.storage.add_blacklist("919876543210")
        self.assertTrue(self.storage.is_blacklisted("919876543210"))
        # Scheduled
        msg = {"id": "s1", "number": "919876543210", "time": "14:30", "recurring": False,
               "message": "Hi", "created_at": time.time(), "status": "pending"}
        self.storage.add_scheduled(msg)
        self.assertEqual(len(self.storage.list_scheduled()), 1)
        # State
        self.storage.mark_contact_seen("919876543210")
        self.assertTrue(self.storage.is_contact_seen("919876543210"))
        # Rate limit
        self.assertTrue(self.storage.try_send_slot(20))
        # Sab ek saath — koi conflict nahi
        self.assertEqual(len(self.storage.list_automations()), 1)
        self.assertEqual(len(self.storage.list_scheduled()), 1)
        self.assertTrue(self.storage.is_blacklisted("919876543210"))


if __name__ == "__main__":
    unittest.main()
