"""
achievements/routes.py

Витрина достижений, редактор достижений (админ), уведомления.
"""

import json
import re
from pathlib import Path

from flask import (
    Blueprint, render_template, session, redirect, url_for,
    jsonify, request, flash,
)
from markupsafe import Markup, escape

from auth.decorators import login_required
from auth.roles import admin_required
from database.models import PlayerAchievement, Player

from achievements.service import (
    get_defs, add_trigger_column, delete_def, process_history,
    get_showcase, notifications_for, mark_all_read,
)

bp = Blueprint(
    "achievements",
    __name__,
    url_prefix="/achievements",
    template_folder="templates",
)

HISTORY_DIR = Path(__file__).resolve().parent.parent / "local_history"

# Конфиг старых достижений из БД (страница /achievements/<steam_id>)
ACHIEVEMENTS = {
    3: {"icon": "🎯", "name": "Охотник Зоны",
        "desc": "Уничтожить логова мутантов."},
    4: {"icon": "⚡", "name": "Боевое крещение",
        "desc": "Особое достижение сервера."},
    6: {"icon": "🗺", "name": "Следопыт",
        "desc": "Посетить ключевые локации Зоны."},
    8: {"icon": "🏅", "name": "Ветеран Зоны",
        "desc": "Особое достижение сервера."},
}


def _progress_info(row):
    try:
        data = json.loads(row.Progress or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict) or not data:
        return None
    total = len(data)
    done = sum(1 for v in data.values() if isinstance(v, (int, float)) and v > 0)
    return done, total, data


@bp.route("/<steam_id>")
def showcase(steam_id):
    """Старая страница достижений из игровой БД."""
    user = session.get("user")
    if not user or not user.get("steam_id"):
        return redirect(url_for("auth.login"))

    player = Player.query.get(steam_id)
    nickname = player.Nickname if player and player.Nickname else steam_id

    rows = PlayerAchievement.query.filter_by(SteamID=steam_id).all()
    ach_list = []
    for row in rows:
        cfg = ACHIEVEMENTS.get(row.AchievementID, {
            "icon": "🏆", "name": f"Достижение #{row.AchievementID}",
            "desc": "Описание уточняется.",
        })
        ach_list.append({
            "id": row.AchievementID, "icon": cfg["icon"], "name": cfg["name"],
            "desc": cfg["desc"], "achieved": bool(row.IsAchieved),
            "achieved_at": row.AchievedAt, "progress": _progress_info(row),
        })
    known = {r.AchievementID for r in rows}
    for aid, cfg in ACHIEVEMENTS.items():
        if aid not in known:
            ach_list.append({
                "id": aid, "icon": cfg["icon"], "name": cfg["name"],
                "desc": cfg["desc"], "achieved": False,
                "achieved_at": None, "progress": None,
            })
    ach_list.sort(key=lambda x: (not x["achieved"], x["id"]))

    history = None
    hfile = HISTORY_DIR / f"{steam_id}.json"
    if hfile.exists():
        try:
            history = json.loads(hfile.read_text(encoding="utf-8"))
        except Exception:
            history = None

    loc_names = {}
    if history:
        for ev in history.get("events", []):
            tid = ev.get("trigger_id")
            if tid and tid not in loc_names:
                loc_names[tid] = (ev.get("value") or tid)[:60]

    return render_template(
        "achievements/showcase.html",
        steam_id=steam_id, nickname=nickname,
        achievements=ach_list, history=history, loc_names=loc_names,
    )


# ═══════════════════════════════════════════════════════════════════
# РЕДАКТОР ДОСТИЖЕНИЙ (админ)
# ═══════════════════════════════════════════════════════════════════

@bp.route("/editor")
@login_required
@admin_required
def editor():
    return render_template("achievements/editor.html", defs=get_defs())


@bp.route("/editor/add", methods=["POST"])
@login_required
@admin_required
def editor_add():
    kind = request.form.get("kind", "location")
    trigger = (request.form.get("trigger") or "").strip()
    title = (request.form.get("title") or "").strip()
    sticker = (request.form.get("sticker") or "").strip()

    if kind not in ("location", "item"):
        flash("❌ Неверный тип", "error")
        return redirect(url_for("achievements.editor"))
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,60}", trigger):
        flash("❌ Триггер: только латиница, цифры, подчёркивание", "error")
        return redirect(url_for("achievements.editor"))
    if not title or not sticker:
        flash("❌ Укажи название и стикер", "error")
        return redirect(url_for("achievements.editor"))
    if "." not in sticker:
        sticker += ".webp"

    ok, msg = add_trigger_column(kind, trigger, title, sticker)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("achievements.editor"))


@bp.route("/editor/delete/<int:def_id>", methods=["POST"])
@login_required
@admin_required
def editor_delete(def_id):
    ok, msg = delete_def(def_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("achievements.editor"))


@bp.route("/editor/sync", methods=["POST"])
@login_required
@admin_required
def editor_sync():
    n = process_history()
    flash(f"✅ Синхронизация: новых достижений — {n}", "success")
    return redirect(url_for("achievements.editor"))


# ═══════════════════════════════════════════════════════════════════
# УВЕДОМЛЕНИЯ (колокол)
# ═══════════════════════════════════════════════════════════════════

@bp.route("/api/notifications")
@login_required
def api_notifications():
    sid = session.get("user", {}).get("steam_id")
    return jsonify({"notifications": notifications_for(sid)})


@bp.route("/api/notifications/read", methods=["POST"])
@login_required
def api_notifications_read():
    sid = session.get("user", {}).get("steam_id")
    mark_all_read(sid)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════
# ВИТРИНА (для вставки в шаблоны)
# ═══════════════════════════════════════════════════════════════════

@bp.app_context_processor
def inject_achievement_showcase():
    def achievement_showcase(steam_id):
        if not steam_id:
            return Markup("")
        items = get_showcase(steam_id)
        if not items:
            return Markup("")
        cards = []
        for it in items:
            cls = "achv-card achv-done" if it["achieved"] else "achv-card achv-locked"
            cards.append(
                f'<div class="{cls}" title="{escape(it["title"])}">'
                f'<img class="achv-img" src="{escape(it["sticker_url"])}" alt="">'
                f'<div class="achv-title">{escape(it["title"]) if it["achieved"] else "???"}</div>'
                f'</div>'
            )
        html = (
            '<section class="ach-showcase"><h2>🏆 Достижения</h2>'
            '<div class="achv-grid">' + "".join(cards) + '</div></section>'
        )
        return Markup(html)
    return {"achievement_showcase": achievement_showcase}
