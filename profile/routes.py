"""
profile/routes.py

Страница профиля игрока.
Данные берутся из локальной SQLite БД.
"""

from flask import Blueprint, render_template, session, current_app, flash, redirect, url_for

from auth.decorators import login_required
from auth.game_data import get_game_player_data
from database.models import moscow_now
from database.models import (
    db,
    Player,
    PlayerStats,
    Faction,
    FactionRank,
    FactionMember,
    PlayerAchievement,
    SiteAppeal,
    PlayerExtendedStats,
    PlayerWeaponStats,

    SiteBadge,)


bp = Blueprint(
    "profile",
    __name__,
    template_folder="templates",
)


def get_player_from_db(steam_id):
    """Получает полные данные игрока из локальной БД."""

    try:
        player_data = (
            db.session.query(
                Player,
                PlayerStats,
                Faction,
                FactionRank,
            )
            .outerjoin(PlayerStats, Player.SteamID == PlayerStats.SteamID)
            .outerjoin(FactionMember, Player.SteamID == FactionMember.MEMBER_ID)
            .outerjoin(Faction, FactionMember.FACTION_ID == Faction.ID)
            .outerjoin(FactionRank, FactionMember.RankID == FactionRank.RankID)
            .filter(Player.SteamID == steam_id)
            .first()
        )

        if not player_data:
            return None

        player, stats, faction, rank = player_data

        # Достижения
        achievements = (
            PlayerAchievement.query
            .filter_by(SteamID=steam_id, IsAchieved=True)
            .all()
        )

        # Расширенная статистика (из FTP)
        extended = PlayerExtendedStats.query.filter_by(SteamID=steam_id).first()

        # Статистика по оружию
        weapons = (
            PlayerWeaponStats.query
            .filter_by(SteamID=steam_id)
            .order_by(PlayerWeaponStats.Kills.desc())
            .all()
        )

        return {
            "player": player,
            "stats": stats,
            "faction": faction,
            "rank": rank,
            "achievements_count": len(achievements),
            "achievements": achievements,
            "extended": extended,
            "weapons": weapons,
        }

    except Exception as e:
        current_app.logger.error(f"Ошибка получения данных игрока: {e}")
        return None


def get_player_appeals(steam_id):
    """Возвращает все обращения игрока (для администрации)."""
    appeals = (
        SiteAppeal.query
        .filter_by(author_steam_id=steam_id)
        .order_by(SiteAppeal.created_at.desc())
        .all()
    )
    return appeals


def is_current_user_moderator():
    """Проверяет, является ли текущий пользователь модератором+."""
    from auth.roles import get_user_site_role, ROLE_LEVELS

    current_steam_id = session.get("user", {}).get("steam_id")
    if not current_steam_id:
        return False

    role = get_user_site_role(current_steam_id)
    return ROLE_LEVELS.get(role, 1) >= ROLE_LEVELS.get('moderator', 2)

def get_profile_roles_data(steam_id):
    """
    Собирает данные о ролях и бейджах ЛЮБОГО игрока
    для отображения в профиле.
    """
    from auth.roles import (
        get_user_site_role,
        get_user_faction_role,
        get_user_special_roles,
        get_user_warnings,
    )
    from leaderboard.service import get_player_leader_badges
    from database.models import SiteRole

    data = {}

    # ── Роль сайта ────────────────────────────────────────────
    site_role_code = get_user_site_role(steam_id)
    site_role = SiteRole.query.filter_by(role_code=site_role_code).first()

    data["site_role"] = site_role_code
    data["site_role_display"] = site_role.display_name if site_role else "Сталкер"
    data["site_role_icon"] = site_role.icon if site_role else "🚶"
    data["site_role_color"] = site_role.color if site_role else "#888888"

    # ── Роль в группировке ────────────────────────────────────
    faction_role = get_user_faction_role(steam_id)
    if faction_role:
        faction_role_ref = SiteRole.query.filter_by(
            role_code=faction_role.role_code
        ).first()

        data["faction_role"] = {
            "role_code": faction_role.role_code,
            "display_name": faction_role_ref.display_name if faction_role_ref else faction_role.role_code,
            "icon": faction_role_ref.icon if faction_role_ref else "🔹",
            "faction_id": faction_role.faction_id,
            "faction_name": faction_role.faction.Name if faction_role.faction else None,
        }
    else:
        data["faction_role"] = None

    # ── Специальные роли ──────────────────────────────────────
    special_roles = get_user_special_roles(steam_id)
    data["special_roles"] = []
    for sr in special_roles:
        sr_ref = SiteRole.query.filter_by(role_code=sr.role_code).first()
        if sr_ref:
            data["special_roles"].append({
                "role_code": sr.role_code,
                "display_name": sr_ref.display_name,
                "icon": sr_ref.icon,
                "color": sr_ref.color,
            })

    # ── Лидерские бейджи ──────────────────────────────────────
    data["leader_badges"] = get_player_leader_badges(steam_id)

    # ── Предупреждения ────────────────────────────────────────
    data["warnings_count"] = len(get_user_warnings(steam_id))

    return data

def get_player_logs_data(steam_id, tail=100):
    """
    Читает локальные логи игрока (logs_players/<steam_id>/).
    Возвращает последние tail строк по каждому типу.
    """
    from sync.player_logs_sync import LOGS_DIR, LOG_TYPES, LOG_LABELS

    result = []
    user_dir = LOGS_DIR / steam_id

    if not user_dir.exists():
        return result

    for log_type in LOG_TYPES:
        path = user_dir / log_type

        if not path.exists():
            continue

        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue

        if not lines:
            continue

        result.append({
            'type': log_type,
            'label': LOG_LABELS.get(log_type, log_type),
            'lines': lines[-tail:],
            'total': len(lines),
            'truncated': len(lines) > tail,
        })

    return result

def update_session_nickname(steam_id):
    """Обновляет никнейм в сессии на игровой из локальной БД."""
    game_data = get_game_player_data(steam_id)

    if game_data and game_data.get("game_nickname"):
        session["user"]["nickname"] = game_data["game_nickname"]
        session["user"]["game_nickname"] = game_data["game_nickname"]
        session["user"]["has_game_data"] = True
        session.modified = True


@bp.route("/my")
@login_required
def index():
    steam_user = session.get("user", {})
    steam_id = steam_user.get("steam_id")

    # Обновляем никнейм на игровой при каждом заходе в профиль
    if steam_id:
        update_session_nickname(steam_id)
        steam_user = session.get("user", {})

    game_data = None
    if steam_id:
        game_data = get_player_from_db(steam_id)

    # Обращения игрока — видны только модераторам+
    is_moderator = is_current_user_moderator()
    player_appeals = get_player_appeals(steam_id) if is_moderator else []
    player_logs = get_player_logs_data(steam_id) if is_moderator else []

    # Значки игрока для витрины
    player_badges = []
    try:
        player_obj = Player.query.get(steam_id)
        if player_obj:
            player_badges = list(player_obj.badges.order_by(SiteBadge.name).all())
    except Exception:
        player_badges = []

    return render_template(
        "profile/index.html",
        steam_user=steam_user,
        game_data=game_data,
        is_moderator=is_moderator,
        player_appeals=player_appeals,
        player_logs=player_logs,
        player_badges=player_badges,
    )


@bp.route("/profile")
@login_required
def my_profile():
    steam_user = session.get("user", {})
    steam_id = steam_user.get("steam_id")

    # Обновляем никнейм на игровой при каждом заходе в профиль
    if steam_id:
        update_session_nickname(steam_id)
        steam_user = session.get("user", {})

    game_data = None
    if steam_id:
        game_data = get_player_from_db(steam_id)

    is_moderator = is_current_user_moderator()
    player_appeals = get_player_appeals(steam_id) if is_moderator else []
    player_logs = get_player_logs_data(steam_id) if is_moderator else []

    # Значки игрока для витрины
    player_badges = []
    try:
        player_obj = Player.query.get(steam_id)
        if player_obj:
            player_badges = list(player_obj.badges.order_by(SiteBadge.name).all())
    except Exception:
        player_badges = []

    return render_template(
        "profile/index.html",
        steam_user=steam_user,
        game_data=game_data,
        is_moderator=is_moderator,
        player_appeals=player_appeals,
        player_logs=player_logs,
        player_badges=player_badges,
    )


@bp.route("/view/<steam_id>")
def view_profile(steam_id):
    """Просмотр профиля другого игрока."""
    steam_user = session.get("user", {})
    current_steam_id = steam_user.get("steam_id")

    # Просмотр чужих профилей доступен всем авторизованным

    game_data = get_player_from_db(steam_id)

    # Если игрока нет в игровой БД — ищем в site_users ("только сайт")
    is_site_only = False
    if not game_data:
        from database.models import SiteUser
        _su = SiteUser.query.get(steam_id)

        if _su is None:
            flash("Игрок не найден в базе данных.", "error")
            return redirect(url_for("profile.index"))

        is_site_only = True
        player_nickname = _su.nickname or "Без ника"
    else:
        player_nickname = game_data["player"].Nickname if game_data["player"].Nickname else "Без ника"

    # Собираем роли и бейджи просматриваемого игрока
    roles_data = get_profile_roles_data(steam_id)

    profile_user = {
        "steam_id": steam_id,
        "nickname": player_nickname,
        **roles_data,
    }

    is_moderator = is_current_user_moderator()
    player_appeals = get_player_appeals(steam_id) if is_moderator else []
    player_logs = get_player_logs_data(steam_id) if is_moderator else []

    # Значки игрока для витрины
    player_badges = []
    try:
        player_obj = Player.query.get(steam_id)
        if player_obj:
            player_badges = list(player_obj.badges.order_by(SiteBadge.name).all())
    except Exception:
        player_badges = []

    return render_template(
        "profile/index.html",
        is_site_only=is_site_only,
        steam_user=profile_user,
        game_data=game_data,
        is_moderator=is_moderator,
        player_appeals=player_appeals,
        player_logs=player_logs,
        player_badges=player_badges,
    )

# ══════════════════════════════════════════════════════════════
# АВАТАРЫ: загрузка и смена
# ══════════════════════════════════════════════════════════════

AVATAR_ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5 МБ


def _avatar_dir():
    import os as _os
    from flask import current_app
    d = _os.path.join(current_app.static_folder, "avatars")
    _os.makedirs(d, exist_ok=True)
    return d


@bp.context_processor
def inject_avatar_helpers():
    """Даёт шаблонам функцию custom_avatar_url(steam_id)."""
    def custom_avatar_url(steam_id):
        if not steam_id:
            return None
        from database.models import SitePlayerAvatar
        rec = SitePlayerAvatar.query.get(steam_id)
        if rec:
            from flask import url_for
            return url_for("static", filename="avatars/" + rec.filename)
        return None
    return {"custom_avatar_url": custom_avatar_url}


@bp.route("/avatar/upload", methods=["POST"])
def avatar_upload():
    """Загрузка кастомного аватара (только свой профиль)."""
    import os as _os
    from datetime import datetime
    from flask import request, redirect, url_for, flash, session
    from werkzeug.utils import secure_filename
    from database.models import db, SitePlayerAvatar

    steam_id = (session.get("user") or {}).get("steam_id")
    if not steam_id:
        flash("Требуется вход через Steam.", "error")
        return redirect(url_for("auth.login"))

    file = request.files.get("avatar")
    back = request.referrer or url_for("profile.my_profile")

    if not file or not file.filename:
        flash("Файл не выбран.", "error")
        return redirect(back)

    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""

    if ext not in AVATAR_ALLOWED:
        flash("Недопустимый формат. Разрешены: PNG, JPG, GIF, WEBP.", "error")
        return redirect(back)

    file.stream.seek(0, _os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)

    if size > AVATAR_MAX_SIZE:
        flash("Файл слишком большой (максимум 5 МБ).", "error")
        return redirect(back)

    filename = f"{steam_id}.{ext}"
    target_dir = _avatar_dir()

    # Удаляем старые файлы с другими расширениями
    for old in _os.listdir(target_dir):
        if old.startswith(steam_id + ".") and old != filename:
            try:
                _os.remove(_os.path.join(target_dir, old))
            except OSError:
                pass

    file.save(_os.path.join(target_dir, filename))

    rec = SitePlayerAvatar.query.get(steam_id)
    if not rec:
        rec = SitePlayerAvatar(steam_id=steam_id)
        db.session.add(rec)
    rec.filename = filename
    rec.updated_at = moscow_now()
    db.session.commit()

    flash(" Аватар обновлён!", "success")
    return redirect(back)


@bp.route("/avatar/reset", methods=["POST"])
def avatar_reset():
    """Возврат к аватару Steam."""
    import os as _os
    from flask import request, redirect, url_for, flash, session
    from database.models import db, SitePlayerAvatar

    steam_id = (session.get("user") or {}).get("steam_id")
    back = request.referrer or url_for("profile.my_profile")

    rec = SitePlayerAvatar.query.get(steam_id)
    if rec:
        target_dir = _avatar_dir()
        try:
            _os.remove(_os.path.join(target_dir, rec.filename))
        except OSError:
            pass
        db.session.delete(rec)
        db.session.commit()
        flash("↩️ Возвращён аватар Steam.", "info")
    else:
        flash("Кастомный аватар не установлен.", "info")

    return redirect(back)


# ══════════════════════════════════════════════════════════════
# БАННЕРЫ: загрузка и смена (рекомендуемый размер 1600x400)
# ══════════════════════════════════════════════════════════════

BANNER_ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
BANNER_MAX_SIZE = 8 * 1024 * 1024  # 8 МБ


def _banner_dir():
    import os as _os
    from flask import current_app
    d = _os.path.join(current_app.static_folder, "banners")
    _os.makedirs(d, exist_ok=True)
    return d


@bp.context_processor
def inject_banner_helpers():
    """Даёт шаблонам функцию custom_banner_url(steam_id)."""
    def custom_banner_url(steam_id):
        if not steam_id:
            return None
        from database.models import SitePlayerBanner
        rec = SitePlayerBanner.query.get(steam_id)
        if rec:
            from flask import url_for
            return url_for("static", filename="banners/" + rec.filename)
        return None
    return {"custom_banner_url": custom_banner_url}


@bp.route("/banner/upload", methods=["POST"])
def banner_upload():
    """Загрузка кастомного баннера (только свой профиль)."""
    import os as _os
    from datetime import datetime
    from flask import request, redirect, url_for, flash, session
    from werkzeug.utils import secure_filename
    from database.models import db, SitePlayerBanner

    steam_id = (session.get("user") or {}).get("steam_id")
    if not steam_id:
        flash("Требуется вход через Steam.", "error")
        return redirect(url_for("auth.login"))

    file = request.files.get("banner")
    back = request.referrer or url_for("profile.my_profile")

    if not file or not file.filename:
        flash("Файл не выбран.", "error")
        return redirect(back)

    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""

    if ext not in BANNER_ALLOWED:
        flash("Недопустимый формат. Разрешены: PNG, JPG, GIF, WEBP.", "error")
        return redirect(back)

    file.stream.seek(0, _os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)

    if size > BANNER_MAX_SIZE:
        flash("Файл слишком большой (максимум 8 МБ).", "error")
        return redirect(back)

    filename = f"{steam_id}.{ext}"
    target_dir = _banner_dir()

    for old in _os.listdir(target_dir):
        if old.startswith(steam_id + ".") and old != filename:
            try:
                _os.remove(_os.path.join(target_dir, old))
            except OSError:
                pass

    file.save(_os.path.join(target_dir, filename))

    rec = SitePlayerBanner.query.get(steam_id)
    if not rec:
        rec = SitePlayerBanner(steam_id=steam_id)
        db.session.add(rec)
    rec.filename = filename
    rec.updated_at = moscow_now()
    db.session.commit()

    flash("🖼️ Баннер обновлён!", "success")
    return redirect(back)


@bp.route("/banner/reset", methods=["POST"])
def banner_reset():
    """Возврат к стандартному градиентному баннеру."""
    import os as _os
    from flask import request, redirect, url_for, flash, session
    from database.models import db, SitePlayerBanner

    steam_id = (session.get("user") or {}).get("steam_id")
    back = request.referrer or url_for("profile.my_profile")

    rec = SitePlayerBanner.query.get(steam_id)
    if rec:
        target_dir = _banner_dir()
        try:
            _os.remove(_os.path.join(target_dir, rec.filename))
        except OSError:
            pass
        db.session.delete(rec)
        db.session.commit()
        flash("↩️ Возвращён стандартный баннер.", "info")
    else:
        flash("Кастомный баннер не установлен.", "info")

    return redirect(back)


# ══════════════════════════════════════════════════════════════
# ГЛАВНАЯ СТРАНИЦА: умный редирект
# ══════════════════════════════════════════════════════════════

@bp.route("/")
def home_redirect():
    """Главная: авторизованные -> /news/, остальные -> /login."""
    user = session.get("user")
    if user and user.get("steam_id"):
        return redirect(url_for("news.index"))
    return render_template("auth/login.html")
