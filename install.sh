#!/bin/sh
# ============================================================
#  WhatsApp Telegram Automation — One-line Installer
#  Windows / macOS / Linux / Termux supported
#
#  One-line install:
#  curl -sSL https://raw.githubusercontent.com/ykewat354-cyber/whatsapp-telegram-automation/main/install.sh | bash
# ============================================================
set -e

REPO_URL="https://github.com/ykewat354-cyber/whatsapp-telegram-automation.git"
OPENWA_URL="https://github.com/rmyndharis/OpenWA.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/whatsapp-telegram-automation}"

log()  { printf '\033[1;32m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[setup]\033[0m %s\n' "$*" >&2; }

# ---------------- platform detection ----------------
IS_TERMUX=0; IS_MAC=0; IS_LINUX=0; IS_WINDOWS=0
case "$PREFIX" in *com.termux*) IS_TERMUX=1 ;; esac
case "$(uname -s)" in
  Darwin)                 IS_MAC=1 ;;
  MINGW*|MSYS*|CYGWIN*)  IS_WINDOWS=1 ;;
  Linux)                  IS_LINUX=1 ;;
esac

log "WhatsApp Telegram Automation — Installer"
log "Platform: $(uname -s) | Termux: $IS_TERMUX | Windows: $IS_WINDOWS"

# ---------------- Python command detect ----------------
# Windows pe 'python3' nahi hota (sirf 'python'), baaki jagah 'python3'
PYTHON="python3"
command -v python3 >/dev/null 2>&1 || PYTHON="python"
log "Python command: $PYTHON ($($PYTHON --version 2>&1))"

# ---------------- package helpers ----------------
install_pkgs() {
  if [ "$IS_TERMUX" = 1 ]; then
    pkg install -y "$@"
  elif [ "$IS_MAC" = 1 ]; then
    # Homebrew mein 'python3' formula nahi hai — 'python' hai
    ARGS=""
    for pkg in "$@"; do
      [ "$pkg" = "python3" ] && pkg="python"
      ARGS="$ARGS $pkg"
    done
    brew install $ARGS
  elif [ "$IS_LINUX" = 1 ]; then
    sudo apt-get update -y && sudo apt-get install -y "$@"
  else
    err "Is platform pe automatic package install supported nahi hai."
    err "Yeh manually install karein: $*"
    exit 1
  fi
}

# ---------------- Step 1: system dependencies ----------------
log "Step 1/6: System dependencies check..."
MISSING=""
command -v git      >/dev/null 2>&1 || MISSING="$MISSING git"
command -v curl     >/dev/null 2>&1 || MISSING="$MISSING curl"
command -v "$PYTHON" >/dev/null 2>&1 || MISSING="$MISSING python3"
command -v node     >/dev/null 2>&1 || MISSING="$MISSING nodejs"
if [ -n "$MISSING" ]; then
  if [ "$IS_WINDOWS" = 1 ]; then
    err "Windows pe yeh tools manually install karein: $MISSING"
    err "  - Git Bash: https://git-scm.com/download/win"
    err "  - Python 3.10+: https://www.python.org/downloads/"
    err "  - Node.js 22+: https://nodejs.org/"
    err "Phir yeh installer dobara chalayein."
    exit 1
  fi
  install_pkgs $MISSING
fi

# pip (Linux distros mein alag package hota hai)
if ! command -v pip3 >/dev/null 2>&1 && [ "$IS_LINUX" = 1 ]; then
  sudo apt-get install -y python3-pip || true
fi

# Node.js >= 22 chahiye (OpenWA ke liye)
NODE_MAJOR="$(node -v 2>/dev/null | sed 's/^v//; s/\..*//')"
if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 22 ]; then
  warn "Node.js 22+ chahiye (OpenWA ke liye). Install ho raha hai..."
  if [ "$IS_TERMUX" = 1 ]; then
    pkg install -y nodejs
  elif [ "$IS_MAC" = 1 ]; then
    brew install node
  elif [ "$IS_LINUX" = 1 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
  fi
fi

# ---------------- Step 2: repository ----------------
log "Step 2/6: Repository clone ho rahi hai..."
if [ -d "$INSTALL_DIR/.git" ]; then
  log "Pehle se installed hai — update ho raha hai..."
  cd "$INSTALL_DIR" && git pull
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ---------------- Step 3: Python dependencies ----------------
log "Step 3/6: Python dependencies install..."
"$PYTHON" -m pip install -r requirements.txt >/dev/null 2>&1 \
  || "$PYTHON" -m pip install --break-system-packages -r requirements.txt \
  || "$PYTHON" -m pip install --user -r requirements.txt

# ---------------- Step 4: OpenWA gateway ----------------
log "Step 4/6: OpenWA (WhatsApp Gateway) setup..."
if [ ! -d "$INSTALL_DIR/openwa/.git" ]; then
  git clone --depth 1 "$OPENWA_URL" "$INSTALL_DIR/openwa"
fi
cd "$INSTALL_DIR/openwa"
if [ ! -d node_modules ]; then
  log "OpenWA dependencies install ho rahi hain (2-5 minute lag sakte hain)..."
  # Chromium auto-install — Termux pe pkg, desktop pe apt/brew
  CHROMIUM_BIN=""
  if command -v chromium-browser >/dev/null 2>&1; then
    CHROMIUM_BIN=$(command -v chromium-browser)
  elif command -v chromium >/dev/null 2>&1; then
    CHROMIUM_BIN=$(command -v chromium)
  fi
  if [ -z "$CHROMIUM_BIN" ]; then
    log "Chromium nahi mila — auto-install ho raha hai..."
    if [ "$IS_TERMUX" = 1 ]; then
      pkg install -y chromium >/dev/null 2>&1 || true
    elif [ "$IS_MAC" = 1 ]; then
      brew install --cask chromium >/dev/null 2>&1 || true
    elif [ "$IS_LINUX" = 1 ]; then
      sudo apt-get install -y chromium-browser >/dev/null 2>&1 || true
    fi
    # Install ke baad dobara check
    if command -v chromium-browser >/dev/null 2>&1; then
      CHROMIUM_BIN=$(command -v chromium-browser)
    elif command -v chromium >/dev/null 2>&1; then
      CHROMIUM_BIN=$(command -v chromium)
    fi
  fi
  if [ -n "$CHROMIUM_BIN" ]; then
    log "Chromium mil gaya: $CHROMIUM_BIN"
  else
    warn "Chromium auto-install fail — puppeteer default Chrome use hoga"
  fi
  if [ "$IS_TERMUX" = 1 ]; then
    PUPPETEER_SKIP_DOWNLOAD=true npm ci
  else
    npm ci
  fi
fi
if [ ! -f dist/main.js ]; then
  log "OpenWA build ho raha hai..."
  npm run build
fi

# ---------------- Step 5: OpenWA first boot (API key) ----------------
log "Step 5/6: OpenWA first boot — API key generate ho raha hai..."
cd "$INSTALL_DIR"
mkdir -p data
# Env template se .env banao (port + engine + chromium path)
CHROMIUM=$(command -v chromium-browser 2>/dev/null || command -v chromium 2>/dev/null || echo '')
if [ -n "$CHROMIUM" ]; then
  sed "s/__PORT__/2785/; s/__ENGINE__/whatsapp-web.js/; s|__CHROMIUM_PATH__|$CHROMIUM|" openwa.env.template > openwa/.env
else
  # Desktop/Codespaces — puppeteer default Chrome use hoga
  sed "s/__PORT__/2785/; s/__ENGINE__/whatsapp-web.js/; s|PUPPETEER_EXECUTABLE_PATH=__CHROMIUM_PATH__|# PUPPETEER_EXECUTABLE_PATH=puppeteer-default|" openwa.env.template > openwa/.env
fi
# Network security — OpenWA ko sirf localhost pe bind karo
# (LAN pe koi aur access na sake)
if command -v iptables >/dev/null 2>&1; then
  sudo iptables -A INPUT -p tcp --dport 2785 -s 127.0.0.1 -j ACCEPT 2>/dev/null || true
  sudo iptables -A INPUT -p tcp --dport 2785 -j DROP 2>/dev/null || true
  log "OpenWA port 2785 sirf localhost pe bind hai (iptables)"
else
  warn "iptables nahi mila — OpenWA port ko firewall se protect karein"
fi
cd "$INSTALL_DIR/openwa"
PORT=2785 node dist/main > "$INSTALL_DIR/data/openwa-firstboot.log" 2>&1 &
OPENWA_PID=$!
for i in $(seq 1 60); do
  [ -f "$INSTALL_DIR/openwa/data/.api-key" ] && break
  kill -0 "$OPENWA_PID" 2>/dev/null || break
  sleep 2
done
kill "$OPENWA_PID" 2>/dev/null || true
wait "$OPENWA_PID" 2>/dev/null || true
if [ -f "$INSTALL_DIR/openwa/data/.api-key" ]; then
  log "OpenWA API key generate ho gaya"
else
  warn "API key auto-generate nahi hua — config screen mein manual enter karenge."
fi

# ---------------- Step 6: configuration screen ----------------
log "Step 6/6: Configuration screen..."
cd "$INSTALL_DIR"
"$PYTHON" run.py --setup

log ""
log "==============================================="
log "  Installation complete!"
log ""
log "  Start karne ke liye:"
log "    cd $INSTALL_DIR"
log "    $PYTHON run.py"
log ""
log "  Phir Telegram bot pe /connect bhejein — QR milega!"
log "  (ya /pair <number> se pairing code login)"
log "==============================================="
