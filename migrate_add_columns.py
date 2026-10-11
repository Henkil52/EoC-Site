"""
migrate_add_columns.py

Скрипт миграции:
1. Добавляет недостающие колонки (ALTER TABLE ADD COLUMN)
2. Пересоздаёт таблицы с изменённой схемой (для SQLite)

Запускать один раз после обновления моделей.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "local_db.sqlite3"

# 1. Простые добавления колонок
MIGRATIONS = [
    ("site_news", "content_html", "TEXT", None),
]

# 2. Таблицы, которые нужно пересоздать (с новой схемой)
# SQLite не умеет менять NOT NULL → NULL, поэтому удаляем и создаём заново.
RECREATE_TABLES = [
    "site_rules_changes",
]


def column_exists(cursor, table, column):
    """Проверяет существование колонки."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def table_exists(cursor, table):
    """Проверяет существование таблицы."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate():
    if not DB_PATH.exists():
        print(f"❌ БД не найдена: {DB_PATH}")
        return

    print(f"🔌 Подключение к {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("МИГРАЦИЯ БАЗЫ ДАННЫХ")
    print("=" * 60)

    # 1. Пересоздание таблиц с новой схемой
    recreated = 0
    for table in RECREATE_TABLES:
        if table_exists(cursor, table):
            cursor.execute(f"DROP TABLE {table}")
            print(f"🗑️  Удалена таблица: {table} (будет пересоздана при следующем запуске сайта)")
            recreated += 1
        else:
            print(f"ℹ️  Таблица '{table}' не существует")

    # 2. Простые добавления колонок
    applied = 0
    skipped = 0

    for table, column, col_type, default in MIGRATIONS:
        if not table_exists(cursor, table):
            print(f"⚠️  Таблица '{table}' не существует, пропуск")
            skipped += 1
            continue

        if column_exists(cursor, table, column):
            print(f"ℹ️  {table}.{column} — уже есть")
            skipped += 1
            continue

        if default is None:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        else:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"

        cursor.execute(sql)
        print(f"✅ Добавлена колонка: {table}.{column} ({col_type})")
        applied += 1

    conn.commit()
    conn.close()

    print("=" * 60)
    print(f"Итого:")
    print(f"  Пересоздано таблиц: {recreated}")
    print(f"  Добавлено колонок: {applied}")
    print(f"  Пропущено: {skipped}")
    print("=" * 60)
    print()
    if recreated > 0:
        print("⚠️  ВАЖНО: перезапусти сайт, чтобы таблицы пересоздались с новой схемой.")


if __name__ == "__main__":
    migrate()