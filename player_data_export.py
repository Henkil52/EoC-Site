"""
player_data_export.py

Скрипт для выгрузки всех данных игрока по Steam ID из локальной БД.
Использует локальную SQLite базу данных.

Использование:
    python player_data_export.py                  # спросит Steam ID
    python player_data_export.py 76561198123456789  # передать Steam ID сразу
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Путь к локальной БД
LOCAL_DB_PATH = Path(__file__).resolve().parent / "local_db.sqlite3"


def format_datetime(dt):
    """Форматирует datetime для вывода."""
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    return dt


def export_player_data(steam_id):
    """Выгружает все данные игрока по Steam ID."""

    if not LOCAL_DB_PATH.exists():
        print(f"❌ ОШИБКА: Локальная БД не найдена: {LOCAL_DB_PATH}")
        print("Запустите синхронизацию сначала.")
        return

    engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")

    print(f"\n{'=' * 70}")
    print(f"ВЫГРУЗКА ДАННЫХ ИГРОКА")
    print(f"Steam ID: {steam_id}")
    print(f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    with engine.connect() as conn:
        # ── 1. Основная информация из players ─────────────────────
        print("📋 ОСНОВНАЯ ИНФОРМАЦИЯ (таблица: players)")
        print("-" * 70)

        result = conn.execute(
            text("SELECT * FROM players WHERE SteamID = :steam_id"),
            {"steam_id": steam_id}
        )
        player = result.fetchone()

        if not player:
            print("❌ Игрок не найден в базе данных.")
            print(f"Steam ID {steam_id} отсутствует в таблице 'players'.")
            return

        for key, value in player._mapping.items():
            if key in ['RegistrationDate', 'LastLogonDate']:
                value = format_datetime(value)
            print(f"  {key:<25} : {value}")

        print()

        # ── 2. Статистика из player_stats ────────────────────────
        print("📊 СТАТИСТИКА (таблица: player_stats)")
        print("-" * 70)

        result = conn.execute(
            text("SELECT * FROM player_stats WHERE SteamID = :steam_id"),
            {"steam_id": steam_id}
        )
        stats = result.fetchone()

        if stats:
            for key, value in stats._mapping.items():
                if key != 'SteamID':
                    print(f"  {key:<25} : {value}")
        else:
            print("  ⚠️ Статистика не найдена")

        print()

        # ── 3. Фракция и ранг ────────────────────────────────────
        print("⚔️ ФРАКЦИЯ И РАНГ")
        print("-" * 70)

        result = conn.execute(
            text("""
                SELECT 
                    fm.FACTION_ID,
                    fm.RankID,
                    f.Name as FactionName,
                    f.Icon as FactionIcon,
                    fr.Name as RankName,
                    fr.Permissions
                FROM faction_members fm
                LEFT JOIN factions f ON fm.FACTION_ID = f.ID
                LEFT JOIN faction_ranks fr ON fm.RankID = fr.RankID
                WHERE fm.MEMBER_ID = :steam_id
            """),
            {"steam_id": steam_id}
        )
        faction_data = result.fetchone()

        if faction_data:
            print(f"  {'Фракция':<25} : {faction_data.FactionName}")
            print(f"  {'ID фракции':<25} : {faction_data.FACTION_ID}")
            print(f"  {'Иконка':<25} : {faction_data.FactionIcon}")
            print(f"  {'Ранг':<25} : {faction_data.RankName}")
            print(f"  {'ID ранга':<25} : {faction_data.RankID}")
            print(f"  {'Права доступа':<25} : {faction_data.Permissions}")
        else:
            print("  ⚠️ Игрок не состоит ни в одной фракции (одиночка)")

        print()

        # ── 4. Достижения ────────────────────────────────────────
        print("🏆 ДОСТИЖЕНИЯ (таблица: player_achievements)")
        print("-" * 70)

        result = conn.execute(
            text("""
                SELECT 
                    AchievementID,
                    IsAchieved,
                    AchievedAt,
                    Progress
                FROM player_achievements
                WHERE SteamID = :steam_id
                ORDER BY AchievementID
            """),
            {"steam_id": steam_id}
        )
        achievements = result.fetchall()

        if achievements:
            print(f"  Всего записей о достижениях: {len(achievements)}")
            print()

            achieved = [a for a in achievements if a.IsAchieved]
            in_progress = [a for a in achievements if not a.IsAchieved]

            print(f"  ✅ Получено достижений: {len(achieved)}")
            print(f"  ⏳ В процессе: {len(in_progress)}")
            print()

            if achieved:
                print("  Полученные достижения:")
                for ach in achieved[:10]:  # Показываем первые 10
                    achieved_at = format_datetime(ach.AchievedAt) if ach.AchievedAt else "—"
                    print(f"    • ID {ach.AchievementID:<3} — получен {achieved_at}")
                if len(achieved) > 10:
                    print(f"    ... и ещё {len(achieved) - 10}")
        else:
            print("  ⚠️ Достижения не найдены")

        print()

        # ── 5. PDA аккаунт ───────────────────────────────────────
        print("📱 PDA АККАУНТ (таблица: pda_accounts)")
        print("-" * 70)

        result = conn.execute(
            text("SELECT * FROM pda_accounts WHERE SteamID = :steam_id"),
            {"steam_id": steam_id}
        )
        pda = result.fetchone()

        if pda:
            for key, value in pda._mapping.items():
                if key == 'LastActivity':
                    value = format_datetime(value)
                if key != 'SteamID':
                    print(f"  {key:<25} : {value}")
        else:
            print("  ⚠️ PDA аккаунт не найден")

        print()

        # ── 6. Сводка ────────────────────────────────────────────
        print("=" * 70)
        print("📝 СВОДКА ДЛЯ ПРОФИЛЯ НА САЙТЕ")
        print("=" * 70)
        print()

        print("Можно вывести на сайт:")
        print()

        # Основная информация
        print("1️⃣  Основная информация:")
        print(f"   • Никнейм: {player.Nickname}")
        print(f"   • Дата регистрации: {format_datetime(player.RegistrationDate)}")
        print(f"   • Последний вход: {format_datetime(player.LastLogonDate)}")
        print()

        # Статистика
        if stats:
            print("2️⃣  Статистика:")
            print(f"   • Пережито выбросов: {stats.EmissionSurvived}")
            print(f"   • Убито мутантов: {stats.MutantsKills}")
            print(f"   • Убито игроков: {stats.PlayerKills}")
            print(f"   • Найдено тайников: {stats.StashesFound}")
            print(f"   • Найдено артефактов: {stats.ArtefactFound}")
            print()

        # Фракция
        if faction_data:
            print("3️⃣  Фракция:")
            print(f"   • Название: {faction_data.FactionName}")
            print(f"   • Ранг: {faction_data.RankName}")
            print()

        # Достижения
        if achievements:
            achieved_count = len([a for a in achievements if a.IsAchieved])
            print("4️⃣  Достижения:")
            print(f"   • Получено: {achieved_count}")
            print(f"   • Всего в базе: {len(achievements)}")
            print()

        print("=" * 70)


def main():
    if len(sys.argv) > 1:
        steam_id = sys.argv[1]
    else:
        steam_id = input("\nВведите Steam ID игрока: ").strip()

    if not steam_id:
        print("❌ Steam ID не может быть пустым")
        return

    export_player_data(steam_id)


if __name__ == "__main__":
    main()