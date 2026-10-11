"""
sync/player_logs_sync.py

Скачивает логи с FTP, разбивает их по игрокам (SteamID) и сохраняет
локально в папки logs_players/<steam_id>/<тип_лога>.log.

Синхронизация инкрементальная: запоминает, сколько строк каждого
исходного файла уже обработано (_sync_state.json), и дописывает
только новые записи. Вызывается каждые 15 минут.
"""

import ftplib
import json
import os
import re
import ssl
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs_players"
STATE_FILE = LOGS_DIR / "_sync_state.json"

# Типы логов для сбора
LOG_TYPES = [
    'player_alerts.log',
    'player_connections.log',
    'player_disconnections.log',
    'player_drop.log',
    'player_harvesting.log',
    'player_items.log',
    'player_kills.log',
]

# Подписи для отображения
LOG_LABELS = {
    'player_alerts.log': '🚨 Алерты (телепорты)',
    'player_connections.log': '🔌 Подключения',
    'player_disconnections.log': '🔌 Отключения',
    'player_drop.log': '🎁 Дроп предметов',
    'player_harvesting.log': '🦌 Добыча',
    'player_items.log': '📦 Контейнеры',
    'player_kills.log': '💀 Убийства и смерти',
}

# Начало новой записи лога: [2026-07-14 00:32:51] ...
ENTRY_START = re.compile(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]')
STEAM_RE = re.compile(r'SteamID:\s*(\d+)')


def _get_ftp_config():
    return {
        'host': os.getenv("FTP_HOST", "").strip(),
        'port': int(os.getenv("FTP_PORT", "21").strip() or "21"),
        'username': os.getenv("FTP_USERNAME", "").strip(),
        'password': os.getenv("FTP_PASSWORD", "").strip(),
        'remote_dir': os.getenv("FTP_REMOTE_DIR", "").strip(),
        'use_ssl': os.getenv("FTP_USE_SSL", "True").strip().lower() in ('true', '1', 'yes'),
        'verify_cert': os.getenv("ssl_verify_cert", "False").strip().lower() in ('true', '1', 'yes'),
    }


def _ftp_connect(cfg):
    if cfg['use_ssl']:
        ctx = ssl.create_default_context()
        if not cfg['verify_cert']:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ftp = ftplib.FTP_TLS(context=ctx)
    else:
        ftp = ftplib.FTP()

    ftp.connect(cfg['host'], cfg['port'], timeout=30)

    if cfg['username']:
        ftp.login(cfg['username'], cfg['password'])
    else:
        ftp.login()

    if cfg['use_ssl']:
        ftp.prot_p()

    return ftp


def _parse_list_line(line):
    line = line.rstrip()
    if not line:
        return None

    if line[0] in 'dl-bcps':
        parts = line.split(None, 8)
        if len(parts) >= 9:
            size = int(parts[4]) if parts[4].isdigit() else 0
            return {'name': parts[8], 'is_dir': parts[0].startswith('d'), 'size': size}
        return None

    parts = line.split(None, 3)
    if len(parts) >= 4:
        token3 = parts[2]
        name = parts[3]
        if token3.upper() == '<DIR>':
            return {'name': name, 'is_dir': True, 'size': 0}
        size = int(token3.replace(',', '')) if token3.replace(',', '').isdigit() else 0
        return {'name': name, 'is_dir': False, 'size': size}
    return None


def _list_remote(ftp, path):
    lines = []
    ftp.retrlines(f"LIST {path}", lines.append)
    items = []
    for line in lines:
        parsed = _parse_list_line(line)
        if not parsed or parsed['name'] in ('.', '..'):
            continue
        items.append(parsed)
    return items


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def _save_state(state):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _parse_entries(lines):
    """
    Разбивает строки лога на записи.
    Запись начинается с [дата время], продолжение — следующие строки.
    """
    entries = []
    current = None

    for line in lines:
        if ENTRY_START.match(line):
            if current:
                entries.append(current)
            m = STEAM_RE.search(line)
            current = {
                'steam': m.group(1) if m else None,
                'lines': [line],
            }
        elif current is not None:
            current['lines'].append(line)

    if current:
        entries.append(current)

    return entries


def _folder_sort_key(folder):
    try:
        return datetime.strptime(folder, "%d.%m.%Y")
    except Exception:
        return datetime.min


def sync_player_logs():
    """
    Скачивает новые записи логов с FTP и раскладывает их
    по папкам игроков logs_players/<steam_id>/.
    """
    cfg = _get_ftp_config()

    if not cfg['host']:
        return {'entries': 0, 'players': 0}

    ftp = _ftp_connect(cfg)
    base = cfg['remote_dir'].rstrip('/')

    state = _load_state()
    new_entries = 0
    touched_players = set()

    try:
        # Папки с датами
        folders = [i['name'] for i in _list_remote(ftp, base) if i['is_dir']]
        folders.sort(key=_folder_sort_key)

        for folder in folders:
            for log_type in LOG_TYPES:
                state_key = f"{folder}/{log_type}"
                remote_path = f"{base}/{folder}/{log_type}"

                # Читаем файл
                try:
                    lines = []
                    ftp.retrlines(f"RETR {remote_path}", lines.append)
                except Exception:
                    continue  # файла нет в этой папке

                # Инкрементально: только новые строки
                offset = state.get(state_key, 0)
                if len(lines) < offset:
                    offset = 0  # файл был обрезан/пересоздан
                new_lines = lines[offset:]
                state[state_key] = len(lines)

                if not new_lines:
                    continue

                # Разбиваем на записи и раскладываем по игрокам
                for entry in _parse_entries(new_lines):
                    if not entry['steam']:
                        continue  # "Неизвестный SteamID" — пропускаем

                    user_dir = LOGS_DIR / entry['steam']
                    user_dir.mkdir(parents=True, exist_ok=True)

                    with open(user_dir / log_type, 'a', encoding='utf-8') as f:
                        f.write('\n'.join(entry['lines']).rstrip('\n') + '\n')

                    new_entries += 1
                    touched_players.add(entry['steam'])
    finally:
        _save_state(state)
        try:
            ftp.quit()
        except Exception:
            pass

    return {'entries': new_entries, 'players': len(touched_players)}