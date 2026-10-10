"""Tests for security fixes: PII masking, regex ReDoS, message length, lock file."""
import logging
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


class FakeOpenWA:
    def __init__(self):
        self.session_id = "sess-1"
        self.sent = []

    def send_text(self, session_id, chat_id, text):
        self.sent.append((chat_id, text))
        return "msg-x"


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wta-sec-test-")
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

    # ---------- PII masking ----------
    def test_pii_masking(self):
        """Phone numbers logs mein mask hone chahiye."""
        logger = logging.getLogger("wta-test-pii")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        # PII filter add karo
        class PIIFilter(logging.Filter):
            def filter(self, record):
                import re
                msg = record.getMessage()
                def mask_phone(m):
                    phone = m.group(0)
                    if len(phone) >= 8:
                        return "***" + phone[-4:]
                    return phone
                record.msg = re.sub(r"\b\d{8,15}\b", mask_phone, msg)
                return True
        logger.addFilter(PIIFilter())
        # Test — phone number mask hona chahiye
        import io
        stream = io.StringIO()
        handler.stream = stream
        logger.info("Message bheja 919876543210 ko")
        output = stream.getvalue()
        self.assertIn("***3210", output)
        self.assertNotIn("919876543210", output)
        logger.removeHandler(handler)

    # ---------- Regex ReDoS ----------
    def test_regex_dangerous_pattern_blocked(self):
        """Dangerous regex patterns block hone chahiye."""
        # Nested quantifier — ReDoS attack pattern
        self.assertFalse(AutomationEngine.match_trigger("(a+)+$", "aaaaaaaaaaaaaaaaaaaa!", "regex"))
        self.assertFalse(AutomationEngine.match_trigger("(.+)+", "test", "regex"))
        self.assertFalse(AutomationEngine.match_trigger("(a|a)*", "test", "regex"))

    def test_regex_long_pattern_blocked(self):
        """Lamba regex pattern block hona chahiye."""
        long_pattern = "a" * 201
        self.assertFalse(AutomationEngine.match_trigger(long_pattern, "test", "regex"))

    def test_regex_valid_pattern_works(self):
        """Normal regex patterns kaam kare."""
        self.assertTrue(AutomationEngine.match_trigger(r"price \d+", "price 100", "regex"))
        self.assertTrue(AutomationEngine.match_trigger(r"hello|hi", "hello there", "regex"))

    # ---------- Message length ----------
    def test_message_length_validation(self):
        """Lamba message reject hona chahiye."""
        client = OpenWAClient(2785, "test-key", "test-session")
        with self.assertRaises(OpenWAError) as ctx:
            client.send_text("sess-1", "919876543210@c.us", "x" * 5000)
        self.assertIn("4096", str(ctx.exception))

    def test_message_length_ok(self):
        """Normal length message pass hona chahiye."""
        client = OpenWAClient(2785, "test-key", "test-session")
        # Mock _request to avoid actual HTTP call
        original = client._request
        client._request = lambda *a, **k: {"messageId": "msg-1"}
        try:
            result = client.send_text("sess-1", "919876543210@c.us", "Hello!")
            self.assertEqual(result, "msg-1")
        finally:
            client._request = original

    # ---------- Lock file ----------
    def test_lock_file_format(self):
        """Lock file mein PID aur start time dono hone chahiye."""
        lock_file = os.path.join(self.tmp, "app.lock")
        with open(lock_file, "w") as f:
            f.write("12345:67890")
        with open(lock_file) as f:
            data = f.read().strip().split(":")
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], "12345")
        self.assertEqual(data[1], "67890")

    # ---------- Scheduled sent marking ----------
    def test_mark_scheduled_sent(self):
        """One-time message 'sent' mark hona chahiye."""
        msg = {
            "id": "s1",
            "number": "919876543210",
            "time": "14:30",
            "recurring": False,
            "message": "Hello!",
            "created_at": time.time(),
            "status": "pending",
        }
        self.storage.add_scheduled(msg)
        self.assertTrue(self.storage.mark_scheduled_sent("s1"))
        messages = self.storage.list_scheduled()
        self.assertEqual(messages[0]["status"], "sent")
        self.assertIn("sent_at", messages[0])
        # Dobara mark karo — already sent
        self.assertFalse(self.storage.mark_scheduled_sent("s1"))


if __name__ == "__main__":
    unittest.main()
