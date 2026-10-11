"""
auth/roles.py

Декораторы и хелперы для ролевой модели.
"""

from functools import wraps
from datetime import datetime

from flask import session, redirect, url_for, abort

from database.models import db, SiteUserRole, SiteFactionRole, SiteWarning

# ──────────────────────────────────────────────
# Уровни ролей сайта
# ──────────────────────────────────────────────

ROLE_LEVELS = {
    'developer': 5,
    'owner': 4,
    'admin': 3,
    'moderator': 2,
    'player': 1,
}


def get_user_site_role(steam_id):
    """Возвращает активную роль сайта пользователя."""
    if not steam_id:
        return None

    user_role = (
        SiteUserRole.query
        .filter_by(steam_id=steam_id)
        .filter(SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator', 'player']))
        .order_by(SiteUserRole.assigned_at.desc())
        .first()
    )

    if user_role and not user_role.is_expired():
        return user_role.role_code

    # Если роли нет, по умолчанию — player
    return 'player'


def get_user_faction_role(steam_id):
    """Возвращает роль пользователя в группировке."""
    if not steam_id:
        return None

    faction_role = (
        SiteFactionRole.query
        .filter_by(steam_id=steam_id)
        .order_by(SiteFactionRole.assigned_at.desc())
        .first()
    )

    return faction_role


def get_user_special_roles(steam_id):
    """Возвращает специальные роли пользователя (VIP, Поддержка проекта)."""
    if not steam_id:
        return []

    special_roles = (
        SiteUserRole.query
        .filter_by(steam_id=steam_id)
        .filter(SiteUserRole.role_code.in_(['vip', 'supporter']))
        .all()
    )

    return [r for r in special_roles if not r.is_expired()]


def get_user_warnings(steam_id):
    """Возвращает активные предупреждения пользователя."""
    if not steam_id:
        return []

    warnings = (
        SiteWarning.query
        .filter_by(steam_id=steam_id, is_active=True)
        .order_by(SiteWarning.given_at.desc())
        .all()
    )

    return [w for w in warnings if not w.is_expired()]


def get_user_role_level(steam_id):
    """Возвращает уровень роли пользователя."""
    role = get_user_site_role(steam_id)
    return ROLE_LEVELS.get(role, 1)


def has_role(steam_id, required_role):
    """Проверяет, есть ли у пользователя роль нужного уровня или выше."""
    user_level = get_user_role_level(steam_id)
    required_level = ROLE_LEVELS.get(required_role, 99)
    return user_level >= required_level


# ──────────────────────────────────────────────
# Декораторы
# ──────────────────────────────────────────────

def role_required(required_role):
    """
    Декоратор для проверки роли пользователя.

    Использование:
        @role_required('admin')
        def admin_page():
            ...
    """

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = session.get("user", {})
            steam_id = user.get("steam_id")

            if not steam_id:
                return redirect(url_for("auth.login", next="/admin"))

            if not has_role(steam_id, required_role):
                abort(403)

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def admin_required(view):
    """Декоратор для страниц, доступных только администраторам и выше."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = session.get("user", {})
        steam_id = user.get("steam_id")

        if not steam_id:
            return redirect(url_for("auth.login", next="/admin"))

        if not has_role(steam_id, 'admin'):
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view


def owner_required(view):
    """Декоратор для страниц, доступных только владельцу и разработчику."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = session.get("user", {})
        steam_id = user.get("steam_id")

        if not steam_id:
            return redirect(url_for("auth.login", next="/admin"))

        if not has_role(steam_id, 'owner'):
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view


def is_user_banned(steam_id):
    """Проверяет, забанен ли пользователь."""
    if not steam_id:
        return False

    from database.models import SiteBan

    ban = (
        SiteBan.query
        .filter_by(steam_id=steam_id, is_active=True)
        .order_by(SiteBan.banned_at.desc())
        .first()
    )

    if not ban:
        return False

    if ban.is_expired():
        # Автоматически деактивируем истёкший бан
        ban.is_active = False
        db.session.commit()
        return False

    return True


def get_user_ban_info(steam_id):
    """Возвращает информацию о бане пользователя."""
    if not steam_id:
        return None

    from database.models import SiteBan

    ban = (
        SiteBan.query
        .filter_by(steam_id=steam_id, is_active=True)
        .order_by(SiteBan.banned_at.desc())
        .first()
    )

    if ban and not ban.is_expired():
        return ban

    return None