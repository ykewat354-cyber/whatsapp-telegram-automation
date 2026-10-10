"""Saved-contact guard + active chat broadcast targets (groups/channels never)."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils
from src.automation_engine import AutomationEngine, TooManyTargets
from src.openwa_client import OpenWAClient
from src.storage import Storage


def make_msg(msg_id, body, phone):
    return {
        "id": msg_id,
        "chatId": f"{phone}@c.us",
        "from": f"{phone}@c.us",
        "body": body,
        "direction": "incoming",
        "timestamp": time.time(),
    }


class FakeOpenWA:
    def __init__(self):
        self.session_id = "sess-1"
        self.sent = []
        self.contacts = []
        self.chats = []
        self.contacts_error = False

    def get_contacts(self, session_id):
        if self.contacts_error:
            raise RuntimeError("down")
        return self.contacts

    def get_chats(self, session_id):
        return self.chats

    def send_text(self, session_id, chat_id, text):
        self.sent.append((chat_id, text))
        return "msg-x"


class GuardBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wta-test-")
        self.storage = Storage(data_dir=self.tmp)
        self.openwa = FakeOpenWA()
        self.config = {
            "cooldown_seconds": 300,
            "rate_limit_per_minute": 20,
            "allow_group_automation": False,
            "only_unsaved_contacts": True,
        }
        self.engine = AutomationEngine(self.storage, self.config, self.openwa)
        self.openwa.contacts = [
            {"id": "911111111111@c.us", "number": "911111111111", "isMyContact": True},
            {"id": "922222222222@c.us", "number": "922222222222", "isMyContact": False},
            {"id": "933333333333@c.us", "number": "933333333333"},  # flag unknown
        ]
        self.storage.add_automation({
            "id": "a1", "trigger": "hi", "reply": "Reply!", "match": "contains",
            "enabled": True, "first_time_only": False, "cooldown": None,
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class AutoReplyGuardTests(GuardBase):
    def test_saved_contact_gets_no_reply(self):
        self.engine.process_message(make_msg("m1", "hi", "911111111111"))
        self.assertEqual(self.openwa.sent, [])

    def test_unsaved_contact_gets_reply(self):
        self.engine.process_message(make_msg("m2", "hi", "922222222222"))
        self.assertEqual(len(self.openwa.sent), 1)

    def test_unknown_flag_is_protected(self):
        self.engine.process_message(make_msg("m3", "hi", "933333333333"))
        self.assertEqual(self.openwa.sent, [])

    def test_number_not_in_contact_list_is_unsaved(self):
        self.engine.process_message(make_msg("m4", "hi", "944444444444"))
        self.assertEqual(len(self.openwa.sent), 1)

    def test_contacts_error_fails_closed(self):
        self.openwa.contacts_error = True
        self.engine.process_message(make_msg("m5", "hi", "922222222222"))
        self.assertEqual(self.openwa.sent, [])


class BroadcastTargetTests(GuardBase):
    def setUp(self):
        super().setUp()
        recent = utils.now_ts() - 30 * 24 * 60 * 60
        self.openwa.chats = [
            {"id": "922222222222@c.us", "kind": "individual", "timestamp": recent},
            {"id": "911111111111@c.us", "kind": "individual", "timestamp": recent},
            {"id": "933333333333@c.us", "kind": "individual", "timestamp": recent},
            {"id": "120363000000@g.us", "kind": "group"},               # group -> skip
            {"id": "1203630000@newsletter", "kind": "channel"},         # channel -> skip
            {"id": "status@broadcast", "kind": "status"},               # status -> skip
            {"id": "955555555555@c.us", "kind": "group", "timestamp": recent},
            {"id": "966666666666@c.us", "kind": "individual", "timestamp": recent},
            {"id": "977777777777@c.us", "timestamp": recent},
            {"id": "922222222222@c.us", "kind": "individual", "timestamp": recent},
        ]
        self.storage.add_blacklist("966666666666")

    def test_only_active_individual_chats_saved_and_unsaved(self):
        self.assertEqual(
            self.engine.active_chat_targets(),
            ["922222222222", "911111111111", "933333333333", "977777777777"],
        )

    def test_own_number_skipped(self):
        self.storage.set_own_phone("977777777777")
        self.assertEqual(
            self.engine.active_chat_targets(),
            ["922222222222", "911111111111", "933333333333"],
        )

    def test_archived_chat_skipped(self):
        self.openwa.chats.append(
            {
                "id": "988888888888@c.us",
                "kind": "individual",
                "archived": True,
                "timestamp": utils.now_ts(),
            }
        )
        self.assertNotIn("988888888888", self.engine.active_chat_targets())

    def test_old_or_missing_activity_is_excluded(self):
        self.openwa.chats.extend([
            {
                "id": "988888888888@c.us",
                "kind": "individual",
                "timestamp": utils.now_ts() - 91 * 24 * 60 * 60,
            },
            {"id": "999999999999@c.us", "kind": "individual"},
        ])
        targets = self.engine.active_chat_targets()
        self.assertNotIn("988888888888", targets)
        self.assertNotIn("999999999999", targets)

    def test_cap_refuses_instead_of_truncating(self):
        with self.assertRaises(TooManyTargets):
            self.engine.active_chat_targets(max_recipients=1)

    def test_contacts_error_does_not_block_chat_broadcast(self):
        self.openwa.contacts_error = True
        self.assertEqual(
            self.engine.active_chat_targets(),
            ["922222222222", "911111111111", "933333333333", "977777777777"],
        )


class HelperTests(unittest.TestCase):
    def test_individual_chat_phone(self):
        f = utils.individual_chat_phone
        self.assertEqual(f({"id": "919876543210@c.us"}), "919876543210")
        self.assertEqual(f({"id": {"_serialized": "919876543210@c.us"}}), "919876543210")
        self.assertIsNone(f({"id": "1203@g.us"}))
        self.assertIsNone(f({"id": "919876543210@c.us", "isGroup": True}))
        self.assertIsNone(f({"id": "919876543210@lid"}))
        self.assertIsNone(f({"id": "919876543210@c.us", "archived": True}))
        self.assertIsNone(f(None))

    def test_contact_saved_flag(self):
        f = utils.contact_saved_flag
        self.assertIs(f({"isMyContact": True}), True)
        self.assertIs(f({"isMyContact": False}), False)
        self.assertIsNone(f({"name": "x"}))

    def test_as_list_shapes(self):
        a = OpenWAClient._as_list
        self.assertEqual(a([1]), [1])
        self.assertEqual(a({"chats": [2]}), [2])
        self.assertEqual(a({"data": [3]}), [3])
        self.assertEqual(a({}), [])


if __name__ == "__main__":
    unittest.main()
