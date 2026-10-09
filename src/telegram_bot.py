"""Telegram admin panel bot — poora control Telegram se."""
from __future__ import annotations

import asyncio
import base64
import io

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from . import utils

# Yeh commands Telegram ke "/" menu mein load ho jayenge
COMMANDS = [
    BotCommand("start", "Bot status & welcome"),
    BotCommand("connect", "WhatsApp QR generate karein"),
    BotCommand("pair", "Phone number se pairing code login (QR alternative)"),
    BotCommand("status", "Poori connection status"),
    BotCommand("all", "Sabko broadcast message bhejein"),
    BotCommand("send", "Specific number pe message bhejein"),
    BotCommand("automation_add", "Naya automation rule banayein"),
    BotCommand("automation_list", "Saari automations dekhein"),
    BotCommand("automation_edit", "Automation edit karein"),
    BotCommand("automation_remove", "Automation delete karein"),
    BotCommand("automation_toggle", "Automation on/off karein"),
    BotCommand("automation_first", "First-time-only mode on/off"),
    BotCommand("blacklist_add", "Number blacklist karein"),
    BotCommand("blacklist_remove", "Number unblock karein"),
    BotCommand("blacklist_list", "Blacklist dekhein"),
    BotCommand("help", "Madad"),
]


class TelegramAdminBot:
    def __init__(self, config, storage, openwa, engine, bridge, openwa_service, logger=None):
        self.config = config
        self.storage = storage
        self.openwa = openwa
        self.engine = engine
        self.bridge = bridge
        self.openwa_service = openwa_service
        self.log = logger or utils.logger
        self.token = config["telegram_bot_token"]
        self.admin_chat_id = str(config["telegram_chat_id"])
        self.session_id: str = None
        self.stop_event = None
        self.start_event = None
        self.application: Application = None
        self.pending_broadcast: str = None

    # ---------------- helpers ----------------
    def _is_admin(self, update: Update) -> bool:
        chat_id = str(update.effective_chat.id)
        if chat_id != self.admin_chat_id:
            self.log.warning("Unauthorized access attempt — chat %s", chat_id)
            return False
        return True

    async def send_admin(self, text: str) -> None:
        try:
            await self.application.bot.send_message(
                chat_id=self.admin_chat_id, text=text, disable_web_page_preview=True
            )
        except Exception as e:
            self.log.error("Admin message failed: %s", e)

    # ---------------- QR flow ----------------
    async def send_qr(self) -> bool:
        try:
            qr, _status = self.openwa.get_qr(self.session_id)
        except Exception as e:
            self.log.error("QR fetch failed: %s", e)
            return False
        if not qr:
            return False
        try:
            png = base64.b64decode(qr.split(",", 1)[1])
        except Exception:
            self.log.error("QR decode failed")
            return False
        caption = (
            "📱 WhatsApp QR code\n\n"
            "Scan karein: WhatsApp → Settings → Linked Devices → Link a Device\n"
            "QR expire ho jayega to /connect dobara chalayein."
        )
        try:
            await self.application.bot.send_photo(
                chat_id=self.admin_chat_id,
                photo=InputFile(io.BytesIO(png), filename="whatsapp-qr.png"),
                caption=caption,
            )
            return True
        except Exception as e:
            self.log.error("QR send failed: %s", e)
            return False

    async def qr_watcher(self) -> None:
        """Background task: session status watch karke alerts bhejta hai."""
        last_status = None
        while not self.stop_event.is_set():
            try:
                session = self.openwa.get_session(self.session_id)
                status = session.get("status")
                if status != last_status:
                    if status == "ready":
                        await self.send_admin(
                            "✅ WhatsApp Connected!\n"
                            f"Number: {session.get('phone')}\n"
                            f"Name: {session.get('pushName')}"
                        )
                        self.storage.set_own_phone(utils.normalize_phone(session.get("phone")))
                    elif status == "qr_ready":
                        await self.send_qr()
                    elif status in ("disconnected", "failed", "action_required"):
                        await self.send_admin(
                            f"⚠️ WhatsApp status: {status}\n"
                            f"Error: {session.get('lastError')}\n\n"
                            "Dobara connect ke liye /connect chalayein."
                        )
                    last_status = status
            except Exception as e:
                self.log.debug("qr_watcher: %s", e)
            for _ in range(30):
                if self.stop_event.is_set():
                    break
                await asyncio.sleep(1)

    # ---------------- commands ----------------
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        try:
            s = self.openwa.get_session(self.session_id)
            wa = f"{s.get('status')} | Number: {s.get('phone') or '-'}"
        except Exception:
            wa = "OpenWA unreachable"
        text = (
            "🤖 WhatsApp Business Automation\n\n"
            f"WhatsApp: {wa}\n"
            f"Automations: {len(self.storage.list_automations())}\n"
            f"Blacklist: {len(self.storage.list_blacklist())} numbers\n\n"
            "Commands dekhne ke liye /help chalayein.\n"
            "WhatsApp connect ke liye /connect."
        )
        await update.message.reply_text(text)

    async def cmd_connect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not self.openwa_service.is_running():
            await update.message.reply_text(
                "🚀 OpenWA service start ho rahi hai... (pehli baar mein time lag sakta hai)"
            )
            self.openwa_service.start()
        if not self.openwa_service.wait_for_health(90):
            await update.message.reply_text(
                "❌ OpenWA service start nahi hui. Console aur data/openwa.log check karein."
            )
            return
        try:
            self.session_id = self.openwa.ensure_session()
        except Exception as e:
            await update.message.reply_text(f"❌ Session error: {e}")
            return
        try:
            session = self.openwa.get_session(self.session_id)
        except Exception as e:
            await update.message.reply_text(f"❌ Session read error: {e}")
            return
        if session.get("status") == "ready":
            await update.message.reply_text(
                f"✅ WhatsApp pehle se connected hai! Number: {session.get('phone')}"
            )
            return
        await update.message.reply_text("⏳ QR generate ho raha hai... WhatsApp pe scan karna hai.")
        try:
            self.openwa.start_session(self.session_id)
        except Exception as e:
            self.log.warning("start_session: %s (ignore agar QR aa gaya)", e)
        qr_sent = False
        for _ in range(45):
            qr, _status = self.openwa.get_qr(self.session_id)
            if qr:
                qr_sent = await self.send_qr()
                break
            await asyncio.sleep(2)
        if not qr_sent:
            await update.message.reply_text(
                "❌ QR nahi mila. /status chalake dekhein.\n"
                "QR ke bajaye /pair <number> se bhi connect kar sakte hain."
            )

    async def cmd_pair(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """QR ka alternative — phone number se pairing code login."""
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /pair <number>\n"
                "Example: /pair 919876543210\n\n"
                "Yeh QR ka alternative hai — phone number se 8-char code generate hoga "
                "jo WhatsApp mein enter karna hoga."
            )
            return
        phone = utils.normalize_phone(args[0])
        if not phone:
            await update.message.reply_text(
                "❌ Number valid nahi hai. Example: 919876543210"
            )
            return

        # Already connected?
        try:
            session = self.openwa.get_session(self.session_id)
            if session.get("status") == "ready":
                await update.message.reply_text(
                    f"✅ WhatsApp pehle se connected hai! Number: {session.get('phone')}"
                )
                return
        except Exception:
            pass

        # Session start karo (agar nahi hua)
        try:
            self.openwa.start_session(self.session_id)
        except Exception as e:
            self.log.warning("start_session: %s", e)

        await update.message.reply_text(
            "⏳ Pairing code generate ho raha hai... WhatsApp ready hone ka wait..."
        )

        # qr_ready hone ka wait karo, phir code request karo
        code = None
        for _ in range(30):
            try:
                session = self.openwa.get_session(self.session_id)
                status = session.get("status")
                if status == "ready":
                    await update.message.reply_text(
                        f"✅ WhatsApp already connected! Number: {session.get('phone')}"
                    )
                    return
                if status in ("qr_ready", "authenticating", "initializing"):
                    code = self.openwa.request_pairing_code(self.session_id, phone)
                    if code:
                        break
            except Exception as e:
                self.log.debug("pair attempt: %s", e)
            await asyncio.sleep(2)

        if not code:
            await update.message.reply_text(
                "❌ Pairing code generate nahi hua.\n"
                "Shayad session ready nahi hua. /status check karein, "
                "ya /connect se QR try karein."
            )
            return

        await update.message.reply_text(
            f"🔑 Pairing Code: {code}\n\n"
            f"Number: {phone}\n\n"
            "Is code ko WhatsApp mein enter karein:\n"
            "1. WhatsApp kholein\n"
            "2. Settings → Linked Devices → Link a Device\n"
            "3. 'Link with phone number instead' pe tap karein\n"
            f"4. Code enter karein: {code}\n\n"
            "⏰ Code 2 minute mein expire ho jayega.\n"
            "Connect hote hi main confirm kar dunga."
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        lines = ["📊 Status", ""]
        lines.append(
            f"OpenWA service: {'✅ running' if self.openwa_service.is_running() else '❌ stopped'}"
        )
        try:
            s = self.openwa.get_session(self.session_id)
            lines.append(
                f"WhatsApp: {s.get('status')} | Number: {s.get('phone') or '-'} | "
                f"Name: {s.get('pushName') or '-'}"
            )
        except Exception as e:
            lines.append(f"WhatsApp: ❌ {e}")
        autos = self.storage.list_automations()
        enabled = sum(1 for a in autos if a.get("enabled", True))
        lines.append(f"Automations: {enabled}/{len(autos)} active")
        lines.append(f"Blacklist: {len(self.storage.list_blacklist())} numbers")
        lines.append(
            f"Cooldown: {self.config.get('cooldown_seconds')}s | "
            f"Rate limit: {self.config.get('rate_limit_per_minute')}/min"
        )
        await update.message.reply_text("\n".join(lines))

    async def cmd_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /send <number> <message>\n"
                "Example: /send 919876543210 Hello! Aapka order ready hai."
            )
            return
        phone = utils.normalize_phone(args[0])
        if not phone:
            await update.message.reply_text("❌ Number valid nahi hai. Example: 919876543210")
            return
        if self.storage.is_blacklisted(phone):
            await update.message.reply_text(
                "⛔ Yeh number blacklist hai. Pehle /blacklist_remove karein."
            )
            return
        text = " ".join(args[1:])
        try:
            msg_id = self.openwa.send_text(
                self.session_id, utils.phone_to_chat_id(phone), text
            )
            self.storage.try_send_slot(self.config.get("rate_limit_per_minute", 20))
            await update.message.reply_text(f"✅ Message bhej diya gaya ({phone})\nID: {msg_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Send failed: {e}")

    async def cmd_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        text = " ".join(context.args or [])
        if not text:
            await update.message.reply_text(
                "Usage: /all <message>\nExample: /all Good morning! Aaj ki offer..."
            )
            return
        try:
            contacts = self.openwa.get_contacts(self.session_id)
        except Exception as e:
            await update.message.reply_text(
                f"❌ Contacts nahi mil sake: {e}\nWhatsApp connected hai? /status chalayein."
            )
            return
        n = len(contacts)
        if n == 0:
            await update.message.reply_text("❌ Koi contact nahi mila.")
            return
        self.pending_broadcast = text
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"✅ Confirm ({n} contacts)", callback_data="bc:confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="bc:cancel"),
                ]
            ]
        )
        await update.message.reply_text(
            f"⚠️ Broadcast confirm karein:\n\n{text}\n\n"
            f"{n} contacts ko yeh message jayega (rate limit ke saath, thoda time lagega).",
            reply_markup=keyboard,
        )

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not self._is_admin(update):
            return
        if query.data == "bc:confirm" and self.pending_broadcast:
            text = self.pending_broadcast
            self.pending_broadcast = None
            await query.edit_message_text("🚀 Broadcast shuru ho raha hai...")
            result = await self._run_broadcast(text)
            await query.edit_message_text(result)
        elif query.data == "bc:cancel":
            self.pending_broadcast = None
            await query.edit_message_text("❌ Broadcast cancel ho gaya.")

    async def _run_broadcast(self, text: str) -> str:
        try:
            contacts = self.openwa.get_contacts(self.session_id)
        except Exception as e:
            return f"❌ Contacts fetch failed: {e}"
        sent = failed = skipped = 0
        own = self.storage.get_own_phone()
        delay = self.config.get("broadcast_delay_seconds", 1.5)
        for i, c in enumerate(contacts):
            phone = utils.normalize_phone(c.get("number")) or utils.chat_id_to_phone(
                c.get("id")
            )
            if not phone or self.storage.is_blacklisted(phone) or (own and phone == own):
                skipped += 1
                continue
            if not self.storage.try_send_slot(self.config.get("rate_limit_per_minute", 20)):
                await asyncio.sleep(5)  # rate limit — thoda wait
            try:
                self.openwa.send_text(self.session_id, utils.phone_to_chat_id(phone), text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(delay)
            if (i + 1) % 10 == 0:
                try:
                    await self.send_admin(
                        f"⏳ Broadcast progress: {i + 1}/{len(contacts)} "
                        f"(sent {sent}, failed {failed}, skipped {skipped})"
                    )
                except Exception:
                    pass
        return (
            f"✅ Broadcast complete!\n\n"
            f"Sent: {sent}\nFailed: {failed}\nSkipped (blacklist/own): {skipped}"
        )

    # ---------------- automations ----------------
    @staticmethod
    def _parse_rule(text: str):
        """'trigger => reply' -> (trigger, reply, match_type)"""
        if "=>" not in text:
            return None
        trigger, reply = text.split("=>", 1)
        trigger = trigger.strip()
        reply = reply.strip()
        match_type = "contains"
        for prefix in ("exact:", "starts:", "regex:"):
            if trigger.lower().startswith(prefix):
                match_type = prefix.rstrip(":")
                trigger = trigger[len(prefix):].strip()
                break
        if not trigger or not reply:
            return None
        return trigger, reply, match_type

    async def cmd_automation_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        text = " ".join(context.args or [])
        parsed = self._parse_rule(text)
        if not parsed:
            await update.message.reply_text(
                "Usage: /automation_add <trigger> => <reply>\n\n"
                "Examples:\n"
                "  /automation_add price => Humara product best price pe hai...\n"
                "  /automation_add exact:hello => Welcome! Kya madad chahiye?\n"
                "  /automation_add starts:hi => Hi! Kaise hain aap?\n"
                "  /automation_add regex:price|cost => Rate list bhej raha hoon..."
            )
            return
        trigger, reply, match_type = parsed
        auto_id = self.storage.next_automation_id()
        auto = {
            "id": auto_id,
            "trigger": trigger,
            "reply": reply,
            "match": match_type,
            "enabled": True,
            "first_time_only": True,  # default: sirf pehle message pe reply
            "cooldown": None,
        }
        self.storage.add_automation(auto)
        warn = ""
        if len(trigger) <= 2 and match_type == "contains":
            warn = (
                "\n\n⚠️ Trigger bahut chhota hai — bahut saare messages match ho sakte hain. "
                "/automation_edit se badal sakte hain."
            )
        await update.message.reply_text(
            f"✅ Automation {auto_id} add ho gayi:\n\n"
            f"Trigger: {trigger!r} (match: {match_type})\n"
            f"Reply: {reply!r}\n"
            f"Mode: first-time-only (sirf pehle message pe reply)\n"
            f"Cooldown: {self.config.get('cooldown_seconds')}s per contact\n\n"
            f"List: /automation_list{warn}"
        )

    async def cmd_automation_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        autos = self.storage.list_automations()
        if not autos:
            await update.message.reply_text(
                "Koi automation nahi hai.\nAdd: /automation_add <trigger> => <reply>"
            )
            return
        lines = [f"📋 Automations ({len(autos)}):"]
        for a in autos:
            status = "🟢" if a.get("enabled", True) else "🔴"
            fto = " [first-time-only]" if a.get("first_time_only") else " [har match pe]"
            lines.append(
                f"{status} {a['id']}: {a.get('trigger')!r} ({a.get('match', 'contains')}){fto}\n"
                f"   → {a.get('reply', '')[:80]!r}"
            )
        await update.message.reply_text("\n\n".join(lines))

    async def cmd_automation_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /automation_edit <id> <trigger> => <reply>\n"
                "Example: /automation_edit a1 exact:price => New reply text"
            )
            return
        auto_id = args[0]
        parsed = self._parse_rule(" ".join(args[1:]))
        if not parsed:
            await update.message.reply_text("❌ Rule format galat. 'trigger => reply' likhein.")
            return
        trigger, reply, match_type = parsed
        if self.storage.update_automation(
            auto_id, {"trigger": trigger, "reply": reply, "match": match_type}
        ):
            await update.message.reply_text(
                f"✅ Automation {auto_id} update ho gayi:\n"
                f"Trigger: {trigger!r} ({match_type})\nReply: {reply!r}"
            )
        else:
            await update.message.reply_text(f"❌ {auto_id} nahi mili. /automation_list")

    async def cmd_automation_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: /automation_remove <id>")
            return
        auto_id = args[0]
        auto = self.storage.get_automation(auto_id)
        if not auto:
            await update.message.reply_text(f"❌ {auto_id} nahi mili.")
            return
        if self.storage.remove_automation(auto_id):
            await update.message.reply_text(
                f"🗑️ Automation {auto_id} delete ho gayi (trigger: {auto.get('trigger')!r})"
            )
        else:
            await update.message.reply_text("❌ Delete nahi hua.")

    async def cmd_automation_toggle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: /automation_toggle <id>")
            return
        auto_id = args[0]
        auto = self.storage.get_automation(auto_id)
        if not auto:
            await update.message.reply_text(f"❌ {auto_id} nahi mili.")
            return
        new_state = not auto.get("enabled", True)
        self.storage.update_automation(auto_id, {"enabled": new_state})
        await update.message.reply_text(
            f"{'🟢' if new_state else '🔴'} Automation {auto_id} "
            f"{'enabled' if new_state else 'disabled'}."
        )

    async def cmd_automation_first(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: /automation_first <id>")
            return
        auto_id = args[0]
        auto = self.storage.get_automation(auto_id)
        if not auto:
            await update.message.reply_text(f"❌ {auto_id} nahi mili.")
            return
        new_state = not auto.get("first_time_only", True)
        self.storage.update_automation(auto_id, {"first_time_only": new_state})
        mode = "first-time-only (sirf pehle message pe reply)" if new_state else "har matching message pe reply (cooldown ke saath)"
        await update.message.reply_text(f"🔁 Automation {auto_id} mode: {mode}")

    # ---------------- blacklist ----------------
    async def cmd_blacklist_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /blacklist_add <number>\nExample: /blacklist_add 919876543210"
            )
            return
        phone = utils.normalize_phone(args[0])
        if not phone:
            await update.message.reply_text("❌ Number valid nahi hai.")
            return
        if self.storage.add_blacklist(phone):
            await update.message.reply_text(
                f"⛔ {phone} blacklist ho gaya. Isko auto-reply aur broadcast messages nahi jayenge."
            )
        else:
            await update.message.reply_text(f"{phone} pehle se blacklist hai.")

    async def cmd_blacklist_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: /blacklist_remove <number>")
            return
        phone = utils.normalize_phone(args[0])
        if not phone:
            await update.message.reply_text("❌ Number valid nahi hai.")
            return
        if self.storage.remove_blacklist(phone):
            await update.message.reply_text(f"✅ {phone} unblock ho gaya.")
        else:
            await update.message.reply_text(f"{phone} blacklist mein nahi tha.")

    async def cmd_blacklist_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        bl = self.storage.list_blacklist()
        if not bl:
            await update.message.reply_text("Blacklist khaali hai.")
            return
        await update.message.reply_text("⛔ Blacklist:\n" + "\n".join(f"• {p}" for p in bl))

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        text = (
            "🤖 Admin Commands\n\n"
            "WhatsApp:\n"
            "  /connect — QR generate karke WhatsApp connect karein\n"
            "  /pair <number> — phone number se pairing code login (QR alternative)\n"
            "  /status — poori status\n\n"
            "Messaging:\n"
            "  /all <message> — sabko broadcast (confirmation ke saath)\n"
            "  /send <number> <message> — specific number pe bhejein\n\n"
            "Automations (WhatsApp pe message aaye to auto-reply):\n"
            "  /automation_add <trigger> => <reply>\n"
            "  /automation_list — saari rules\n"
            "  /automation_edit <id> <trigger> => <reply>\n"
            "  /automation_remove <id>\n"
            "  /automation_toggle <id> — on/off\n"
            "  /automation_first <id> — first-time-only mode on/off\n\n"
            "Blacklist:\n"
            "  /blacklist_add <number>\n"
            "  /blacklist_remove <number>\n"
            "  /blacklist_list\n\n"
            "Match types (trigger ke pehle lagayein):\n"
            "  exact:  — poora message exactly match\n"
            "  starts: — message trigger se shuru ho\n"
            "  regex:  — regular expression\n"
            "  (kuch na likhein — contains match)\n\n"
            "Safety: first-match-only reply, per-contact cooldown, rate limit, "
            "blacklist aur group-message skip (default)."
        )
        await update.message.reply_text(text)

    # ---------------- lifecycle ----------------
    async def start(self, session_id: str, stop_event, start_event) -> None:
        self.session_id = session_id
        self.stop_event = stop_event
        self.start_event = start_event
        # Longer HTTP timeout — slow networks pe 5s default timeout fail hota hai
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
        )
        self.application = Application.builder().token(self.token).request(request).build()

        app = self.application
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("connect", self.cmd_connect))
        app.add_handler(CommandHandler("pair", self.cmd_pair))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("all", self.cmd_all))
        app.add_handler(CommandHandler("send", self.cmd_send))
        app.add_handler(CommandHandler("automation_add", self.cmd_automation_add))
        app.add_handler(CommandHandler("automation_list", self.cmd_automation_list))
        app.add_handler(CommandHandler("automation_edit", self.cmd_automation_edit))
        app.add_handler(CommandHandler("automation_remove", self.cmd_automation_remove))
        app.add_handler(CommandHandler("automation_toggle", self.cmd_automation_toggle))
        app.add_handler(CommandHandler("automation_first", self.cmd_automation_first))
        app.add_handler(CommandHandler("blacklist_add", self.cmd_blacklist_add))
        app.add_handler(CommandHandler("blacklist_remove", self.cmd_blacklist_remove))
        app.add_handler(CommandHandler("blacklist_list", self.cmd_blacklist_list))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CallbackQueryHandler(self.on_callback))

        await app.initialize()
        await app.start()
        try:
            await app.bot.set_my_commands(COMMANDS)
        except Exception as e:
            self.log.error("set_my_commands failed: %s", e)

        self.bridge.set_loop(asyncio.get_running_loop())
        start_event.set()  # poller thread ab chal sakta hai

        await self.send_admin(
            "✅ Bot connected!\n\n"
            "WhatsApp connect karne ke liye /connect chalayein — QR Telegram pe bheja jayega."
        )
        asyncio.create_task(self.qr_watcher())

        await app.updater.start_polling()
        while not stop_event.is_set():
            await asyncio.sleep(1)

        # Pehle updater stop, phir app — warna "Updater is still running" error
        if app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
