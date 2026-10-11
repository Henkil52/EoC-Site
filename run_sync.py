"""
run_sync.py

Синхронизация данных из MySQL в SQLite.
Создаёт таблицы в SQLite через SQLAlchemy модели, затем копирует данные.
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, text, inspect

# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = Path(r"C:\Users\Administrator\Documents\.env")
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
# Загрузка .env
# ──────────────────────────────────────────────

print("=" * 60)
print("ЗАПУСК СИНХРОНИЗАЦИИ")
print("=" * 60)
print()

from env_config import load_env

ENV_PATH = load_env()

if ENV_PATH:
    print(f"✅ .env загружен: {ENV_PATH}")
else:
    print(f"⚠️  .env не найден, используются переменные окружения")

# ──────────────────────────────────────────────
# Проверяем переменные
# ──────────────────────────────────────────────

db_host = os.getenv("DB_HOST", "").strip()
db_port = os.getenv("DB_PORT", "").strip()
db_user = os.getenv("DB_USER", "").strip()
db_pass = os.getenv("DB_PASS", "").strip()
db_name = os.getenv("DB_NAME", "").strip()

print("📋 Параметры подключения:")
print(f"   DB_HOST: {db_host}")
print(f"   DB_PORT: {db_port}")
print(f"   DB_USER: {db_user}")
print(f"   DB_PASS: {'*' * len(db_pass)}")
print(f"   DB_NAME: {db_name}")
print()

if not db_host or not db_name:
    print("❌ ОШИБКА: DB_HOST или DB_NAME не заданы!")
    sys.exit(1)

# ──────────────────────────────────────────────
# Подключение к удалённой БД
# ──────────────────────────────────────────────

safe_pass = quote_plus(db_pass) if db_pass else ""
port = db_port or "3306"
remote_url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{port}/{db_name}"

print(f"🔌 Подключение к удалённой БД...")

try:
    remote_engine = create_engine(remote_url, pool_pre_ping=True)
    with remote_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        result.fetchone()
    print(f"✅ Удалённая БД: подключение успешно!")
except Exception as e:
    print(f"❌ ОШИБКА подключения к удалённой БД:")
    print(f"   {e}")
    sys.exit(1)

print()

# ──────────────────────────────────────────────
# Подключение к локальной БД
# ──────────────────────────────────────────────

if LOCAL_DB_PATH.exists() and LOCAL_DB_PATH.stat().st_size == 0:
    LOCAL_DB_PATH.unlink()
    print(f"🗑️  Удалён пустой файл: {LOCAL_DB_PATH}")

local_url = f"sqlite:///{LOCAL_DB_PATH}"
local_engine = create_engine(local_url)
print(f"✅ Локальная БД: {LOCAL_DB_PATH}")

print()

# ──────────────────────────────────────────────
# Создаём таблицы в SQLite через модели
# ──────────────────────────────────────────────

print("📦 Создаю таблицы в локальной БД...")

try:
    # Импортируем модели и db
    sys.path.insert(0, str(PROJECT_ROOT))
    from database.models import db

    # Создаём Flask app для работы с db
    from flask import Flask
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = local_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # Создаём таблицы
    with app.app_context():
        db.create_all()

    print(f"✅ Таблицы созданы успешно!")
except Exception as e:
    print(f"❌ ОШИБКА создания таблиц:")
    print(f"   {e}")
    sys.exit(1)

print()

# ──────────────────────────────────────────────
# Читаем структуру удалённой БД
# ──────────────────────────────────────────────

print("📚 Читаю структуру удалённой БД...")

try:
    remote_meta = MetaData()
    remote_meta.reflect(bind=remote_engine)
    remote_tables = set(remote_meta.tables.keys())
    print(f"   Таблиц в удалённой БД: {len(remote_tables)}")
except Exception as e:
    print(f"❌ ОШИБКА чтения структуры удалённой БД:")
    print(f"   {e}")
    sys.exit(1)

print()

# ──────────────────────────────────────────────
# Синхронизация таблиц
# ──────────────────────────────────────────────

print("🔄 Синхронизация таблиц:")
print("-" * 60)

for table_name in SYNC_TABLES:
    print()
    print(f"   [{table_name}]")

    if table_name not in remote_tables:
        print(f"      ⚠️  Таблица не найдена в удалённой БД. Пропуск.")
        continue

    try:
        # Получаем таблицу из удалённой БД
        remote_table = remote_meta.tables[table_name]

        # Получаем таблицу из локальной БД
        local_meta = MetaData()
        local_meta.reflect(bind=local_engine)

        if table_name not in local_meta.tables:
            print(f"      ⚠️  Таблица не найдена в локальной БД. Пропуск.")
            continue

        local_table = local_meta.tables[table_name]

        # Читаем все данные из удалённой БД
        with remote_engine.connect() as remote_conn:
            result = remote_conn.execute(remote_table.select())
            rows = result.fetchall()
            columns = list(result.keys())

        print(f"      📥 Получено записей: {len(rows)}")

        # Записываем в локальную БД
        with local_engine.connect() as local_conn:
            local_conn.execute(local_table.delete())

            if rows:
                data = [dict(zip(columns, row)) for row in rows]
                local_conn.execute(local_table.insert(), data)

            local_conn.commit()

        print(f"      📤 Записано в локальную БД: {len(rows)}")

    except Exception as e:
        print(f"      ❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

print()
print("=" * 60)
print("✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")
print("=" * 60)

# ──────────────────────────────────────────────
# Проверка результата
# ──────────────────────────────────────────────

print()
print("📊 Проверка локальной БД:")

inspector = inspect(local_engine)
tables = inspector.get_table_names()

if tables:
    for table in tables:
        try:
            with local_engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM [{table}]"))
                count = result.scalar()
                print(f"   • {table:<30} {count} записей")
        except Exception as e:
            print(f"   • {table:<30} ОШИБКА: {e}")
else:
    print("   ⚠️  Таблиц нет!")