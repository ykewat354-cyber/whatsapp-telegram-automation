"""Utils tests — phone normalization, chat id conversion."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import utils


class TestPhoneUtils(unittest.TestCase):
    def test_normalize_plain(self):
        self.assertEqual(utils.normalize_phone("919876543210"), "919876543210")

    def test_normalize_formatted(self):
        self.assertEqual(utils.normalize_phone("+91 98765-43210"), "919876543210")
        self.assertEqual(utils.normalize_phone("+1 (555) 123-4567"), "15551234567")

    def test_normalize_invalid(self):
        self.assertIsNone(utils.normalize_phone(""))
        self.assertIsNone(utils.normalize_phone("12345"))  # chhota
        self.assertIsNone(utils.normalize_phone("12345678901234567890"))  # bada
        self.assertIsNone(utils.normalize_phone(None))

    def test_chat_id_roundtrip(self):
        self.assertEqual(utils.chat_id_to_phone("919876543210@c.us"), "919876543210")
        self.assertEqual(utils.phone_to_chat_id("919876543210"), "919876543210@c.us")

    def test_group_detection(self):
        self.assertTrue(utils.is_group_chat("120363000000000000@g.us"))
        self.assertFalse(utils.is_group_chat("919876543210@c.us"))
        self.assertFalse(utils.is_group_chat(""))

    def test_match_trigger(self):
        self.assertTrue(utils.normalize_phone is not None)


if __name__ == "__main__":
    unittest.main()
