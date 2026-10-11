"""
steam_utils.py

Получение аватарки из Steam Web API (ISteamUser/GetPlayerSummaries).
Результат кэшируется в памяти процесса.

Использование:
    from steam_utils import fetch_steam_avatar
    url = fetch_steam_avatar(steam_id)
"""

import os
import threading
from pathlib import Path

import requests

_cache = {}
_lock = threading.Lock()

ENV_PATHS = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path("/opt/env"),                               # Ubuntu: файл /opt/env
    Path("/opt/env/.env"),                          # Ubuntu: каталог /opt/env с .env
]


def _env(key):
    """Читает переменную из os.environ или из .env."""
    val = os.getenv(key)
    if val:
        return val
    for p in ENV_PATHS:
        try:
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith(key + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def fetch_steam_avatar(steam_id, timeout=5):
    """Возвращает URL аватарки Steam или None."""
    if not steam_id:
        return None

    with _lock:
        if steam_id in _cache:
            return _cache[steam_id]

    key = _env("STEAM_API_KEY")
    result = None

    if key:
        try:
            r = requests.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                params={"key": key, "steamids": steam_id},
                timeout=timeout,
            )
            players = (r.json() or {}).get("response", {}).get("players", [])
            if players:
                p = players[0]
                result = p.get("avatarfull") or p.get("avatarmedium") or p.get("avatar")
        except Exception:
            result = None

    with _lock:
        _cache[steam_id] = result
    return result
