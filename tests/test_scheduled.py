"""Tests for scheduled messages, days filter, and new features."""
import datetime
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils
from src.storage import Storage


class ScheduledMessageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wta-sched-test-")
        self.storage = Storage(data_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_list_scheduled(self):
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
        messages = self.storage.list_scheduled()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], "s1")
        self.assertEqual(messages[0]["message"], "Hello!")

    def test_remove_scheduled(self):
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
        self.assertTrue(self.storage.remove_scheduled("s1"))
        self.assertEqual(len(self.storage.list_scheduled()), 0)
        self.assertFalse(self.storage.remove_scheduled("s1"))  # already removed

    def test_next_scheduled_id(self):
        self.assertEqual(self.storage.next_scheduled_id(), "s1")
        msg = {"id": "s1", "number": "919876543210", "time": "14:30", "recurring": False, "message": "Hi", "created_at": time.time(), "status": "pending"}
        self.storage.add_scheduled(msg)
        self.assertEqual(self.storage.next_scheduled_id(), "s2")

    def test_contact_last_seen(self):
        self.assertEqual(self.storage.get_contact_last_seen("919876543210"), 0)
        self.storage.mark_contact_seen("919876543210")
        last_seen = self.storage.get_contact_last_seen("919876543210")
        self.assertGreater(last_seen, 0)

    def test_days_filter_logic(self):
        """Days filter ka logic test karo."""
        # Contact jo 2 din pehle message kiya
        self.storage.mark_contact_seen("919876543210")
        # Contact jo kabhi nahi message kiya
        # (no mark_contact_seen call)
        now = utils.now_ts()
        # 1d filter — dono chahiye (ek hai, ek nahi)
        cutoff_1d = now - (1 * 86400)
        self.assertGreater(self.storage.get_contact_last_seen("919876543210"), cutoff_1d)
        self.assertEqual(self.storage.get_contact_last_seen("911111111111"), 0)

    def test_time_filter_logic(self):
        """Minutes/hours/days filter ka logic test karo."""
        self.storage.mark_contact_seen("919876543210")
        now = utils.now_ts()
        # 30m filter — 30 min pehle aaya tha, to match hona chahiye
        cutoff_30m = now - (30 * 60)
        self.assertGreater(self.storage.get_contact_last_seen("919876543210"), cutoff_30m)
        # 2h filter
        cutoff_2h = now - (2 * 3600)
        self.assertGreater(self.storage.get_contact_last_seen("919876543210"), cutoff_2h)
        # 1d filter
        cutoff_1d = now - (1 * 86400)
        self.assertGreater(self.storage.get_contact_last_seen("919876543210"), cutoff_1d)


class ScheduleTimeParsingTestCase(unittest.TestCase):
    def test_parse_daily_time(self):
        from src.main import _parse_schedule_time
        import datetime
        msg = {"time": "daily 08:00"}
        now = utils.now_ts()
        result = _parse_schedule_time(msg, now)
        self.assertGreater(result, now)

    def test_parse_specific_time(self):
        from src.main import _parse_schedule_time
        import datetime
        # Aaj ka future time
        future = datetime.datetime.now() + datetime.timedelta(hours=2)
        time_str = f"{future.hour:02d}:{future.minute:02d}"
        msg = {"time": time_str}
        now = utils.now_ts()
        result = _parse_schedule_time(msg, now)
        self.assertGreater(result, now)

    def test_parse_past_time(self):
        from src.main import _parse_schedule_time
        # Aaj ka past time — skip hona chahiye
        past = datetime.datetime.now() - datetime.timedelta(hours=2)
        time_str = f"{past.hour:02d}:{past.minute:02d}"
        msg = {"time": time_str}
        now = utils.now_ts()
        result = _parse_schedule_time(msg, now)
        self.assertEqual(result, 0)  # past time — skip


if __name__ == "__main__":
    unittest.main()
