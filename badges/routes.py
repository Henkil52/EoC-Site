"""
badges/routes.py

Система значков: создание, назначение, витрина, логи.
Обновлено: список пользователей включает и игроков сервера, и всех, кто заходил на сайт.
"""

import os
import uuid
from types import SimpleNamespace
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from werkzeug.utils import secure_filename

from auth.decorators import login_required
from auth.roles import admin_required, get_user_site_role
from database.models import db, SiteBadge, SiteBadgeLog, Player, SiteUser, site_user_badges
from database.models import moscow_now

bp = Blueprint(
    "badges",
    __name__,
    url_prefix="/badges",
    template_folder="templates",
)

ALLOWED_EXTENSIONS = {"png"}
UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "static" / "badges"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _find_user(steam_id):
    """Находит пользователя в players или site_users. Возвращает объект с атрибутами SteamID, Nickname."""
    player = Player.query.get(steam_id)
    if player:
        return player
    site_user = SiteUser.query.get(steam_id)
    if site_user:
        # Создаём совместимый объект с теми же атрибутами, что у Player
        return SimpleNamespace(
            SteamID=site_user.steam_id,
            Nickname=site_user.nickname or site_user.steam_id,
        )
    return None


def _all_users():
    """Объединённый список всех пользователей: игроки сервера + пользователи сайта.
    Без дубликатов. Сортировка по нику.
    """
    seen = set()
    users = []

    # Сначала игроки сервера
    for p in Player.query.order_by(Player.Nickname).all():
        users.append(p)
        seen.add(p.SteamID)

    # Затем пользователи сайта, которых нет в players
    for u in SiteUser.query.order_by(SiteUser.nickname).all():
        if u.steam_id not in seen:
            users.append(SimpleNamespace(
                SteamID=u.steam_id,
                Nickname=u.nickname or u.steam_id,
            ))
            seen.add(u.steam_id)

    # Сортируем по нику (регистронезависимо)
    users.sort(key=lambda x: (x.Nickname or "").lower())
    return users


def log_action(action, badge, actor, user=None, details=None):
    """Логирует действие со значком."""
    log_entry = SiteBadgeLog(
        action=action,
        badge_id=badge.id if badge else None,
        badge_name=badge.name if badge else "N/A",
        user_steam_id=user.SteamID if user else None,
        user_nickname=user.Nickname if user else None,
        actor_steam_id=actor.SteamID,
        actor_nickname=actor.Nickname,
        details=details,
    )
    db.session.add(log_entry)
    db.session.commit()


@bp.route("/")
@login_required
def index():
    """Список всех значков."""
    badges = SiteBadge.query.order_by(SiteBadge.created_at.desc()).all()
    is_admin = False
    try:
        from auth.roles import has_role
        is_admin = bool(has_role(session.get("user", {}).get("steam_id"), "admin"))
    except Exception:
        is_admin = False
    
    return render_template("badges/index.html", badges=badges, is_admin=is_admin)


@bp.route("/admin")
@login_required
@admin_required
def admin():
    """Админ-панель: управление значками."""
    badges = SiteBadge.query.order_by(SiteBadge.created_at.desc()).all()
    players = _all_users()
    return render_template("badges/admin.html", badges=badges, players=players)


@bp.route("/create", methods=["POST"])
@login_required
@admin_required
def create():
    """Создание нового значка."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    file = request.files.get("image")
    
    if not name:
        flash("Название значка обязательно", "error")
        return redirect(url_for("badges.admin"))
    
    if not file or not allowed_file(file.filename):
        flash("Загрузите PNG-файл", "error")
        return redirect(url_for("badges.admin"))
    
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    filepath = UPLOAD_FOLDER / filename
    file.save(filepath)
    
    actor_steam_id = session.get("user", {}).get("steam_id")
    actor = _find_user(actor_steam_id)
    
    badge = SiteBadge(
        name=name,
        description=description,
        image_filename=filename,
        created_by_steam_id=actor_steam_id,
    )
    db.session.add(badge)
    db.session.commit()
    
    log_action("create", badge, actor, details=f"Создан значок '{name}'")
    
    flash(f"Значок '{name}' создан", "success")
    return redirect(url_for("badges.admin"))


@bp.route("/award", methods=["POST"])
@login_required
@admin_required
def award():
    """Назначение значка пользователю."""
    badge_id = request.form.get("badge_id", type=int)
    user_steam_id = request.form.get("user_steam_id")
    
    badge = SiteBadge.query.get_or_404(badge_id)
    user = _find_user(user_steam_id)
    if not user:
        flash("Пользователь не найден", "error")
        return redirect(url_for("badges.admin"))

    actor_steam_id = session.get("user", {}).get("steam_id")
    actor = _find_user(actor_steam_id)
    
    existing = db.session.query(site_user_badges).filter_by(
        user_steam_id=user_steam_id, badge_id=badge_id
    ).first()
    
    if existing:
        flash(f"У {user.Nickname} уже есть значок '{badge.name}'", "warning")
        return redirect(url_for("badges.admin"))
    
    stmt = site_user_badges.insert().values(
        user_steam_id=user_steam_id,
        badge_id=badge_id,
        awarded_at=moscow_now(),
        awarded_by_steam_id=actor_steam_id,
    )
    db.session.execute(stmt)
    db.session.commit()
    
    log_action("award", badge, actor, user=user, details=f"Значок '{badge.name}' назначен игроку {user.Nickname}")
    
    flash(f"Значок '{badge.name}' назначен игроку {user.Nickname}", "success")
    return redirect(url_for("badges.admin"))


@bp.route("/revoke", methods=["POST"])
@login_required
@admin_required
def revoke():
    """Отзыв значка у пользователя."""
    badge_id = request.form.get("badge_id", type=int)
    user_steam_id = request.form.get("user_steam_id")
    
    badge = SiteBadge.query.get_or_404(badge_id)
    user = _find_user(user_steam_id)
    if not user:
        flash("Пользователь не найден", "error")
        return redirect(url_for("badges.admin"))

    actor_steam_id = session.get("user", {}).get("steam_id")
    actor = _find_user(actor_steam_id)
    
    stmt = site_user_badges.delete().where(
        (site_user_badges.c.user_steam_id == user_steam_id) &
        (site_user_badges.c.badge_id == badge_id)
    )
    db.session.execute(stmt)
    db.session.commit()
    
    log_action("revoke", badge, actor, user=user, details=f"Значок '{badge.name}' отозван у {user.Nickname}")
    
    flash(f"Значок '{badge.name}' отозван у {user.Nickname}", "success")
    return redirect(url_for("badges.admin"))


@bp.route("/delete/<int:badge_id>", methods=["POST"])
@login_required
@admin_required
def delete(badge_id):
    """Удаление значка."""
    badge = SiteBadge.query.get_or_404(badge_id)
    actor_steam_id = session.get("user", {}).get("steam_id")
    actor = _find_user(actor_steam_id)
    
    stmt = site_user_badges.delete().where(site_user_badges.c.badge_id == badge_id)
    db.session.execute(stmt)
    
    filepath = UPLOAD_FOLDER / badge.image_filename
    if filepath.exists():
        filepath.unlink()
    
    log_action("delete", badge, actor, details=f"Удалён значок '{badge.name}'")
    
    db.session.delete(badge)
    db.session.commit()
    
    flash(f"Значок '{badge.name}' удалён", "success")
    return redirect(url_for("badges.admin"))


@bp.route("/log/<int:badge_id>")
@login_required
@admin_required
def log(badge_id):
    """Просмотр лога действий со значком."""
    badge = SiteBadge.query.get_or_404(badge_id)
    logs = SiteBadgeLog.query.filter_by(badge_id=badge_id).order_by(
        SiteBadgeLog.created_at.desc()
    ).all()
    return render_template("badges/log.html", badge=badge, logs=logs)
