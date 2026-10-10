# 🤖 WhatsApp Business Automation + Telegram Admin Panel

**Pure Python** business automation — WhatsApp pe message aaye to auto-reply,
aur **poora control Telegram bot se** (admin panel ki tarah).

WhatsApp ke liye [OpenWA](https://github.com/rmyndharis/OpenWA) open-source gateway
use hota hai — whatsapp-web.js engine + real Chromium browser se connect hota hai.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔌 **QR Connect** | `/connect` → QR Telegram pe bheja jata hai → WhatsApp scan karein |
| 🔑 **Pairing Code** | `/pair <number>` → 8-char code → WhatsApp mein enter karein |
| 💬 **Auto-reply Automation** | Trigger → Reply rules. Message aaye to automatic reply |
| 🛡️ **Anti-spam** | First-match-only, per-contact cooldown, first-time-only mode, rate limit |
| 📢 **Broadcast `/all`** | Pichhle 90 din active, non-archived 1-to-1 chats (saved/unsaved) — **confirmation ke saath** |
| 🎯 **Specific number `/send`** | Telegram se kisi bhi number pe direct message |
| 🚫 **Blacklist** | `/blacklist_add` / `/blacklist_remove` — unko koi message nahi jayega |
| 📋 **Automation Admin** | `/automation_add` / `edit` / `remove` / `toggle` — sab Telegram se |
| ⌨️ **Command Menu** | Bot mein `/` likhte hi saare commands load ho jate hain |
| 🔔 **Connected Alerts** | Bot connect → "✅ Bot connected", WhatsApp connect → "✅ WhatsApp Connected" |
| ⚡ **Lightning Fast** | Optimized Chromium — unnecessary features disabled, fast headless mode |
| 🖥️ **Cross-platform** | Windows · macOS · Linux · Termux — sab pe chalta hai |
| 📦 **One-line install** | Single command se kisi bhi device pe install |

---

## 🚀 One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/ykewat354-cyber/whatsapp-telegram-automation/main/install.sh | bash
```

Installer yeh sab karta hai:
1. System dependencies check/install (Python 3.10+, Node.js 22+, git, curl)
2. Repository clone
3. Python dependencies (`python-telegram-bot`, `requests`)
4. OpenWA clone + build (WhatsApp gateway)
5. **Browser setup** — Termux pe Chromium install, desktop pe Chrome download
6. OpenWA first boot → API key auto-generate
7. **Configuration screen** — Telegram Bot Token, Chat ID, engine, safety settings

### Windows pe
1. Install karein: [Git Bash](https://git-scm.com/download/win), [Python 3.10+](https://www.python.org/downloads/), [Node.js 22+](https://nodejs.org/)
2. Git Bash mein upar wala one-line command chalayein.

### Termux pe
```bash
pkg install -y git curl python nodejs
curl -sSL https://raw.githubusercontent.com/ykewat354-cyber/whatsapp-telegram-automation/main/install.sh | bash
```

> **Note:** Installer automatically detect karta hai ki aap Termux pe hain ya desktop pe.
> Termux pe Chromium install hota hai, desktop pe puppeteer ka Chrome download hota hai.
> Engine mein **whatsapp-web.js** choose karein — real browser connection WhatsApp ko
> reject nahi karta (baileys reject hota hai).

---

## 🎬 First Start

```bash
cd ~/whatsapp-telegram-automation
python3 run.py
```

1. Startup par Telegram admin ko **"✅ Bot connected"** message jayega
2. Telegram bot pe **`/connect`** bhejein (ya **`/pair <number>`** se pairing code login)
3. **QR code** Telegram pe milega → WhatsApp → Settings → Linked Devices → scan karein
   - **Pairing code method:** `/pair 919876543210` → code milega → WhatsApp mein enter karein
4. Connect hote hi **"✅ WhatsApp Connected!"** alert + auto-reply shuru!

---

## ⌨️ Telegram Commands

### WhatsApp
| Command | Kaam |
|---|---|
| `/connect` | QR generate karke WhatsApp connect karein |
| `/pair <number>` | Phone number se pairing code login |
| `/status` | Poori connection status |

### Messaging
| Command | Kaam |
|---|---|
| `/all <message>` | Pichhle 90 din active 1-to-1 chats (saved/unsaved; archived/groups excluded), confirmation ke saath |
| `/send <number> <message>` | Specific number pe message |

### Automations
| Command | Kaam |
|---|---|
| `/automation_add <trigger> => <reply>` | Naya rule banayein |
| `/automation_list` | Saari rules dekhein |
| `/automation_edit <id> <trigger> => <reply>` | Rule edit karein |
| `/automation_remove <id>` | Rule delete karein |
| `/automation_toggle <id>` | Rule on/off karein |
| `/automation_first <id>` | First-time-only mode on/off |

### Blacklist
| Command | Kaam |
|---|---|
| `/blacklist_add <number>` | Number block karein |
| `/blacklist_remove <number>` | Number unblock karein |
| `/blacklist_list` | Blacklist dekhein |

---

## 📖 Automation Guide

**Basic rule:**
```
/automation_add price => Humara product best price pe hai. Details ke liye call karein.
```

**Match types** (trigger ke pehle lagayein):
| Prefix | Matlab | Example |
|---|---|---|
| *(kuch nahi)* | contains (default) | `price` → "price" wale saare messages |
| `exact:` | poora message match | `exact:hello` → sirf "hello" |
| `starts:` | message shuru ho | `starts:hi` → "hi..." se shuru |
| `regex:` | regular expression | `regex:price\|c` → price ya cost |

---

## 🛡️ Safety Features

1. **First-match-only** — ek incoming message pe sirf ek auto-reply
2. **First-time-only mode** (default) — rule sirf pehle message pe fire
3. **Per-contact cooldown** — same person pe dobara reply gap ke baad hi
4. **Global cooldown** — rule chalane ka overall gap
5. **Rate limiter** — max N messages/minute (account safe rakhta hai)
6. **Broadcast confirmation** — `/all` pehle Confirm maangta hai; sirf pichhle 90 din mein active, non-archived 1-to-1 chats (saved/unsaved) include hote hain
7. **Blacklist** — blocked numbers ko koi message nahi (auto + broadcast)
8. **Group skip** — group messages pe auto-reply band (default)
9. **Own-number skip** — apne number pe reply nahi
10. **Admin-only** — sirf aapke Telegram chat ID se control

---

## ⚙️ Configuration

`data/config.json` (setup screen se banta hai):

```json
{
  "telegram_bot_token": "123456789:AA...",
  "telegram_chat_id": "123456789",
  "openwa_port": 2785,
  "openwa_api_key": "...",
  "openwa_session_name": "business-bot",
  "openwa_engine": "whatsapp-web.js",
  "poll_interval": 30,
  "cooldown_seconds": 300,
  "rate_limit_per_minute": 20,
  "allow_group_automation": false,
  "broadcast_delay_seconds": 1.0
}
```

Dobara configure karne ke liye: `python3 run.py --setup`

---

## 📁 Project Structure

```
whatsapp-telegram-automation/
├── install.sh                  # One-line installer
├── run.py                      # Entry point
├── requirements.txt
├── openwa.env.template         # OpenWA env template (Chromium optimized)
├── src/
│   ├── main.py                 # Bootstrap
│   ├── config.py               # Config + setup screen
│   ├── storage.py              # JSON storage (thread-safe)
│   ├── openwa_client.py        # OpenWA REST client + service manager
│   ├── automation_engine.py    # Rules + anti-spam + safety
│   ├── telegram_bot.py         # Telegram admin panel
│   └── utils.py                # Helpers
├── openwa/                     # OpenWA gateway (installer clone karta hai)
└── data/                       # Runtime data (config, state, logs)
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---|---|
| QR nahi mil raha | `/connect` dobara chalayein; `data/openwa.log` check karein |
| QR expire ho gaya | `/connect` dobara — naya QR milega |
| OpenWA start nahi ho raha | `data/openwa.log` dekhein; Node 22+ installed hai? |
| "Conflict" error | Purana bot instance chal raha hai — `pkill -f "python3 run.py"` |
| Send timeout | Normal hai — Chromium pe send slow hota hai (120s timeout set hai) |
| Commands nahi dikhe `/` mein | Bot restart karein — `setMyCommands` startup pe hota hai |
| Auto-reply nahi aa raha | `/status` se WhatsApp `ready` hai? `/automation_list` se rule enabled hai? |

### Linux pe Chrome dependencies

```bash
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
  libpango-1.0-0 libcairo2
```

### Docker (alternative deploy)

```bash
cd ~/whatsapp-telegram-automation/openwa
docker compose up -d
# API key: docker exec openwa-api cat /data/.api-key
```

---

## ⚠️ Disclaimer

Yeh system unofficial WhatsApp client (whatsapp-web.js) use karta hai.
WhatsApp ke hisaab se **automation pe account restrict/ban ka risk hamesha hota hai**.

- Hamesha ek **dedicated number** use karein (personal number nahi)
- Fresh number ko **warm up** karein (pehle din normal messages se)
- Cold-blast strangers ko **na** karein
- Official business ke liye Meta ke [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api) consider karein

Aapki zimmedari — use at your own risk.

---

## 📄 License

MIT — free for personal and commercial use.
