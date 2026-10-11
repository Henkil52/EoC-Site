"""
admin/env_editor.py

Логика работы с файлом .env:
- чтение
- запись
- создание бэкапов
- логирование изменений
"""

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from env_config import find_env_path

# Ищем .env автоматически. Если не найден — будем создавать рядом с проектом.
ENV_PATH = find_env_path() or (PROJECT_ROOT / ".env")
BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups" / "env"
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "env_changes.log"

# Переменные, значения которых маскируются при отображении
SENSITIVE_KEYS = {
    'SECRET_KEY',
    'STEAM_API_KEY',
    'DB_PASS',
    'DATABASE_URL',
    'PASSWORD',
    'TOKEN',
}

# Настройка логирования изменений .env
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

env_logger = logging.getLogger("env_changes")
env_logger.setLevel(logging.INFO)
env_logger.propagate = False

if not env_logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s")
    )
    env_logger.addHandler(handler)


def parse_env_file(path: Path) -> list[dict]:
    """
    Читает .env файл и возвращает список записей.

    Формат записи:
    {
        'key': 'VAR_NAME',
        'value': 'значение',
        'line_number': 5,
        'is_comment': False,
        'raw_line': 'VAR_NAME=значение',
    }
    """
    entries = []

    if not path.exists():
        return entries

    with open(path, 'r', encoding='utf-8') as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip('\n\r')

            # Пустая строка
            if not line.strip():
                entries.append({
                    'key': None,
                    'value': None,
                    'line_number': line_number,
                    'is_comment': False,
                    'is_empty': True,
                    'raw_line': line,
                })
                continue

            # Комментарий
            if line.strip().startswith('#'):
                entries.append({
                    'key': None,
                    'value': None,
                    'line_number': line_number,
                    'is_comment': True,
                    'is_empty': False,
                    'raw_line': line,
                })
                continue

            # Переменная KEY=VALUE
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()

                # Убираем кавычки
                if (value.startswith('"') and value.endswith('"')) or \
                        (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

                entries.append({
                    'key': key,
                    'value': value,
                    'line_number': line_number,
                    'is_comment': False,
                    'is_empty': False,
                    'is_sensitive': is_sensitive(key),
                    'raw_line': line,
                })
            else:
                # Неизвестная строка — сохраняем как комментарий
                entries.append({
                    'key': None,
                    'value': None,
                    'line_number': line_number,
                    'is_comment': True,
                    'is_empty': False,
                    'raw_line': line,
                })

    return entries


def is_sensitive(key: str) -> bool:
    """Проверяет, является ли ключ чувствительным."""
    if not key:
        return False
    key_upper = key.upper()
    return key_upper in SENSITIVE_KEYS or \
        any(s in key_upper for s in ['PASS', 'SECRET', 'TOKEN', 'KEY', 'API'])


def mask_value(key: str, value: str) -> str:
    """Маскирует значение чувствительных полей."""
    if not is_sensitive(key):
        return value
    if not value:
        return ""
    # Показываем только первые 4 и последние 2 символа
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * (len(value) - 6)}{value[-2:]}"


def create_backup() -> Path | None:
    """Создаёт бэкап текущего .env файла."""
    if not ENV_PATH.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f".env.backup_{timestamp}"

    shutil.copy2(ENV_PATH, backup_path)
    return backup_path


def save_env_file(entries: list[dict]) -> None:
    """Сохраняет записи обратно в .env файл."""
    lines = []

    for entry in entries:
        if entry.get('is_empty'):
            lines.append("")
            continue

        if entry.get('is_comment'):
            lines.append(entry['raw_line'])
            continue

        key = entry.get('key')
        value = entry.get('value', '')

        if not key:
            continue

        # Оборачиваем в кавычки, если есть пробелы или спецсимволы
        if ' ' in value or any(c in value for c in ['"', "'", '#', '\n']):
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f'{key}={value}')

    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n')


def log_change(changed_by: str, action: str, key: str, old_value: str, new_value: str):
    """Записывает изменение в лог."""
    sensitive = is_sensitive(key)

    if sensitive:
        old_display = "***" if old_value else ""
        new_display = "***" if new_value else ""
    else:
        old_display = old_value or "(пусто)"
        new_display = new_value or "(пусто)"

    env_logger.info(
        f"USER: {changed_by} | ACTION: {action} | KEY: {key} | "
        f"OLD: {old_display} | NEW: {new_display}"
    )


def get_backups() -> list[dict]:
    """Возвращает список бэкапов с датой."""
    backups = []

    if not BACKUPS_DIR.exists():
        return backups

    for path in sorted(BACKUPS_DIR.glob(".env.backup_*"), reverse=True):
        stat = path.stat()
        backups.append({
            'path': path,
            'filename': path.name,
            'created_at': datetime.fromtimestamp(stat.st_mtime),
            'size': stat.st_size,
        })

    return backups


def restore_backup(filename: str) -> bool:
    """Восстанавливает .env из бэкапа."""
    backup_path = BACKUPS_DIR / filename
    if not backup_path.exists():
        return False

    # Создаём бэкап текущего файла перед восстановлением
    create_backup()

    shutil.copy2(backup_path, ENV_PATH)
    return True