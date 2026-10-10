"""Automation rule engine — matching, anti-spam cooldowns aur safety guards."""
from __future__ import annotations

import re

from . import utils


class TooManyTargets(Exception):
    """Broadcast targets configured limit se zyada."""

    def __init__(self, count: int, limit: int):
        super().__init__(f"{count} chats mili, limit {limit} hai")
        self.count = count
        self.limit = limit


class AutomationEngine:
    """
    Har incoming WhatsApp message pe chalti hai.

    Safety model (accident se bachne ke liye):
    1. Sirf pehle matching automation fire hoti hai (first-match-only).
    2. first_time_only (default ON): rule sirf us contact ke PEHLE message pe
       fire hota hai — baar-baar messages pe nahi.
    3. Cooldown: har contact+rule ke beech minimum gap.
    4. Global cooldown: ek rule kitni baar bhi fire ho, gap zaroori.
    5. Rate limit: max N outgoing messages per minute.
    6. Blacklist, own-number aur group messages hamesha skip.
    """

    def __init__(self, storage, config, openwa, logger=None):
        self.storage = storage
        self.config = config
        self.openwa = openwa
        self.log = logger or utils.logger
        self.notify = None  # sync callable — admin Telegram par alert bhejne ke liye
        self._rate_limit_warned = False
        self._saved_cache = None
        self._saved_cache_ts = 0.0

    # ---------------- saved-contact guard ----------------
    def saved_numbers(self, force: bool = False) -> set:
        """Address-book mein saved numbers (cache 2 min). Fail hone par exception."""
        now = utils.now_ts()
        if not force and self._saved_cache is not None and now - self._saved_cache_ts < 120:
            return self._saved_cache
        contacts = self.openwa.get_contacts(self.openwa.session_id)
        if isinstance(contacts, dict):
            contacts = contacts.get("contacts", [])
        if not isinstance(contacts, list) or not contacts:
            raise RuntimeError("contact list empty/unavailable")
        saved = set()
        for c in contacts:
            phone = utils.normalize_phone(c.get("number")) or utils.chat_id_to_phone(c.get("id"))
            if not phone:
                continue
            # saved ya flag unknown => protected (safe side). Sirf clearly-unsaved allowed.
            if utils.contact_saved_flag(c) is not False:
                saved.add(phone)
        self._saved_cache = saved
        self._saved_cache_ts = now
        return saved

    def is_saved(self, phone: str) -> bool:
        """True = is number ko message NAHI jayega. Error aaye to bhi True (fail-closed)."""
        try:
            return phone in self.saved_numbers()
        except Exception as e:
            self.log.warning("Saved-contact check fail (%s) — safety ke liye skip: %s", e, phone)
            return True

    def active_chat_targets(
        self, max_recipients: int = None, active_days: int = 90
    ) -> list:
        """
        Broadcast targets = recent activity wali 1-to-1 chats, saved ya unsaved.
        Archived chats, groups/channels/status aur purani chats exclude hoti hain.
        """
        if active_days <= 0:
            raise ValueError("active_days must be greater than zero")
        cutoff = utils.now_ts() - active_days * 24 * 60 * 60
        own = self.storage.get_own_phone()
        chats = self.openwa.get_chats(self.openwa.session_id)
        out, seen = [], set()
        for c in chats:
            timestamp = c.get("timestamp") if isinstance(c, dict) else None
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, (int, float))
                or timestamp <= cutoff
            ):
                continue
            phone = utils.individual_chat_phone(c)
            if not phone or phone in seen:
                continue
            seen.add(phone)
            if self.storage.is_blacklisted(phone) or (own and phone == own):
                continue
            out.append(phone)
        if max_recipients and len(out) > max_recipients:
            raise TooManyTargets(len(out), max_recipients)
        return out

    # ---------------- matching ----------------
    @staticmethod
    def match_trigger(trigger: str, body: str, match_type: str = "contains") -> bool:
        if not trigger or not body:
            return False
        t = trigger.lower()
        b = body.lower()
        if match_type == "exact":
            return b.strip() == t.strip()
        if match_type == "starts":
            return b.strip().startswith(t.strip())
        if match_type == "regex":
            try:
                return bool(re.search(trigger, body, re.IGNORECASE))
            except re.error:
                return False
        return t in b  # contains (default)

    # ---------------- main entry ----------------
    def process_message(self, msg: dict) -> None:
        if msg.get("direction") != "incoming":
            return
        body = (msg.get("body") or "").strip()
        if not body:
            return
        chat_id = msg.get("chatId") or ""
        phone = utils.chat_id_to_phone(msg.get("from") or chat_id)
        if not phone:
            return

        # group messages — default mein skip (safety)
        if utils.is_group_chat(chat_id) and not self.config.get(
            "allow_group_automation"
        ):
            self.log.debug("Group message skip: %s", chat_id)
            return

        # blacklist
        if self.storage.is_blacklisted(phone):
            self.log.info("Blacklisted contact ka message ignore: %s", phone)
            return

        # apna khud ka number
        own = self.storage.get_own_phone()
        if own and phone == own:
            return

        # saved contacts (friends/family) ko kabhi auto-reply nahi
        if self.config.get("only_unsaved_contacts", True) and self.is_saved(phone):
            self.log.debug("Saved contact skip: %s", phone)
            return

        # first_time_only check (mark se PEHLE)
        was_seen = self.storage.is_contact_seen(phone)
        self.storage.mark_contact_seen(phone)

        for auto in self.storage.list_automations():
            if not auto.get("enabled", True):
                continue
            if not self.match_trigger(
                auto.get("trigger", ""), body, auto.get("match", "contains")
            ):
                continue
            if auto.get("first_time_only") and was_seen:
                self.log.debug("first_time_only skip: %s (%s)", auto["id"], phone)
                continue
            cooldown = self._cooldown_for(auto)
            last = self.storage.get_last_fired(auto["id"], phone)
            if last and (utils.now_ts() - last) < cooldown:
                self.log.debug("Cooldown skip: %s (%s)", auto["id"], phone)
                continue
            last_global = self.storage.get_last_fired(auto["id"], "*")
            if last_global and (utils.now_ts() - last_global) < cooldown:
                self.log.debug("Global cooldown skip: %s", auto["id"])
                continue
            self._fire(auto, phone)
            break  # ek message pe sirf EK reply — double reply kabhi nahi

    def _cooldown_for(self, auto: dict) -> int:
        cd = auto.get("cooldown")
        if cd is not None:
            return int(cd)
        return int(self.config.get("cooldown_seconds", 300))

    def _fire(self, auto: dict, phone: str) -> None:
        if not self.storage.try_send_slot(self.config.get("rate_limit_per_minute", 20)):
            if not self._rate_limit_warned:
                self._rate_limit_warned = True
                self.log.warning("Rate limit reached — send skip")
                if self.notify:
                    self.notify(
                        "⚠️ Rate limit reach hua — kuch auto-reply messages skip ho gayi.\n"
                        "Config: rate_limit_per_minute"
                    )
            return
        chat_id = utils.phone_to_chat_id(phone)
        try:
            self.openwa.send_text(self.openwa.session_id, chat_id, auto.get("reply", ""))
        except Exception as e:
            self.log.error("Automation send failed (%s): %s", auto["id"], e)
            return
        self.storage.set_last_fired(auto["id"], phone)
        self.storage.set_last_fired(auto["id"], "*")
        self._rate_limit_warned = False
        self.log.info(
            "Automation %s fire hua — contact %s (trigger=%r)",
            auto["id"],
            phone,
            auto.get("trigger"),
        )
