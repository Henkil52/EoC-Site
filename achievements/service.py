"""
achievements/service.py

Логика достижений: динамические столбцы, обработка логов,
витрина и уведомления.
"""

import json
from pathlib import Path

from flask import url_for
from sqlalchemy import text

from database.models import db, AchievementDef, AchievementNotification

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "local_history"
STICKER_FOLDER = "stickers/achievement"

_tables_ready = False


def ensure_tables():
    """Создаёт широкие таблицы, если их нет."""
    global _tables_ready
    if _tables_ready:
        return
    for t in ("ach_locations", "ach_items"):
        db.session.execute(text(
            f"CREATE TABLE IF NOT EXISTS {t} (steam_id TEXT PRIMARY KEY)"
        ))
    db.session.commit()
    _tables_ready = True


def _columns(table):
    rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return [r[1] for r in rows]


def _mapping(table, row):
    if row is None:
        return {}
    try:
        return dict(row._mapping)
    except Exception:
        return dict(zip(_columns(table), row))


def get_defs():
    ensure_tables()
    return AchievementDef.query.order_by(AchievementDef.id).all()


def add_trigger_column(kind, trigger, title, sticker):
    """Создаёт достижение + столбец в широкой таблице."""
    ensure_tables()
    table = "ach_locations" if kind == "location" else "ach_items"
    if AchievementDef.query.filter_by(trigger=trigger).first():
        return False, "❌ Такой триггер уже существует"
    if trigger not in _columns(table):
        db.session.execute(text(
            f'ALTER TABLE {table} ADD COLUMN "{trigger}" INTEGER NOT NULL DEFAULT 0'
        ))
        db.session.commit()
    d = AchievementDef(kind=kind, trigger=trigger, title=title, sticker=sticker)
    db.session.add(d)
    db.session.commit()
    return True, f"✅ Достижение '{title}' добавлено"


def delete_def(def_id):
    d = AchievementDef.query.get(def_id)
    if not d:
        return False, "❌ Не найдено"
    AchievementNotification.query.filter_by(def_id=def_id).delete()
    db.session.delete(d)
    db.session.commit()
    return True, "✅ Удалено"


def process_history():
    """Проходит логи history и отмечает достижения + создаёт уведомления."""
    ensure_tables()
    defs = AchievementDef.query.all()
    if not defs or not HISTORY_DIR.exists():
        return 0

    new_notes = 0
    for f in sorted(HISTORY_DIR.glob("*.json")):
        sid = f.stem
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        values = {
            "location": set(data.get("visited_locations") or []),
            "item": set(data.get("found_items") or []),
        }

        for kind, table in (("location", "ach_locations"), ("item", "ach_items")):
            relevant = [d for d in defs if d.kind == kind]
            if not relevant:
                continue
            cols = _columns(table)
            db.session.execute(
                text(f"INSERT OR IGNORE INTO {table} (steam_id) VALUES (:sid)"),
                {"sid": sid},
            )
            row = db.session.execute(
                text(f"SELECT * FROM {table} WHERE steam_id=:sid"), {"sid": sid}
            ).fetchone()
            cur = _mapping(table, row)

            for d in relevant:
                if d.trigger not in cols:
                    continue
                if cur.get(d.trigger):
                    continue
                if d.trigger in values[kind]:
                    db.session.execute(
                        text(f'UPDATE {table} SET "{d.trigger}"=1 WHERE steam_id=:sid'),
                        {"sid": sid},
                    )
                    db.session.add(AchievementNotification(
                        steam_id=sid, def_id=d.id, title=d.title, sticker=d.sticker,
                    ))
                    new_notes += 1

    db.session.commit()
    return new_notes


def get_showcase(steam_id):
    """Достижения игрока для витрины."""
    ensure_tables()
    defs = AchievementDef.query.order_by(AchievementDef.id).all()
    if not defs:
        return []

    rows = {}
    for kind, table in (("location", "ach_locations"), ("item", "ach_items")):
        r = db.session.execute(
            text(f"SELECT * FROM {table} WHERE steam_id=:sid"), {"sid": steam_id}
        ).fetchone()
        rows[kind] = _mapping(table, r)

    out = []
    for d in defs:
        out.append({
            "title": d.title,
            "sticker_url": url_for("static", filename=STICKER_FOLDER + "/" + d.sticker),
            "achieved": bool(rows.get(d.kind, {}).get(d.trigger)),
        })
    return out


def notifications_for(sid):
    items = (
        AchievementNotification.query
        .filter_by(steam_id=sid)
        .order_by(AchievementNotification.id.desc())
        .limit(50)
        .all()
    )
    return [{
        "id": n.id,
        "title": n.title,
        "sticker": url_for("static", filename=STICKER_FOLDER + "/" + n.sticker),
        "time": n.created_at.strftime("%d.%m.%Y %H:%M"),
        "read": bool(n.is_read),
    } for n in items]


def mark_all_read(sid):
    AchievementNotification.query.filter_by(steam_id=sid, is_read=False).update({"is_read": True})
    db.session.commit()
