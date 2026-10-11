"""
sync/ftp_sync.py

Скачивает player_database.json с FTP и записывает расширенную
статистику и статистику по оружию в локальную БД.
Вызывается каждые 15 минут вместе с основной синхронизацией.
"""

import ftplib
import io
import json
import logging
import os
import ssl
from datetime import datetime
from pathlib import Path

from flask import Flask

from database.models import db, PlayerExtendedStats, PlayerWeaponStats

logger = logging.getLogger("ftp_sync")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_PATH = PROJECT_ROOT / "local_db.sqlite3"


def _get_ftp_config():
    """Читает настройки FTP из переменных окружения."""
    return {
        'host': os.getenv("FTP_HOST", "").strip(),
        'port': int(os.getenv("FTP_PORT", "21").strip() or "21"),
        'username': os.getenv("FTP_USERNAME", "").strip(),
        'password': os.getenv("FTP_PASSWORD", "").strip(),
        'remote_dir': os.getenv("FTP_REMOTE_DIR", "").strip(),
        'use_ssl': os.getenv("FTP_USE_SSL", "True").strip().lower() in ('true', '1', 'yes'),
        'verify_cert': os.getenv("ssl_verify_cert", "False").strip().lower() in ('true', '1', 'yes'),
    }


def _parse_dt(value):
    """Парсит дату из формата JSON."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def sync_ftp_player_stats():
    """
    Скачивает player_database.json с FTP и обновляет
    player_extended_stats и player_weapon_stats в локальной БД.
    """
    config = _get_ftp_config()

    if not config['host']:
        logger.warning("FTP_HOST не задан — пропускаю синхронизацию FTP-статистики")
        return 0

    # ── Скачиваем player_database.json ────────────────────────
    try:
        if config['use_ssl']:
            ctx = ssl.create_default_context()
            if not config['verify_cert']:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            ftp = ftplib.FTP_TLS(context=ctx)
        else:
            ftp = ftplib.FTP()

        ftp.connect(config['host'], config['port'], timeout=30)

        if config['username']:
            ftp.login(config['username'], config['password'])
        else:
            ftp.login()

        if config['use_ssl']:
            ftp.prot_p()

        # ── ПЕРЕХОДИМ В ПАПКУ С ДАННЫМИ (исправление) ─────────
        if config['remote_dir']:
            ftp.cwd(config['remote_dir'])
            logger.info(f"FTP: перешли в {config['remote_dir']}")

        buffer = io.BytesIO()
        ftp.retrbinary("RETR player_database.json", buffer.write)
        ftp.quit()

    except Exception as e:
        logger.error(f"Ошибка скачивания player_database.json: {e}")
        return 0

    # ── Парсим JSON ───────────────────────────────────────────
    try:
        data = json.loads(buffer.getvalue().decode("utf-8"))
    except Exception as e:
        logger.error(f"Ошибка разбора player_database.json: {e}")
        return 0

    # ── Записываем в локальную БД ─────────────────────────────
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{LOCAL_DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    updated = 0

    with app.app_context():
        for steam_id, rec in data.items():
            ext = PlayerExtendedStats.query.filter_by(SteamID=steam_id).first()

            if not ext:
                ext = PlayerExtendedStats(SteamID=steam_id)
                db.session.add(ext)

            ext.FirstJoinDate = _parse_dt(rec.get("FirstJoinDate"))
            ext.LastSeen = _parse_dt(rec.get("LastSeen"))
            ext.SessionCount = rec.get("SessionCount", 0)
            ext.TotalPlayTime = rec.get("TotalPlayTime", 0)
            ext.Kills = rec.get("Kills", 0)
            ext.Deaths = rec.get("Deaths", 0)
            ext.KDRatio = rec.get("KDRatio", 0)
            ext.FavoriteWeapon = rec.get("FavoriteWeapon", "Нет")
            ext.FavoriteWeaponKills = rec.get("FavoriteWeaponKills", 0)
            ext.HeadshotKills = rec.get("HeadshotKills", 0)
            ext.HeadshotRatio = rec.get("HeadshotRatio", 0)
            ext.TotalDistanceTraveled = rec.get("TotalDistanceTraveled", 0)
            ext.ItemsCrafted = rec.get("ItemsCrafted", 0)
            ext.BuildingsConstructed = rec.get("BuildingsConstructed", 0)
            ext.TrapCount = rec.get("TrapCount", 0)
            ext.ZombieKills = rec.get("ZombieKills", 0)
            ext.AnimalKills = rec.get("AnimalKills", 0)
            ext.NamesHistory = json.dumps(rec.get("NamesHistory", []), ensure_ascii=False)
            ext.LastPosition = json.dumps(rec.get("LastPosition", []))

            # Оружие: удаляем старые записи и вставляем новые
            PlayerWeaponStats.query.filter_by(SteamID=steam_id).delete()

            for weapon, kills in (rec.get("WeaponKills") or {}).items():
                db.session.add(PlayerWeaponStats(
                    SteamID=steam_id,
                    WeaponName=weapon,
                    Kills=kills,
                ))

            updated += 1

        db.session.commit()

    logger.info(f"FTP-статистика синхронизирована: {updated} игроков")
    return updated