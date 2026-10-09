"""OpenWA REST API client + local Node.js service manager."""
from __future__ import annotations

import os
import socket
import subprocess
import time

import requests

from . import utils


class OpenWAError(Exception):
    """OpenWA se related har error."""

    def __init__(self, message: str, status: int = None):
        super().__init__(message)
        self.status = status


class OpenWAClient:
    """OpenWA gateway (http://127.0.0.1:2785/api) ka synchronous client."""

    def __init__(self, port: int, api_key: str, session_name: str, logger=None):
        self.base_url = f"http://127.0.0.1:{port}/api"
        self.api_key = api_key
        self.session_name = session_name
        self.log = logger or utils.logger
        self.session_id: str = None

    def _request(self, method: str, path: str, ok=(200, 201), timeout=30, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-API-Key"] = self.api_key
        max_retries = 3
        for attempt in range(max_retries):
            try:
                r = requests.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    timeout=timeout,
                    **kwargs,
                )
            except requests.RequestException as e:
                raise OpenWAError(f"OpenWA service unreachable: {e}")
            if r.status_code == 429 and attempt < max_retries - 1:
                # Rate limited — thoda wait karke retry
                wait = 5 * (attempt + 1)
                self.log.warning(
                    "OpenWA rate limit (429) — %s mein retry (attempt %s/%s)",
                    wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            if r.status_code not in ok:
                raise OpenWAError(
                    f"OpenWA {method} {path} -> {r.status_code}: {r.text[:200]}",
                    status=r.status_code,
                )
            if r.content:
                try:
                    return r.json()
                except ValueError:
                    return {}
            return {}
        return {}

    # ---------------- sessions ----------------
    def list_sessions(self) -> list:
        return self._request("GET", "/sessions")

    def get_session(self, session_id: str) -> dict:
        return self._request("GET", f"/sessions/{session_id}")

    def create_session(self, name: str) -> dict:
        return self._request("POST", "/sessions", json={"name": name})

    def ensure_session(self) -> str:
        """Naam se session dhundo, na mile to naya bana do."""
        if self.session_id:
            return self.session_id
        for s in self.list_sessions():
            if s.get("name") == self.session_name:
                self.session_id = s["id"]
                break
        if not self.session_id:
            s = self.create_session(self.session_name)
            self.session_id = s["id"]
        self.log.info("OpenWA session: %s (%s)", self.session_id, self.session_name)
        return self.session_id

    def start_session(self, session_id: str) -> dict:
        return self._request("POST", f"/sessions/{session_id}/start")

    def get_qr(self, session_id: str):
        """Return (qr_data_url, status)."""
        data = self._request("GET", f"/sessions/{session_id}/qr")
        return data.get("qrCode"), data.get("status")

    def request_pairing_code(self, session_id: str, phone_number: str) -> str:
        """QR ke alternative — phone number se 8-char pairing code generate karo."""
        data = self._request(
            "POST",
            f"/sessions/{session_id}/pairing-code",
            ok=(201,),
            json={"phoneNumber": phone_number},
        )
        return data.get("pairingCode")

    # ---------------- messages ----------------
    def get_messages(self, session_id: str, direction: str = "incoming", limit: int = 50) -> list:
        data = self._request(
            "GET",
            f"/sessions/{session_id}/messages",
            params={"direction": direction, "limit": limit, "orderBy": "timestamp"},
        )
        return data.get("messages", [])

    def send_text(self, session_id: str, chat_id: str, text: str) -> str:
        data = self._request(
            "POST",
            f"/sessions/{session_id}/messages/send-text",
            json={"chatId": chat_id, "text": text},
            timeout=120,  # Chromium browser send slow ho sakta hai (Termux)
        )
        return data.get("messageId")

    def get_contacts(self, session_id: str) -> list:
        return self._request("GET", f"/sessions/{session_id}/contacts")


class OpenWAService:
    """OpenWA Node.js gateway ko local subprocess ki tarah manage karta hai."""

    def __init__(self, openwa_dir: str, port: int, logger=None):
        self.openwa_dir = openwa_dir
        self.port = port
        self.log = logger or utils.logger
        self.process: subprocess.Popen = None

    def is_built(self) -> bool:
        return os.path.exists(os.path.join(self.openwa_dir, "dist", "main.js"))

    def _port_open(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(("127.0.0.1", self.port)) == 0
        except OSError:
            return False

    def is_running(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        return self._port_open()

    def start(self) -> None:
        if self.is_running():
            self.log.info("OpenWA service pehle se running hai (port %s)", self.port)
            return
        env = dict(os.environ)
        env["PORT"] = str(self.port)
        env["NODE_ENV"] = "production"
        log_path = os.path.join(utils.DATA_DIR, "openwa.log")
        log_file = open(log_path, "ab")
        popen_kwargs = {}
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True
        self.process = subprocess.Popen(
            ["node", "dist/main"],
            cwd=self.openwa_dir,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        self.log.info("OpenWA service start ho gayi (pid %s)", self.process.pid)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.log.info("OpenWA service stop ho gayi")
        self.process = None

    def wait_for_health(self, timeout: int = 90) -> bool:
        """TCP port khulne ka wait karo."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._port_open():
                return True
            time.sleep(1)
        return False
