"""
auth/routes.py

Маршруты авторизации через Steam.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .steam import (
    build_steam_login_url,
    extract_steam_id,
    fetch_steam_user,
    safe_next_url,
    verify_openid_response,
)

from .game_data import get_game_player_data

from .roles import (
    get_user_site_role,
    get_user_faction_role,
    get_user_special_roles,
    get_user_warnings,
    is_user_banned,
    get_user_ban_info,
    ROLE_LEVELS,
)

from database.models import moscow_now
from database.models import SiteRole

from leaderboard.service import get_player_leader_badges


bp = Blueprint(
    "auth",
    __name__,
    template_folder="templates",
)


@bp.app_context_processor
def inject_current_user():
    """
    Передаёт данные текущего пользователя во все шаблоны.
    Также обновляет роли и бейджи из БД при каждом запросе,
    чтобы изменения применялись без перелогина.
    """
    user = session.get("user")

    if user and user.get("steam_id"):
        steam_id = user["steam_id"]

        try:
            # ── Роль сайта ────────────────────────────────────
            site_role_code = get_user_site_role(steam_id)
            site_role = SiteRole.query.filter_by(role_code=site_role_code).first()

            user["site_role"] = site_role_code
            user["site_role_display"] = site_role.display_name if site_role else "Сталкер"
            user["site_role_icon"] = site_role.icon if site_role else "🚶"
            user["site_role_color"] = site_role.color if site_role else "#888888"
            user["is_admin"] = ROLE_LEVELS.get(site_role_code, 1) >= ROLE_LEVELS.get('admin', 3)

            # ── Роль в группировке ────────────────────────────
            faction_role = get_user_faction_role(steam_id)
            if faction_role:
                faction_role_ref = SiteRole.query.filter_by(
                    role_code=faction_role.role_code
                ).first()

                user["faction_role"] = {
                    "role_code": faction_role.role_code,
                    "display_name": faction_role_ref.display_name if faction_role_ref else faction_role.role_code,
                    "icon": faction_role_ref.icon if faction_role_ref else "🔹",
                    "faction_id": faction_role.faction_id,
                    "faction_name": faction_role.faction.Name if faction_role.faction else None,
                }
            else:
                user["faction_role"] = None

            # ── Специальные роли ──────────────────────────────
            special_roles = get_user_special_roles(steam_id)
            user["special_roles"] = []
            for sr in special_roles:
                sr_ref = SiteRole.query.filter_by(role_code=sr.role_code).first()
                if sr_ref:
                    user["special_roles"].append({
                        "role_code": sr.role_code,
                        "display_name": sr_ref.display_name,
                        "icon": sr_ref.icon,
                        "color": sr_ref.color,
                    })

            # ── Лидерские бейджи ──────────────────────────────
            user["leader_badges"] = get_player_leader_badges(steam_id)

            # ── Предупреждения ────────────────────────────────
            warnings = get_user_warnings(steam_id)
            user["warnings_count"] = len(warnings)

            session["user"] = user
            session.modified = True

        except Exception as e:
            print(f"Ошибка получения ролей: {e}")

    return {
        "current_user": user
    }


@bp.route("/login")
def login():
    """Страница входа."""
    if session.get("user"):
        return redirect(url_for("profile.index"))

    # Сохраняем next, если он передан
    next_url = safe_next_url(request.args.get("next"))
    if next_url:
        session["next_url"] = next_url

    return redirect("/")


@bp.route("/login/steam")
def steam_login():
    """Перенаправление на Steam OpenID."""
    if session.get("user"):
        return redirect(url_for("profile.index"))

    if not session.get("next_url"):
        session["next_url"] = safe_next_url(request.args.get("next"))

    return redirect(build_steam_login_url())


@bp.route("/login/steam/callback")
def steam_callback():
    """Обработка ответа от Steam OpenID."""
    if not verify_openid_response(request.args):
        flash("Steam не подтвердил авторизацию.", "error")
        return redirect(url_for("auth.login"))

    steam_id = extract_steam_id(request.args)

    if not steam_id:
        flash("Не удалось получить Steam ID.", "error")
        return redirect(url_for("auth.login"))

    # ── Проверка бана ────────────────────────────────────────
    if is_user_banned(steam_id):

        ban_info = get_user_ban_info(steam_id)

        return render_template("auth/banned.html", ban=ban_info), 403

    # Получаем данные из Steam API (ник, аватар)
    user = fetch_steam_user(steam_id)
    # ── Записываем/обновляем пользователя сайта ─────────────
    try:
        from database.models import db, SiteUser
        site_user = SiteUser.query.get(steam_id)
        if site_user:
            site_user.nickname = user.get("nickname")
            site_user.avatar_url = user.get("avatar_url")
            site_user.profile_url = user.get("profile_url")
            site_user.last_site_login = moscow_now()
            site_user.login_count = (site_user.login_count or 0) + 1
        else:
            site_user = SiteUser(
                steam_id=steam_id,
                nickname=user.get("nickname"),
                avatar_url=user.get("avatar_url"),
                profile_url=user.get("profile_url"),
            )
            db.session.add(site_user)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи site_users: {e}")


    # Проверяем локальную БД на наличие игровых данных
    game_data = get_game_player_data(steam_id)

    if game_data:
        # Обновляем никнейм на игровой
        user["nickname"] = game_data.get("game_nickname") or user.get("nickname")
        user["game_nickname"] = game_data.get("game_nickname")
        user["has_game_data"] = True
    else:
        user["has_game_data"] = False

    # Получаем роль сайта и бейджи
    try:
        site_role_code = get_user_site_role(steam_id)
        site_role = SiteRole.query.filter_by(role_code=site_role_code).first()

        user["site_role"] = site_role_code
        user["site_role_display"] = site_role.display_name if site_role else "Сталкер"
        user["site_role_icon"] = site_role.icon if site_role else "🚶"
        user["site_role_color"] = site_role.color if site_role else "#888888"
        user["is_admin"] = ROLE_LEVELS.get(site_role_code, 1) >= ROLE_LEVELS.get('admin', 3)

        # Роль в группировке
        faction_role = get_user_faction_role(steam_id)
        if faction_role:
            faction_role_ref = SiteRole.query.filter_by(
                role_code=faction_role.role_code
            ).first()

            user["faction_role"] = {
                "role_code": faction_role.role_code,
                "display_name": faction_role_ref.display_name if faction_role_ref else faction_role.role_code,
                "icon": faction_role_ref.icon if faction_role_ref else "🔹",
                "faction_id": faction_role.faction_id,
                "faction_name": faction_role.faction.Name if faction_role.faction else None,
            }
        else:
            user["faction_role"] = None

        # Специальные роли
        special_roles = get_user_special_roles(steam_id)
        user["special_roles"] = []
        for sr in special_roles:
            sr_ref = SiteRole.query.filter_by(role_code=sr.role_code).first()
            if sr_ref:
                user["special_roles"].append({
                    "role_code": sr.role_code,
                    "display_name": sr_ref.display_name,
                    "icon": sr_ref.icon,
                    "color": sr_ref.color,
                })

        # Лидерские бейджи
        user["leader_badges"] = get_player_leader_badges(steam_id)

        # Предупреждения
        warnings = get_user_warnings(steam_id)
        user["warnings_count"] = len(warnings)

    except Exception as e:
        print(f"Ошибка получения ролей при входе: {e}")
        user["site_role"] = "player"
        user["is_admin"] = False

    session["user"] = user

    flash(f"Вы вошли через Steam: {user.get('nickname')}", "success")

    next_url = session.pop("next_url", None) or url_for("profile.index")

    return redirect(next_url)


@bp.route("/logout")
def logout():
    """Выход из аккаунта."""
    session.clear()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("auth.login"))