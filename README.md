# 🤖 WhatsApp Business Automation + Telegram Admin Panel

**Pure Python** business automation system — WhatsApp pe message aaye to auto-reply,
aur **poora control Telegram bot se** (admin panel ki tarah).

WhatsApp ke liye [OpenWA](https://github.com/rmyndharis/OpenWA) open-source gateway use hota hai
(local service ki tarah chalta hai, Python usse REST API se baat karta hai).

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔌 **QR Connect** | Telegram pe `/connect` → QR Telegram pe bheja jata hai → WhatsApp scan karein |
| 🔑 **Pairing Code** | `/pair <number>` → 8-char code → WhatsApp mein enter karein (QR alternative) |
| 💬 **Auto-reply Automation** | Trigger → Reply rules. Message aaye to automatic reply |
| 🛡️ **Anti-spam (accident-proof)** | First-match-only reply, per-contact cooldown, first-time-only mode, rate limit |
| 📢 **Broadcast `/all`** | Sabko 1-time message (Good Morning etc.) — **confirmation ke saath** |
| 🎯 **Specific number `/send`** | Telegram se kisi bhi number pe direct message |
| 🚫 **Blacklist** | `/blacklist_add` / `/blacklist_remove` — unko koi message nahi jayega |
| 📋 **Automation Admin** | `/automation_add` / `edit` / `remove` / `toggle` — sab Telegram se |
| ⌨️ **Command Menu** | Bot mein `/` likhte hi saare commands load ho jate hain |
| 🔔 **Connected Alerts** | Bot connect → "✅ Bot connected", WhatsApp connect → "✅ WhatsApp Connected" |
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
5. OpenWA first boot → API key auto-generate
6. **Configuration screen** — Telegram Bot Token, Chat ID, engine, safety settings

### Windows pe
1. Install karein: [Git Bash](https://git-scm.com/download/win), [Python 3.10+](https://www.python.org/downloads/), [Node.js 22+](https://nodejs.org/)
2. Git Bash mein upar wala one-line command chalayein.

### Termux pe
```bash
pkg install -y git curl python nodejs
curl -sSL https://raw.githubusercontent.com/ykewat354-cyber/whatsapp-telegram-automation/main/install.sh | bash
```

> **Termux note:** Installer Termux pe automatically Chrome download skip karta hai
> (puppeteer Android support nahi karta). Config screen mein **baileys (option 2)**
> choose karein — lightweight hai (~80MB RAM) aur bina Chrome ke chalta hai.

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
4. Connect hote hi **"✅ WhatsApp Connected"** alert + auto-reply shuru!

---

## ⌨️ Telegram Commands

### WhatsApp
| Command | Kaam |
|---|---|
| `/connect` | QR generate karke WhatsApp connect karein |
| `/pair <number>` | Phone number se pairing code login (QR alternative) |
| `status` | Poori connection status |

### Messaging
| Command | Kaam |
|---|---|
| `/all <message>` | Sabko broadcast (Confirm/Cancel ke saath) |
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
> Customer: *"price kya hai?"* → Bot auto-reply: *"Humara product best price pe hai..."*

**Match types** (trigger ke pehle lagayein):
| Prefix | Matlab | Example |
|---|---|---|
| *(kuch nahi)* | contains (default) | `price` → "price" wale saare messages |
| `exact:` | poora message match | `exact:hello` → sirf "hello" |
| `starts:` | message shuru ho | `starts:hi` → "hi..." se shuru |
| `regex:` | regular expression | `regex:price\|c` → price ya cost |

**Anti-spam (default ON):**
- Har rule **sirf us contact ke pehle message pe** fire hota hai (first-time-only)
- Baar-baar messages pe reply **nahi** — cooldown (default 300s) + first-match-only
- Har message pe **sirf ek** reply (double reply kabhi nahi)
- Rate limit: default 20 messages/minute
- Group messages pe auto-reply **nahi** (default)

**First-time-only hata ke har message pe reply chahiye:**
```
/automation_first a1
```

---

## 🛡️ Safety Features (accident se bachav)

1. **First-match-only** — ek incoming message pe sirf ek auto-reply
2. **First-time-only mode** (default) — rule sirf pehle message pe fire
3. **Per-contact cooldown** — same person pe dobara reply gap ke baad hi
4. **Global cooldown** — rule chalane ka overall gap
5. **Rate limiter** — max N messages/minute (account safe rakhta hai)
6. **Broadcast confirmation** — `/all` pehle Confirm maangta hai
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
  "poll_interval": 5,
  "cooldown_seconds": 300,
  "rate_limit_per_minute": 20,
  "allow_group_automation": false,
  "broadcast_delay_seconds": 1.5
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
├── openwa.env.template         # OpenWA env template
├── src/
│   ├── main.py                 # Bootstrap (services jodta hai)
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
| Termux pe Chrome fail | Config screen mein **baileys** engine choose karein |
| API key nahi mila | `openwa/data/.api-key` file check karein, ya `python3 run.py --setup` |
| Commands nahi dikhe `/` mein | Bot restart karein — `setMyCommands` startup pe hota hai |
| Auto-reply nahi aa raha | `/status` se WhatsApp `ready` hai? `/automation_list` se rule enabled hai? |

### Linux pe Chrome dependencies (whatsapp-web.js engine)

Agar aap Linux server pe chalate hain aur whatsapp-web.js engine use karte hain, to Chrome ko
kuch system libraries chahiye hote hain. Agar ye missing hon to OpenWA start hone ke baad
QR nahi milega ya error aayega. Debian/Ubuntu pe:

```bash
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
  libpango-1.0-0 libcairo2
```

Termux pe yeh zaroori nahi — baileys engine bina Chrome ke chalta hai.

### Docker (alternative deploy)

Agar aap Docker use karna chahte hain, to OpenWA khud Docker-native hai:

```bash
cd ~/whatsapp-telegram-automation/openwa
docker compose up -d
# API key: docker exec openwa-api cat /data/.api-key
```

Docker mein Puppeteer Chrome pehle se configured hai, isliye whatsapp-web.js engine
bina kisi extra setup ke kaam karega.

---

## ⚠️ Disclaimer

Yeh system unofficial WhatsApp clients (whatsapp-web.js / baileys) use karta hai.
WhatsApp ke hisaab se **automation pe account restrict/ban ka risk hamesha hota hai**.

- Hamesha ek **dedicated number** use karein (personal number nahi)
- Fresh number ko **warm up** karein (pehle din normal messages se)
- Cold-blast strangers ko **na** karein
- Official business ke liye Meta ke [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api) consider karein

Aapki zimmedari — use at your own risk.

---

## 📄 License

MIT — free for personal and commercial use.
