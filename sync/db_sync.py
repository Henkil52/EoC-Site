"""
sync/db_sync.py

Синхронизация удалённой БД (MySQL) в локальную (SQLite).
Использует SQLAlchemy модели для создания таблиц, затем копирует данные.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, inspect
from flask import Flask

try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False


# ──────────────────────────────────────────────
# Цветной форматтер
# ──────────────────────────────────────────────

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Fore.CYAN if HAS_COLORAMA else '',
        'INFO': Fore.GREEN if HAS_COLORAMA else '',
        'WARNING': Fore.BLUE if HAS_COLORAMA else '',
        'ERROR': Fore.RED if HAS_COLORAMA else '',
        'CRITICAL': (Back.RED + Fore.WHITE) if HAS_COLORAMA else '',
    }
    RESET = Style.RESET_ALL if HAS_COLORAMA else ''

    def format(self, record):
        orig_levelname = record.levelname
        if orig_levelname in self.COLORS:
            record.levelname = self.COLORS[orig_levelname] + orig_levelname + self.RESET
        result = super().format(record)
        record.levelname = orig_levelname
        return result


# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from env_config import load_env

load_env()

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "db_sync.log"

logger = logging.getLogger("db_sync")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ColoredFormatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(stream_handler)


LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"

SYNC_TABLES = [
    "players",
    "player_stats",
    "factions",
    "faction_ranks",
    "faction_members",
    "player_achievements",
    "pda_accounts",
]

# ──────────────────────────────────────────────
# Коррекция часового пояса для таблицы players
# ──────────────────────────────────────────────

def correct_players_timezone(local_engine):
    """
    Сдвигает все datetime-колонки таблицы players на -5 часов.
    Игровой сервер пишет время как UTC+5, нужно UTC+3 (Москва).
    Превращает 20:16 → 15:16.
    """
    from sqlalchemy import inspect as sa_inspect, text
    from sqlalchemy import DateTime as SADateTime

    inspector = sa_inspect(local_engine)

    if "players" not in inspector.get_table_names():
        return

    columns = inspector.get_columns("players")
    dt_cols = [c["name"] for c in columns if isinstance(c["type"], SADateTime)]

    if not dt_cols:
        return

    # Формируем SQL для сдвига
    set_clauses = ", ".join(
        f"{col} = datetime({col}, '-5 hours')" for col in dt_cols
    )
    sql = f"UPDATE players SET {set_clauses}"

    with local_engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    logger.info(f"Коррекция времени players: {len(dt_cols)} колонок сдвинуты на -5ч")



# ──────────────────────────────────────────────
# Подключения
# ──────────────────────────────────────────────

def get_remote_engine():
    db_type = os.getenv("DB_TYPE", "mysql").strip().lower()
    db_host = os.getenv("DB_HOST", "").strip()
    db_port = os.getenv("DB_PORT", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()

    if not db_host or not db_name:
        logger.error("DB_HOST или DB_NAME не заданы в .env")
        return None

    safe_pass = quote_plus(db_pass) if db_pass else ""
    port = db_port or "3306"

    if db_type == "postgresql":
        url = f"postgresql://{db_user}:{safe_pass}@{db_host}:{port}/{db_name}"
    else:
        url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{port}/{db_name}"

    # NullPool — подключение без пула: создаётся, используется,
    # СРАЗУ ЗАКРЫВАЕТСЯ. Решает проблему max_user_connections (5).
    from sqlalchemy.pool import NullPool
    return create_engine(
        url,
        poolclass=NullPool,
        pool_recycle=300,
        pool_pre_ping=True,
    )


def get_local_engine():
    # Удаляем пустой файл, если есть
    if LOCAL_DB_PATH.exists() and LOCAL_DB_PATH.stat().st_size == 0:
        LOCAL_DB_PATH.unlink()
    return create_engine(f"sqlite:///{LOCAL_DB_PATH}")


# ──────────────────────────────────────────────
# Создание таблиц через SQLAlchemy модели
# ──────────────────────────────────────────────

def ensure_tables_created(local_engine):
    """Создаёт таблицы в локальной БД через Flask-SQLAlchemy модели."""
    # Добавляем корень проекта в sys.path, чтобы импорт database.models работал
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from database.models import db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{LOCAL_DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    logger.info("Таблицы в локальной БД созданы/проверены.")


# ──────────────────────────────────────────────
# Основная логика синхронизации
# ──────────────────────────────────────────────

def sync_database():
    logger.info("=" * 60)
    logger.info("НАЧАЛО СИНХРОНИЗАЦИИ")
    logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    remote_engine = get_remote_engine()
    local_engine = get_local_engine()

    if not remote_engine:
        logger.error("Не удалось подключиться к удалённой БД.")
        return

    try:
        # Проверяем подключение
        with remote_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        logger.info("Подключение к удалённой БД: OK")

        # Создаём таблицы в локальной БД через модели
        ensure_tables_created(local_engine)

        # Читаем структуру удалённой БД
        remote_meta = MetaData()
        remote_meta.reflect(bind=remote_engine)

        for table_name in SYNC_TABLES:
            if table_name not in remote_meta.tables:
                logger.warning(f"Таблица '{table_name}' не найдена в удалённой БД. Пропуск.")
                continue

            remote_table = remote_meta.tables[table_name]

            # Проверяем, есть ли таблица в локальной БД
            local_meta = MetaData()
            local_meta.reflect(bind=local_engine)

            if table_name not in local_meta.tables:
                logger.warning(f"Таблица '{table_name}' не найдена в локальной БД. Пропуск.")
                continue

            local_table = local_meta.tables[table_name]

            # Читаем данные
            with remote_engine.connect() as remote_conn:
                result = remote_conn.execute(remote_table.select())
                rows = result.fetchall()
                columns = list(result.keys())

            logger.info(f"Таблица '{table_name}': получено {len(rows)} записей")

            # Записываем в локальную БД
            with local_engine.connect() as local_conn:
                local_conn.execute(local_table.delete())

                if rows:
                    data = [dict(zip(columns, row)) for row in rows]
                    # Дедупликация для таблиц с составными ключами
                    if table_name == 'player_achievements':
                        seen = set()
                        deduped = []
                        for row in data:
                            key = (row.get('SteamID'), row.get('AchievementID'))
                            if key not in seen:
                                seen.add(key)
                                deduped.append(row)
                        data = deduped
                        logger.info(f"  Дедупликация: {len(rows)} -> {len(data)} записей")
                    
                    local_conn.execute(local_table.insert(), data)

                local_conn.commit()

            logger.info(f"Таблица '{table_name}': записано {len(rows)} записей")


        # ── Синхронизация ролей в группировках ──────────────
        logger.info("Запуск синхронизации ролей в группировках...")
        try:
            from sync.faction_roles import sync_faction_roles
            sync_faction_roles()
        except Exception as e:
            logger.error(f"Ошибка синхронизации ролей группировок: {e}")
            logger.exception("Подробности:")

        # ── Синхронизация расширенной статистики с FTP ──────
        logger.info("Запуск синхронизации FTP-статистики игроков...")
        try:
            from sync.ftp_sync import sync_ftp_player_stats
            sync_ftp_player_stats()
        except Exception as e:
            logger.error(f"Ошибка синхронизации FTP-статистики: {e}")
            logger.exception("Подробности:")

        logger.info("СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        logger.exception("Подробности:")
        # ── Синхронизация логов игроков с FTP ───────────────
        logger.info("Запуск синхронизации логов игроков...")
        try:
            from sync.player_logs_sync import sync_player_logs
            logs_result = sync_player_logs()
            logger.info(
                f"Логи игроков: новых записей {logs_result['entries']}, "
                f"игроков {logs_result['players']}"
            )
        except Exception as e:
            logger.error(f"Ошибка синхронизации логов игроков: {e}")
            logger.exception("Подробности:")

    finally:
        # Гарантированное закрытие подключения к удалённой БД
        try:
            remote_engine.dispose()
            local_engine.dispose()
        except Exception:
            pass

# ──────────────────────────────────────────────
# Ручной запуск
# ──────────────────────────────────────────────

if __name__ == "__main__":
    sync_database()