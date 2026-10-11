"""
database_inspector.py

Скрипт для анализа структуры удалённой базы данных.
Подключается к БД, получает список таблиц, столбцы, типы данных,
ключи и записывает всё в лог-файл.

Использование:
    python database_inspector.py          # разовый запуск
    python database_inspector.py --loop   # запуск каждые 15 минут
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text


# ──────────────────────────────────────────────
# Настройка путей и .env
# ──────────────────────────────────────────────

ENV_PATH = Path(r"C:\Users\Administrator\Documents\.env")

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=True)


def build_database_url():
    """Собирает строку подключения из отдельных переменных окружения."""

    db_type = os.getenv("DB_TYPE", "mysql").strip().lower()
    db_host = os.getenv("DB_HOST", "").strip()
    db_port = os.getenv("DB_PORT", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()

    if not db_host or not db_name:
        return ""

    # Экранируем специальные символы в пароле
    safe_pass = quote_plus(db_pass) if db_pass else ""

    if db_type == "sqlite":
        # Для SQLite db_name — это путь к файлу
        return f"sqlite:///{db_name}"

    elif db_type == "postgresql":
        port = db_port or "5432"
        return f"postgresql://{db_user}:{safe_pass}@{db_host}:{port}/{db_name}"

    else:
        # По умолчанию mysql
        port = db_port or "3306"
        return f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{port}/{db_name}"


DATABASE_URL = build_database_url()

# Папка для логов
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "db_structure.log"


# ──────────────────────────────────────────────
# Настройка логирования
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("database_inspector")


# ──────────────────────────────────────────────
# Основная логика анализа БД
# ──────────────────────────────────────────────

def inspect_database(database_url: str):
    """Подключается к БД и записывает структуру в лог."""

    if not database_url:
        logger.error("Не удалось собрать строку подключения. Проверь переменные DB_HOST, DB_NAME в .env.")
        return

    # Скрываем логин и пароль для вывода в лог
    safe_url = database_url
    if "@" in safe_url:
        safe_url = safe_url.split("@")[-1]

    logger.info("=" * 60)
    logger.info("НАЧАЛО АНАЛИЗА БАЗЫ ДАННЫХ")
    logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Подключение к: {safe_url}")
    logger.info("=" * 60)

    try:
        engine = create_engine(database_url)
        inspector = inspect(engine)

        # Получаем список таблиц
        tables = inspector.get_table_names()
        logger.info(f"Всего таблиц в БД: {len(tables)}")
        logger.info("-" * 60)

        for table_name in tables:
            logger.info(f"")
            logger.info(f"ТАБЛИЦА: {table_name}")
            logger.info("-" * 40)

            # Столбцы
            columns = inspector.get_columns(table_name)
            logger.info(f"  Столбцы ({len(columns)}):")
            for col in columns:
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                default = col.get("default")
                default_str = f", default={default}" if default is not None else ""
                logger.info(
                    f"    - {col['name']:<30} {str(col['type']):<20} {nullable}{default_str}"
                )

            # Первичные ключи
            pk = inspector.get_pk_constraint(table_name)
            if pk and pk.get("constrained_columns"):
                logger.info(f"  PRIMARY KEY: {', '.join(pk['constrained_columns'])}")

            # Внешние ключи
            fks = inspector.get_foreign_keys(table_name)
            if fks:
                logger.info(f"  FOREIGN KEYS:")
                for fk in fks:
                    local_cols = ", ".join(fk.get("constrained_columns", []))
                    referred_table = fk.get("referred_table", "?")
                    referred_cols = ", ".join(fk.get("referred_columns", []))
                    logger.info(
                        f"    - {local_cols} -> {referred_table}({referred_cols})"
                    )

            # Индексы
            indexes = inspector.get_indexes(table_name)
            if indexes:
                logger.info(f"  ИНДЕКСЫ:")
                for idx in indexes:
                    idx_name = idx.get("name", "unnamed")
                    idx_cols = ", ".join(idx.get("column_names", []))
                    unique = "UNIQUE" if idx.get("unique") else ""
                    logger.info(f"    - {idx_name} ({idx_cols}) {unique}")

            # Количество строк (примерное, через SELECT COUNT)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
                    row_count = result.scalar()
                    logger.info(f"  Количество записей: ~{row_count}")
            except Exception as e:
                logger.warning(f"  Не удалось получить количество записей: {e}")

        logger.info("")
        logger.info("=" * 60)
        logger.info("АНАЛИЗ БАЗЫ ДАННЫХ ЗАВЕРШЁН")
        logger.info(f"Лог сохранён: {LOG_FILE}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        logger.error("Проверь переменные DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME в .env")


# ──────────────────────────────────────────────
# Запуск
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if "--loop" in sys.argv:
        # Запуск каждые 15 минут
        import time

        INTERVAL_SECONDS = 15 * 60  # 15 минут

        logger.info(f"Запуск в режиме цикла. Интервал: {INTERVAL_SECONDS // 60} минут.")
        logger.info("Нажми Ctrl+C для остановки.")

        try:
            while True:
                inspect_database(DATABASE_URL)
                time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Остановка по команде пользователя.")
    else:
        # Разовый запуск
        inspect_database(DATABASE_URL)