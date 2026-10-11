"""
leaderboard/routes.py

Таблица лидеров.
"""

from flask import Blueprint, render_template

from leaderboard.service import get_leaderboards

bp = Blueprint(
    "leaderboard",
    __name__,
    url_prefix="/leaderboard",
    template_folder="templates",
)


@bp.route("/")
def index():
    """Таблица лидеров."""
    from flask import render_template, session, redirect, url_for
    from database.models import db, Player, PlayerStats

    user = session.get("user")
    if not user or not user.get("steam_id"):
        return redirect(url_for("auth.login"))

    categories = {
        "mutants":   {"title": "Охотник",       "icon": "🐾", "description": "Убито мутантов",    "color": "#8bc34a", "field": "MutantsKills"},
        "pvp":       {"title": "PvP",           "icon": "⚔️", "description": "Убито игроков",     "color": "#f44336", "field": "PlayerKills"},
        "stashes":   {"title": "Кладоискатель", "icon": "🎒", "description": "Найдено тайников",  "color": "#ff9800", "field": "StashesFound"},
        "artefacts": {"title": "Артефакты",     "icon": "💎", "description": "Найдено артефактов","color": "#03a9f4", "field": "ArtefactFound"},
        "emission":  {"title": "Выживший",      "icon": "⚡", "description": "Пережито выбросов", "color": "#9c27b0", "field": "EmissionSurvived"},
    }

    leaderboards = {}
    for code, cat in categories.items():
        rows = (
            db.session.query(PlayerStats, Player)
            .join(Player, PlayerStats.SteamID == Player.SteamID)
            .order_by(getattr(PlayerStats, cat["field"]).desc())
            .limit(10)
            .all()
        )
        leaders = [
            {"player": player, "nickname": player.Nickname, "value": getattr(stats, cat["field"])}
            for stats, player in rows
        ]
        cat_obj = type("Category", (), cat)()
        leaderboards[code] = {"category": cat_obj, "leaders": leaders}

    return render_template("leaderboard/index.html", leaderboards=leaderboards)

