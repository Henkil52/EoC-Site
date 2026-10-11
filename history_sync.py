"""
history_sync.py

Копирует папку History с FTP-сервера в локальный каталог local_history/
(рядом с сервером) и обновляет её каждые 5 минут в фоновом потоке.
Скачиваются только новые и изменённые файлы (сравнение по размеру).
"""

import ftplib
import os
import ssl
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_HISTORY = PROJECT_ROOT / "local_history"

REMOTE_HISTORY_DEFAULT = "/MAIN/profiles/Kot_Mods/Kot_Message/History"

_thread = None
_lock = threading.Lock()


def _env(key, default=""):
    val = os.getenv(key)
    if val:
        return val
    from env_config import find_env_paths as _fep
    for p in (_fep() or [PROJECT_ROOT / '.env', PROJECT_ROOT.parent / '.env']):
        try:
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith(key + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return default


def remote_history_dir():
    return _env("HISTORY_REMOTE_DIR") or REMOTE_HISTORY_DEFAULT


def _connect():
    host = _env("FTP_HOST")
    port = int(_env("FTP_PORT", "21"))
    user = _env("FTP_USERNAME")
    password = _env("FTP_PASSWORD")
    use_ssl = _env("FTP_USE_SSL", "0").lower() in ("1", "true", "yes", "on")
    verify = _env("ssl_verify_cert", "0").lower() in ("1", "true", "yes", "on")

    if use_ssl:
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ftp = ftplib.FTP_TLS(context=ctx)
    else:
        ftp = ftplib.FTP()

    ftp.connect(host, port, timeout=30)
    ftp.login(user, password)
    if use_ssl:
        ftp.prot_p()
    ftp.sendcmd("TYPE I")
    return ftp


def _walk(ftp, remote_dir, rel="", depth=0):
    """Рекурсивно обходит папку FTP: (remote_path, rel_path, size)."""
    try:
        entries = ftp.nlst(remote_dir)
    except Exception:
        return
    for entry in entries:
        name = entry.rstrip("/").split("/")[-1]
        if name in (".", "..", ""):
            continue
        remote_path = remote_dir.rstrip("/") + "/" + name
        rel_path = rel + name
        try:
            size = ftp.size(remote_path)
        except Exception:
            size = None
        if size is None:
            # похоже на папку — заходим внутрь (ограничение глубины)
            if depth < 3:
                yield from _walk(ftp, remote_path, rel_path + "/", depth + 1)
        else:
            yield remote_path, rel_path, size


def sync_history(verbose=True):
    """Одна синхронизация: возвращает (скачано, пропущено)."""
    with _lock:
        ftp = _connect()
        try:
            LOCAL_HISTORY.mkdir(parents=True, exist_ok=True)
            downloaded = 0
            skipped = 0
            for remote_path, rel_path, size in _walk(ftp, remote_history_dir()):
                local = LOCAL_HISTORY / rel_path
                local.parent.mkdir(parents=True, exist_ok=True)

                if local.exists() and local.stat().st_size == size:
                    skipped += 1
                    continue

                tmp = local.with_suffix(local.suffix + ".tmp")
                with open(tmp, "wb") as f:
                    ftp.retrbinary("RETR " + remote_path, f.write)
                os.replace(tmp, local)
                downloaded += 1

            if verbose:
                print(f"[history_sync] скачано: {downloaded}, без изменений: {skipped}")
            return downloaded, skipped
        finally:
            try:
                ftp.quit()
            except Exception:
                pass


def start_history_scheduler(interval=300):
    """Фоновое обновление каждые interval секунд (по умолчанию 5 минут)."""
    global _thread
    if _thread is not None:
        return

    debug = _env("FLASK_DEBUG", "0").lower() in ("1", "true", "yes", "on")
    is_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if debug and not is_child:
        print("Пропуск запуска history-синхронизации (reloader process)")
        return

    def loop():
        while True:
            try:
                sync_history(verbose=False)
            except Exception as e:
                print(f"[history_sync] ошибка синхронизации: {e}")
            try:
                from main import app
                from achievements.service import process_history
                with app.app_context():
                    n = process_history()
                    if n:
                        print(f"[achievements] новых достижений: {n}")
            except Exception as e:
                print(f"[achievements] ошибка обработки: {e}")
            try:
                from main import app
                from playtime import take_playtime_snapshots
                with app.app_context():
                    take_playtime_snapshots()
            except Exception as e:
                print(f"[playtime] ошибка снапшотов: {e}")

            time.sleep(interval)

    _thread = threading.Thread(target=loop, daemon=True, name="history-sync")
    _thread.start()
    print(f"[history_sync] планировщик запущен (интервал {interval} сек)")
