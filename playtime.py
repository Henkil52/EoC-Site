"""
playtime.py

Дневные снапшоты TotalPlayTime и расчёт
"часов за последние 7 дней" для игрока.
"""

from datetime import date, timedelta

from database.models import db, PlayerExtendedStats, PlaytimeSnapshot


def take_playtime_snapshots():
    """Раз в день записывает снапшот TotalPlayTime каждого игрока."""
    today = date.today()
    added = 0
    for row in PlayerExtendedStats.query.all():
        exists = PlaytimeSnapshot.query.filter_by(
            steam_id=row.SteamID, snapshot_date=today
        ).first()
        if not exists:
            db.session.add(PlaytimeSnapshot(
                steam_id=row.SteamID,
                snapshot_date=today,
                total_playtime=row.TotalPlayTime or 0,
            ))
            added += 1
    if added:
        db.session.commit()
        print(f"[playtime] снапшотов за {today}: {added}")
    return added


def weekly_hours(steam_id):
    """
    Возвращает (hours, days):
      hours — часов за последние 7 дней
              (или с начала наблюдения, если данных меньше недели)
      days  — сколько дней охватывает измерение
    Если данных нет — (None, None).
    """
    ext = PlayerExtendedStats.query.get(steam_id)
    if ext is None or ext.TotalPlayTime is None:
        return None, None

    today = date.today()
    target = today - timedelta(days=7)

    # Снапшот ровно до окна 7 дней (или ближайший ранее)
    snap = (
        PlaytimeSnapshot.query
        .filter(PlaytimeSnapshot.steam_id == steam_id)
        .filter(PlaytimeSnapshot.snapshot_date <= target)
        .order_by(PlaytimeSnapshot.snapshot_date.desc())
        .first()
    )
    if snap is not None:
        days = (today - snap.snapshot_date).days
    else:
        # Истории ещё мало — берём самый первый снапшот
        snap = (
            PlaytimeSnapshot.query
            .filter(PlaytimeSnapshot.steam_id == steam_id)
            .order_by(PlaytimeSnapshot.snapshot_date.asc())
            .first()
        )
        if snap is None:
            return None, None
        days = max((today - snap.snapshot_date).days, 1)

    delta = (ext.TotalPlayTime or 0) - (snap.total_playtime or 0)
    if delta < 0:
        delta = 0
    return round(delta / 3600, 1), days
