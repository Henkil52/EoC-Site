"""
full_db_export.py

Полная выгрузка ВСЕХ таблиц из удалённой игровой БД в CSV для анализа.
Каждая таблица сохраняется в отдельный CSV-файл в папке db_export/.

Использование:
    python full_db_export.py
"""

import csv
import os
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

PROJECT_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = PROJECT_ROOT / "db_export"
ENV_PATH = Path(r"C:\Users\Administrator\Documents\.env")

# Цветной вывод
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    GREEN = Fore.GREEN
    BLUE = Fore.BLUE
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    CYAN = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    RESET = Style.RESET_ALL
    BOLD = Style.BRIGHT
except ImportError:
    GREEN = BLUE = YELLOW = RED = CYAN = MAGENTA = RESET = BOLD = ''


def get_remote_engine():
    """Подключение к удалённой игровой БД."""
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    else:
        load_dotenv(override=True)

    db_host = os.getenv("DB_HOST", "").strip()
    db_port = os.getenv("DB_PORT", "3306").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()

    if not db_host or not db_name:
        print(f"{RED}❌ DB_HOST или DB_NAME не заданы в .env{RESET}")
        return None

    safe_pass = quote_plus(db_pass) if db_pass else ""
    url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{db_port}/{db_name}"

    return create_engine(url, pool_pre_ping=True)


def main():
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}📦 ПОЛНАЯ ВЫГРУЗКА БАЗЫ ДАННЫХ{RESET}")
    print(f"{BOLD}{GREEN}Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")

    engine = get_remote_engine()
    if not engine:
        return

    # Создаём папку для экспорта
    EXPORT_DIR.mkdir(exist_ok=True)
    print(f"\n{BLUE}📁 Папка для экспорта: {EXPORT_DIR}{RESET}")

    # Получаем список всех таблиц
    inspector = inspect(engine)
    all_tables = sorted(inspector.get_table_names())

    print(f"{BLUE}📋 Всего таблиц: {len(all_tables)}{RESET}")
    print()

    total_rows = 0
    exported = 0
    empty = 0
    errors = 0

    with engine.connect() as conn:
        for i, table in enumerate(all_tables, start=1):
            print(f"{CYAN}[{i}/{len(all_tables)}]{RESET} Таблица: {BOLD}{table}{RESET}")

            try:
                # Читаем все данные
                result = conn.execute(text(f"SELECT * FROM `{table}`"))
                rows = result.fetchall()

                if not rows:
                    print(f"   {YELLOW}⚠️  Пуста (0 записей){RESET}")
                    empty += 1
                    continue

                columns = list(rows[0]._mapping.keys())

                # Сохраняем в CSV
                csv_path = EXPORT_DIR / f"{table}.csv"
                with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    for row in rows:
                        writer.writerow(list(row._mapping.values()))

                total_rows += len(rows)
                exported += 1

                print(f"   {GREEN}✅ {len(rows)} записей → {table}.csv{RESET}")

            except Exception as e:
                errors += 1
                print(f"   {RED}❌ Ошибка: {e}{RESET}")

    # ── Итоговая сводка ────────────────────────────────────────
    print()
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}📊 ИТОГОВАЯ СВОДКА{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"  Всего таблиц          : {len(all_tables)}")
    print(f"  Выгружено             : {exported}")
    print(f"  Пустых                : {empty}")
    print(f"  Ошибок                : {errors}")
    print(f"  Всего записей         : {total_rows}")
    print(f"  Папка с файлами       : {EXPORT_DIR}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")


if __name__ == "__main__":
    main()