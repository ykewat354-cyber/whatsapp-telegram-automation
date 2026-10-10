"""Thread-safe JSON storage: automations, blacklist aur runtime state."""
from __future__ import annotations

import json
import os
import threading
import time

from . import utils

MAX_PROCESSED_IDS = 1000


class Storage:
    """Saara data data/ folder ke JSON files mein, memory + disk sync ke saath."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or utils.DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._automations = self._read("automations.json", {"automations": []})
        self._blacklist = self._read("blacklist.json", {"blacklist": []})
        self._state = self._read("state.json", {})

    # ---------- low-level helpers ----------
    def _path(self, name: str) -> str:
        return os.path.join(self.data_dir, name)

    def _read(self, name: str, default):
        try:
            with open(self._path(name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return default

    def _write(self, name: str, data) -> None:
        tmp = self._path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path(name))

    # ---------- automations ----------
    def list_automations(self) -> list:
        with self._lock:
            return list(self._automations["automations"])

    def get_automation(self, auto_id: str):
        with self._lock:
            for a in self._automations["automations"]:
                if a["id"] == auto_id:
                    return dict(a)
        return None

    def next_automation_id(self) -> str:
        with self._lock:
            nums = [
                int(a["id"][1:])
                for a in self._automations["automations"]
                if a["id"].startswith("a") and a["id"][1:].isdigit()
            ]
            return f"a{max(nums) + 1 if nums else 1}"

    def add_automation(self, auto: dict) -> None:
        with self._lock:
            self._automations["automations"].append(auto)
            self._write("automations.json", self._automations)

    def update_automation(self, auto_id: str, fields: dict) -> bool:
        with self._lock:
            for a in self._automations["automations"]:
                if a["id"] == auto_id:
                    a.update(fields)
                    self._write("automations.json", self._automations)
                    return True
            return False

    def remove_automation(self, auto_id: str) -> bool:
        with self._lock:
            before = len(self._automations["automations"])
            self._automations["automations"] = [
                a for a in self._automations["automations"] if a["id"] != auto_id
            ]
            if len(self._automations["automations"]) < before:
                self._write("automations.json", self._automations)
                return True
            return False

    # ---------- blacklist ----------
    def list_blacklist(self) -> list:
        with self._lock:
            return list(self._blacklist["blacklist"])

    def is_blacklisted(self, phone: str) -> bool:
        with self._lock:
            return phone in self._blacklist["blacklist"]

    def add_blacklist(self, phone: str) -> bool:
        with self._lock:
            if phone in self._blacklist["blacklist"]:
                return False
            self._blacklist["blacklist"].append(phone)
            self._write("blacklist.json", self._blacklist)
            return True

    def remove_blacklist(self, phone: str) -> bool:
        with self._lock:
            if phone not in self._blacklist["blacklist"]:
                return False
            self._blacklist["blacklist"].remove(phone)
            self._write("blacklist.json", self._blacklist)
            return True

    # ---------- runtime state ----------
    def is_message_processed(self, msg_id: str) -> bool:
        with self._lock:
            return msg_id in self._state.get("processed_message_ids", [])

    def mark_message_processed(self, msg_id: str) -> None:
        with self._lock:
            ids = self._state.setdefault("processed_message_ids", [])
            if msg_id not in ids:
                ids.append(msg_id)
            if len(ids) > MAX_PROCESSED_IDS:
                ids[:] = ids[-MAX_PROCESSED_IDS:]
            self._write("state.json", self._state)

    def is_contact_seen(self, phone: str) -> bool:
        with self._lock:
            return phone in self._state.get("contact_seen", {})

    def get_contact_last_seen(self, phone: str) -> float:
        """Contact ka last message timestamp (0 agar kabhi nahi aaya)."""
        with self._lock:
            return self._state.get("contact_seen", {}).get(phone, 0)

    def mark_contact_seen(self, phone: str) -> None:
        with self._lock:
            self._state.setdefault("contact_seen", {})[phone] = time.time()
            self._write("state.json", self._state)

    def get_last_fired(self, auto_id: str, phone: str) -> float:
        with self._lock:
            return self._state.get("automation_last_fired", {}).get(
                f"{auto_id}:{phone}", 0
            )

    def set_last_fired(self, auto_id: str, phone: str, ts: float = None) -> None:
        with self._lock:
            self._state.setdefault("automation_last_fired", {})[
                f"{auto_id}:{phone}"
            ] = ts or time.time()
            self._write("state.json", self._state)

    def get_own_phone(self) -> "str | None":
        with self._lock:
            return self._state.get("own_phone")

    def set_own_phone(self, phone: str) -> None:
        with self._lock:
            self._state["own_phone"] = phone
            self._write("state.json", self._state)

    # ---------- rate limiter (atomic check + record) ----------
    def try_send_slot(self, max_per_minute: int) -> bool:
        """Agar is minute mein limit se kam messages bheje hain to slot do."""
        with self._lock:
            now = time.time()
            stamps = [
                t for t in self._state.get("send_timestamps", []) if now - t < 60
            ]
            if len(stamps) >= max_per_minute:
                self._state["send_timestamps"] = stamps
                self._write("state.json", self._state)
                return False
            stamps.append(now)
            self._state["send_timestamps"] = stamps
            self._write("state.json", self._state)
            return True

    # ---------- scheduled messages ----------
    def list_scheduled(self) -> list:
        with self._lock:
            return list(self._read("scheduled_messages.json", {"messages": []})["messages"])

    def add_scheduled(self, msg: dict) -> None:
        with self._lock:
            data = self._read("scheduled_messages.json", {"messages": []})
            data["messages"].append(msg)
            self._write("scheduled_messages.json", data)

    def remove_scheduled(self, msg_id: str) -> bool:
        with self._lock:
            data = self._read("scheduled_messages.json", {"messages": []})
            before = len(data["messages"])
            data["messages"] = [m for m in data["messages"] if m["id"] != msg_id]
            if len(data["messages"]) < before:
                self._write("scheduled_messages.json", data)
                return True
            return False

    def next_scheduled_id(self) -> str:
        with self._lock:
            data = self._read("scheduled_messages.json", {"messages": []})
            nums = [
                int(m["id"][1:])
                for m in data["messages"]
                if m["id"].startswith("s") and m["id"][1:].isdigit()
            ]
            return f"s{max(nums) + 1 if nums else 1}"

    def mark_scheduled_sent(self, msg_id: str) -> bool:
        """One-time message ko 'sent' mark karo."""
        with self._lock:
            data = self._read("scheduled_messages.json", {"messages": []})
            for m in data["messages"]:
                if m["id"] == msg_id:
                    m["status"] = "sent"
                    m["sent_at"] = time.time()
                    self._write("scheduled_messages.json", data)
                    return True
            return False
