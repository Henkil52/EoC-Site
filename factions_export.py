"""
factions_export.py

Скрипт для выгрузки списка группировок (фракций) из локальной БД.
Показывает информацию о группировке, её рангах и участниках.

Использование:
    python factions_export.py              # все группировки
    python factions_export.py 1            # группировка с ID=1
    python factions_export.py --stats      # только общая статистика
"""

import sys
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, text

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

LOCAL_DB_PATH = Path(__file__).resolve().parent / "local_db.sqlite3"


def format_datetime(dt):
    if dt is None:
        return "—"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%d.%m.%Y %H:%M")
    return str(dt)


def color_from_int(color_int):
    """Конвертирует integer цвет в HEX для отображения."""
    if color_int is None or color_int == 0:
        return "#888888"
    try:
        # BigInteger в MySQL может быть отрицательным
        color_int = int(color_int)
        if color_int < 0:
            color_int += 2 ** 32
        return f"#{color_int:06X}"
    except Exception:
        return "#888888"


def get_stats(conn):
    """Общая статистика по группировкам."""
    factions_count = conn.execute(text("SELECT COUNT(*) FROM factions")).scalar()
    ranks_count = conn.execute(text("SELECT COUNT(*) FROM faction_ranks")).scalar()
    members_count = conn.execute(text("SELECT COUNT(*) FROM faction_members")).scalar()
    players_count = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()

    return {
        'factions': factions_count,
        'ranks': ranks_count,
        'members': members_count,
        'players': players_count,
    }


def print_faction(conn, faction_id=None):
    """Выводит информацию об одной или всех группировках."""

    # Запрос группировок
    if faction_id:
        factions_query = text("""
            SELECT ID, Name, SpawnPos, MaxMembers, Abilities, Color, Icon
            FROM factions
            WHERE ID = :faction_id
            ORDER BY Name
        """)
        result = conn.execute(factions_query, {"faction_id": faction_id})
    else:
        factions_query = text("""
            SELECT ID, Name, SpawnPos, MaxMembers, Abilities, Color, Icon
            FROM factions
            ORDER BY Name
        """)
        result = conn.execute(factions_query)

    factions = result.fetchall()

    if not factions:
        print(f"{RED}❌ Группировки не найдены{RESET}")
        return

    for faction in factions:
        faction_id_current = faction.ID
        color_hex = color_from_int(faction.Color)

        print()
        print(f"{BOLD}{MAGENTA}{'=' * 70}{RESET}")
        print(f"{BOLD}{MAGENTA}🏛️  ГРУППИРОВКА: {faction.Name} (ID: {faction_id_current}){RESET}")
        print(f"{BOLD}{MAGENTA}{'=' * 70}{RESET}")

        # Основная информация
        print(f"\n{BLUE}📋 Основная информация:{RESET}")
        print(f"  {'ID':<25} : {faction.ID}")
        print(f"  {'Название':<25} : {faction.Name}")
        print(f"  {'Цвет':<25} : {color_hex}")
        print(f"  {'Иконка':<25} : {faction.Icon}")
        print(f"  {'Позиция спавна':<25} : {faction.SpawnPos or '—'}")
        print(f"  {'Макс. участников':<25} : {faction.MaxMembers}")
        print(f"  {'Способности':<25} : {faction.Abilities}")

        # Ранги
        print(f"\n{BLUE}🎖️  Ранги группировки:{RESET}")
        ranks_query = text("""
            SELECT RankID, Name, Permissions
            FROM faction_ranks
            WHERE FACTION_ID = :faction_id
            ORDER BY Permissions DESC, RankID ASC
        """)
        ranks = conn.execute(ranks_query, {"faction_id": faction_id_current}).fetchall()

        if ranks:
            print(f"  Всего рангов: {len(ranks)}")
            print()
            for rank in ranks:
                perm_bin = bin(rank.Permissions)[2:].zfill(10) if rank.Permissions else '0000000000'
                print(f"    • ID {rank.RankID:<3} | {rank.Name:<30} | права: {rank.Permissions} (0b{perm_bin})")
        else:
            print(f"  {YELLOW}⚠️  Ранги не найдены{RESET}")

        # Участники
        print(f"\n{BLUE}👥 Участники группировки:{RESET}")
        members_query = text("""
            SELECT 
                fm.MEMBER_ID,
                fm.RankID,
                fr.Name as RankName,
                p.Nickname,
                p.RegistrationDate,
                p.LastLogonDate
            FROM faction_members fm
            LEFT JOIN faction_ranks fr ON fm.RankID = fr.RankID
            LEFT JOIN players p ON fm.MEMBER_ID = p.SteamID
            WHERE fm.FACTION_ID = :faction_id
            ORDER BY fr.Permissions DESC, p.Nickname ASC
        """)
        members = conn.execute(members_query, {"faction_id": faction_id_current}).fetchall()

        if members:
            print(f"  Всего участников: {len(members)} / {faction.MaxMembers}")
            print()
            for member in members:
                print(
                    f"    • {member.Nickname or 'Без ника':<25} | ранг: {member.RankName or '?':<20} | последний вход: {format_datetime(member.LastLogonDate)}")
        else:
            print(f"  {YELLOW}⚠️  Участников пока нет{RESET}")

        print()


def print_summary(stats):
    """Выводит итоговую сводку."""
    print()
    print(f"{GREEN}{'=' * 70}{RESET}")
    print(f"{GREEN}📊 ИТОГОВАЯ СВОДКА{RESET}")
    print(f"{GREEN}{'=' * 70}{RESET}")
    print(f"  Всего группировок     : {stats['factions']}")
    print(f"  Всего рангов          : {stats['ranks']}")
    print(f"  Всего участников      : {stats['members']}")
    print(f"  Всего игроков в БД   : {stats['players']}")

    if stats['players'] > 0:
        free_stalkers = stats['players'] - stats['members']
        print(f"  Одиночки (без ГП)     : {free_stalkers}")

    print()


def main():
    if not LOCAL_DB_PATH.exists():
        print(f"{RED}❌ Локальная БД не найдена: {LOCAL_DB_PATH}{RESET}")
        print(f"Запустите синхронизацию сначала.")
        sys.exit(1)

    engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")

    print(f"\n{BOLD}{GREEN}{'=' * 70}{RESET}")
    print(f"{BOLD}{GREEN}📋 ВЫГРУЗКА ГРУППИРОВОК{RESET}")
    print(f"{BOLD}{GREEN}Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}{RESET}")
    print(f"{BOLD}{GREEN}{'=' * 70}{RESET}")

    with engine.connect() as conn:
        stats = get_stats(conn)

        # Определяем режим работы
        if len(sys.argv) > 1:
            arg = sys.argv[1]

            if arg == "--stats":
                # Только статистика
                print_summary(stats)
                return

            try:
                faction_id = int(arg)
                print_faction(conn, faction_id=faction_id)
                print_summary(stats)
                return
            except ValueError:
                print(f"{RED}❌ Неверный аргумент: {arg}{RESET}")
                print(f"Используйте ID группировки или --stats")
                sys.exit(1)
        else:
            # Все группировки
            print_faction(conn)
            print_summary(stats)


if __name__ == "__main__":
    main()