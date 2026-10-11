"""
check_local_db.py

Проверка содержимого локальной БД.
"""

from pathlib import Path
from sqlalchemy import create_engine, inspect

LOCAL_DB_PATH = Path(__file__).resolve().parent / "local_db.sqlite3"

if not LOCAL_DB_PATH.exists():
    print(f"❌ Файл локальной БД не найден: {LOCAL_DB_PATH}")
    print("Запустите сайт или синхронизацию, чтобы создать БД.")
    exit(1)

print(f"✅ Локальная БД найдена: {LOCAL_DB_PATH}")
print(f"   Размер: {LOCAL_DB_PATH.stat().st_size} байт")
print()

engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
inspector = inspect(engine)

tables = inspector.get_table_names()

print(f"Таблиц в локальной БД: {len(tables)}")
print()

if tables:
    for table in tables:
        with engine.connect() as conn:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = result.scalar()
            print(f"  • {table:<35} ({count} записей)")
else:
    print("  ⚠️  Таблиц нет! БД пуста.")
