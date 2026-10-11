"""
env_config.py

Поиск и загрузка файла .env из нескольких возможных мест.
Если найдено НЕСКОЛЬКО .env файлов — все они загружаются (объединяются),
приоритет у файла в папке проекта.
"""

from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


def find_env_paths():
    """
    Возвращает список существующих .env файлов
    в порядке приоритета (первый — самый приоритетный).
    """
    candidates = [
        PROJECT_ROOT / ".env",                          # рядом с проектом
        Path.home() / "Documents" / ".env",             # Documents текущего пользователя
        Path.home() / ".env",                           # домашняя папка
        Path(r"C:\Users\Администратор\Documents\.env"),  # кириллица
        Path(r"C:\Users\Administrator\Documents\.env"),  # латиница
        Path("/opt/env"),                               # Ubuntu: файл /opt/env
        Path("/opt/env/.env"),                          # Ubuntu: каталог /opt/env с .env
    ]

    found = []
    for candidate in candidates:
        try:
            if candidate.exists() and candidate not in found:
                found.append(candidate)
        except OSError:
            continue

    return found


def find_env_path():
    """Возвращает самый приоритетный .env или None."""
    paths = find_env_paths()
    return paths[0] if paths else None


def load_env():
    """
    Загружает ВСЕ найденные .env файлы (объединяет переменные).
    Загрузка идёт от менее приоритетных к более приоритетным,
    чтобы файл проекта перекрывал остальные.
    Возвращает самый приоритетный путь (или None).
    """
    found = find_env_paths()

    if not found:
        load_dotenv(override=True)
        return None

    # Загружаем в обратном порядке (низкий приоритет → высокий)
    for path in reversed(found):
        load_dotenv(dotenv_path=path, override=True)

    return found[0]
