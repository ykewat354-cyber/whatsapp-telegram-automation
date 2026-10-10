"""Chromium/Chrome detection and auto-install for all platforms."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess

from .utils import logger


def detect_chromium() -> str | None:
    """System pe installed Chromium/Chrome ka path dhundo."""
    system = platform.system()
    candidates = []
    if system == "Linux":
        candidates = [
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/snap/bin/chromium",
            "/data/data/com.termux/files/usr/bin/chromium-browser",
            "/data/data/com.termux/files/usr/bin/chromium",
        ]
    elif system == "Darwin":  # macOS
        candidates = [
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    elif system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", "")
        candidates = [
            os.path.join(local, "Chromium/Application/chrome.exe"),
            os.path.join(program_files, "Chromium/Application/chrome.exe"),
            os.path.join(program_files, "Google/Chrome/Application/chrome.exe"),
            os.path.join(program_files, "Google/Chrome/Application/chrome.exe"),
        ]
    # PATH mein bhi check karo
    for cmd in ["chromium-browser", "chromium", "google-chrome", "google-chrome-stable"]:
        path = shutil.which(cmd)
        if path:
            candidates.append(path)
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def install_chromium() -> str | None:
    """Chromium auto-install karo. Return installed path ya None."""
    system = platform.system()
    logger.info("Chromium nahi mila — auto-install shuru ho raha hai...")
    try:
        if system == "Linux":
            # Termux check
            if "com.termux" in os.environ.get("PREFIX", ""):
                subprocess.run(["pkg", "install", "-y", "chromium"],
                               check=True, timeout=300)
            else:
                # Debian/Ubuntu
                subprocess.run(["sudo", "apt-get", "update", "-y"],
                               check=True, timeout=120)
                subprocess.run(["sudo", "apt-get", "install", "-y", "chromium-browser"],
                               check=True, timeout=300)
        elif system == "Darwin":
            # macOS — Homebrew
            subprocess.run(["brew", "install", "--cask", "chromium"],
                           check=True, timeout=300)
        elif system == "Windows":
            # Windows — winget ya direct download
            try:
                subprocess.run(["winget", "install", "-e", "--id", "Chromium.Chromium"],
                               check=True, timeout=300)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("winget nahi mila — manual install zaroori hai")
                return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("Chromium install failed: %s", e)
        return None
    # Install ke baad dobara detect karo
    path = detect_chromium()
    if path:
        logger.info("Chromium install ho gaya: %s", path)
    else:
        logger.error("Chromium install ke baad bhi nahi mila")
    return path


def ensure_chromium() -> str | None:
    """Chromium ensure karo — ho to path do, na ho to install karo."""
    path = detect_chromium()
    if path:
        logger.info("Chromium mil gaya: %s", path)
        return path
    logger.info("Chromium nahi mila — install karta hoon...")
    return install_chromium()
