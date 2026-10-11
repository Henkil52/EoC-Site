"""
auth/game_data.py

Получение игровых данных из локальной БД.
Используется для обновления никнейма и других данных при входе.
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"


def get_game_nickname(steam_id):
    """
    Возвращает игровой никнейм из локальной БД по Steam ID.
    Если игрок не найден — возвращает None.
    """
    if not LOCAL_DB_PATH.exists():
        return None

    try:
        engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT Nickname FROM players WHERE SteamID = :steam_id"),
                {"steam_id": steam_id}
            )
            row = result.fetchone()

        if row and row.Nickname:
            return row.Nickname

        return None

    except Exception as e:
        print(f"Ошибка получения игрового никнейма: {e}")
        return None


def get_game_player_data(steam_id):
    """
    Возвращает полные игровые данные из локальной БД по Steam ID.
    Используется для обновления сессии.
    """
    if not LOCAL_DB_PATH.exists():
        return None

    try:
        engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
        with engine.connect() as conn:
            # Основная информация
            result = conn.execute(
                text("SELECT * FROM players WHERE SteamID = :steam_id"),
                {"steam_id": steam_id}
            )
            player = result.fetchone()

        if not player:
            return None

        return {
            "game_nickname": player.Nickname,
            "registration_date": player.RegistrationDate,
            "last_logon_date": player.LastLogonDate,
        }

    except Exception as e:
        print(f"Ошибка получения игровых данных: {e}")
        return None