"""
admin/routes.py

Административная панель сайта.
"""

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from auth.roles import (
    role_required,
    admin_required,
    owner_required,
    get_user_site_role,
    get_user_faction_role,
    get_user_special_roles,
    get_user_warnings,
    ROLE_LEVELS,
)

from database.models import moscow_now
from database.models import (
    db,
    Player,
    SiteRole,
    SiteUserRole,
    SiteFactionRole,
    SiteWarning,
    SiteRoleHistory,
    SiteBan,
)
from admin import env_editor

bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
)


# ══════════════════════════════════════════════════════════════
# ГЛАВНАЯ СТРАНИЦА АДМИНКИ
# ══════════════════════════════════════════════════════════════

@bp.route("/")
@admin_required
def dashboard():
    """Главная страница админки."""
    total_players = Player.query.count()
    total_warnings = SiteWarning.query.filter_by(is_active=True).count()
    total_admins = SiteUserRole.query.filter(
        SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator'])
    ).count()

    return render_template(
        "admin/dashboard.html",
        total_players=total_players,
        total_warnings=total_warnings,
        total_admins=total_admins,
    )


# ══════════════════════════════════════════════════════════════
# ИГРОКИ
# ══════════════════════════════════════════════════════════════

@bp.route("/players")
@admin_required
def players():
    """Список всех игроков: игровики + все, кто авторизовывался на сайте."""
    from datetime import datetime as _dt
    from database.models import SiteUser, SiteUserRole, SiteRole, SiteBan, SiteWarning

    merged = {}

    # 1. Все, кто авторизовывался на сайте
    for su in SiteUser.query.all():
        merged[su.steam_id] = {'site_user': su, 'player': None}

    # 2. Все игроки из игровой БД
    for p in Player.query.all():
        if p.SteamID in merged:
            merged[p.SteamID]['player'] = p
        else:
            merged[p.SteamID] = {'site_user': None, 'player': p}

    players_data = []

    for steam_id, entry in merged.items():
        player = entry['player']
        site_user = entry['site_user']

        nickname = (
            (player.Nickname if player else None)
            or (site_user.nickname if site_user else None)
            or "Без ника"
        )

        # Последняя активность (сервер ИЛИ сайт)
        last_activity = None
        if player is not None and player.LastLogonDate:
            last_activity = player.LastLogonDate
        if site_user is not None and site_user.last_site_login:
            if last_activity is None or site_user.last_site_login > last_activity:
                last_activity = site_user.last_site_login

        # Роль сайта
        site_role = (
            SiteUserRole.query
            .filter_by(steam_id=steam_id)
            .filter(SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator', 'player']))
            .order_by(SiteUserRole.assigned_at.desc())
            .first()
        )

        # Спецроли
        special_roles = (
            SiteUserRole.query
            .filter_by(steam_id=steam_id)
            .filter(SiteUserRole.role_code.in_(['vip', 'supporter']))
            .all()
        )

        # Бан
        ban = (
            SiteBan.query
            .filter_by(steam_id=steam_id, is_active=True)
            .order_by(SiteBan.banned_at.desc())
            .first()
        )

        # Предупреждения
        warnings_count = (
            SiteWarning.query
            .filter_by(steam_id=steam_id, is_active=True)
            .count()
        )

        players_data.append({
            'steam_id': steam_id,
            'nickname': nickname,
            'player': player,
            'site_user': site_user,
            'site_role': site_role,
            'special_roles': [r for r in special_roles if not r.is_expired()],
            'ban': ban,
            'warnings_count': warnings_count,
            'is_site_only': player is None,
            'last_activity': last_activity,
        })

    # Сортировка по последней активности
    players_data.sort(
        key=lambda d: d['last_activity'] or _dt.min,
        reverse=True,
    )

    return render_template(
        "admin/players.html",
        players_data=players_data,
    )

def _player_exists(steam_id):
    """Проверяет, существует ли игрок (в players или site_users)."""
    if Player.query.filter_by(SteamID=steam_id).first():
        return True
    from database.models import SiteUser
    return SiteUser.query.get(steam_id) is not None


@bp.route("/player/<steam_id>")
@admin_required
def player_edit(steam_id):
    """Страница редактирования игрока."""
    player = Player.query.filter_by(SteamID=steam_id).first()

    # Если игрока нет в players, проверяем site_users
    if player is None:
        from database.models import SiteUser
        site_user = SiteUser.query.get(steam_id)
        if site_user is None:
            from flask import abort
            abort(404)
        # Создаём минимальный объект для шаблона
        class MinimalPlayer:
            def __init__(self, su):
                self.SteamID = su.steam_id
                self.Nickname = su.nickname or "Без ника"
                self.RegistrationDate = su.first_site_login
                self.LastLogonDate = su.last_site_login
        player = MinimalPlayer(site_user)
        is_site_only = True
    else:
        is_site_only = False

    user_roles = (
        SiteUserRole.query
        .filter_by(steam_id=steam_id)
        .order_by(SiteUserRole.assigned_at.desc())
        .all()
    )

    all_roles = SiteRole.query.order_by(SiteRole.level.desc()).all()

    ban = (
        SiteBan.query
        .filter_by(steam_id=steam_id, is_active=True)
        .order_by(SiteBan.banned_at.desc())
        .first()
    )

    warnings = (
        SiteWarning.query
        .filter_by(steam_id=steam_id, is_active=True)
        .order_by(SiteWarning.given_at.desc())
        .all()
    )

    return render_template(
        "admin/player_edit.html",
        is_site_only=is_site_only,
        player=player,
        user_roles=user_roles,
        all_roles=all_roles,
        ban=ban,
        warnings=warnings,
    )


@bp.route("/player/<steam_id>/update", methods=["POST"])
@admin_required
def player_update(steam_id):
    """Обновление ролей игрока."""
    player = Player.query.filter_by(SteamID=steam_id).first()

    # Если игрока нет в игровой БД — ищем в site_users ("только сайт")
    is_site_only = False
    if player is None:
        from database.models import SiteUser
        _su = SiteUser.query.get(steam_id)

        if _su is None:
            from flask import abort
            abort(404)

        is_site_only = True

        class _MinimalPlayer:
            SteamID = _su.steam_id
            Nickname = _su.nickname or "Без ника"
            RegistrationDate = _su.first_site_login
            LastLogonDate = _su.last_site_login

        player = _MinimalPlayer()

    role_code = request.form.get("role_code")
    expires_in_days = request.form.get("expires_in_days")

    if not role_code:
        flash("Не указана роль.", "error")
        return redirect(url_for("admin.player_edit", steam_id=steam_id))

    role = SiteRole.query.filter_by(role_code=role_code).first()
    if not role:
        flash("Роль не найдена.", "error")
        return redirect(url_for("admin.player_edit", steam_id=steam_id))

    # Для ролей сайта — удаляем старую
    if role.role_type == 'site':
        SiteUserRole.query.filter_by(
            steam_id=steam_id
        ).filter(
            SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator', 'player'])
        ).delete()

    # Для спецролей — проверяем лимит
    if role.role_type == 'special':
        existing_special = SiteUserRole.query.filter_by(
            steam_id=steam_id
        ).filter(
            SiteUserRole.role_code.in_(['vip', 'supporter'])
        ).count()

        if existing_special >= 2:
            flash("У пользователя уже есть две специальные роли.", "error")
            return redirect(url_for("admin.player_edit", steam_id=steam_id))

    # Срок действия
    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            if days > 0:
                expires_at = moscow_now() + timedelta(days=days)
        except ValueError:
            pass

    current_steam_id = session.get("user", {}).get("steam_id")

    new_role = SiteUserRole(
        steam_id=steam_id,
        role_code=role_code,
        assigned_by=current_steam_id,
        assigned_at=moscow_now(),
        expires_at=expires_at,
    )
    db.session.add(new_role)

    history = SiteRoleHistory(
        steam_id=steam_id,
        role_code=role_code,
        action='assigned',
        changed_by=current_steam_id,
        changed_at=moscow_now(),
        comment=f"Назначена роль {role.display_name}",
    )
    db.session.add(history)

    db.session.commit()

    flash(f"Роль '{role.display_name}' назначена.", "success")
    return redirect(url_for("admin.player_edit", steam_id=steam_id))


@bp.route("/player/<steam_id>/ban", methods=["POST"])
@admin_required
def player_ban(steam_id):
    """Бан игрока (игрового или только-сайт)."""
    if not _player_exists(steam_id):
        from flask import abort
        abort(404)

    reason = request.form.get("reason")
    expires_in_days = request.form.get("expires_in_days")

    if not reason:
        flash("Не указана причина бана.", "error")
        return redirect(url_for("admin.player_edit", steam_id=steam_id))

    # Деактивируем старые активные баны
    SiteBan.query.filter_by(steam_id=steam_id, is_active=True).update({'is_active': False})

    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            if days > 0:
                expires_at = moscow_now() + timedelta(days=days)
        except ValueError:
            pass

    current_steam_id = session.get("user", {}).get("steam_id")

    ban = SiteBan(
        steam_id=steam_id,
        banned_by=current_steam_id,
        reason=reason,
        banned_at=moscow_now(),
        expires_at=expires_at,
        is_active=True,
    )
    db.session.add(ban)
    db.session.commit()

    expires_text = f" на {expires_in_days} дней" if expires_in_days else " перманентно"
    flash(f"Игрок забанен{expires_text}. Причина: {reason}", "success")
    return redirect(url_for("admin.player_edit", steam_id=steam_id))


@bp.route("/player/<steam_id>/unban", methods=["POST"])
@admin_required
def player_unban(steam_id):
    """Разбан игрока (игрового или только-сайт)."""
    if not _player_exists(steam_id):
        from flask import abort
        abort(404)

    SiteBan.query.filter_by(steam_id=steam_id, is_active=True).update({'is_active': False})
    db.session.commit()

    flash("Игрок разбанен.", "success")
    return redirect(url_for("admin.player_edit", steam_id=steam_id))


@bp.route("/player/<steam_id>/warning", methods=["POST"])
@admin_required
def player_warning(steam_id):
    """Добавить предупреждение игроку."""
    player = Player.query.filter_by(SteamID=steam_id).first_or_404()

    reason = request.form.get("reason")

    if not reason:
        flash("Не указана причина предупреждения.", "error")
        return redirect(url_for("admin.player_edit", steam_id=steam_id))

    current_steam_id = session.get("user", {}).get("steam_id")

    warning = SiteWarning(
        steam_id=steam_id,
        given_by=current_steam_id,
        reason=reason,
        given_at=moscow_now(),
        is_active=True,
    )
    db.session.add(warning)
    db.session.commit()

    flash("Предупреждение добавлено.", "success")
    return redirect(url_for("admin.player_edit", steam_id=steam_id))


@bp.route("/player/<steam_id>/warning/remove/<int:warning_id>", methods=["POST"])
@admin_required
def player_warning_remove(steam_id, warning_id):
    """Снять предупреждение."""
    warning = SiteWarning.query.get_or_404(warning_id)
    warning.is_active = False
    db.session.commit()

    flash("Предупреждение снято.", "success")
    return redirect(url_for("admin.player_edit", steam_id=steam_id))


# ══════════════════════════════════════════════════════════════
# УПРАВЛЕНИЕ РОЛЯМИ
# ══════════════════════════════════════════════════════════════

@bp.route("/roles")
@owner_required
def roles():
    """Страница управления ролями."""
    users_with_roles = (
        db.session.query(Player, SiteUserRole)
        .outerjoin(SiteUserRole, Player.SteamID == SiteUserRole.steam_id)
        .all()
    )

    all_roles = SiteRole.query.order_by(SiteRole.level.desc()).all()

    return render_template(
        "admin/roles.html",
        users_with_roles=users_with_roles,
        all_roles=all_roles,
    )


@bp.route("/roles/assign", methods=["POST"])
@owner_required
def assign_role():
    """Назначить роль пользователю."""
    steam_id = request.form.get("steam_id")
    role_code = request.form.get("role_code")
    expires_in_days = request.form.get("expires_in_days")

    if not steam_id or not role_code:
        flash("Не указаны необходимые параметры.", "error")
        return redirect(url_for("admin.roles"))

    role = SiteRole.query.filter_by(role_code=role_code).first()
    if not role:
        flash("Роль не найдена.", "error")
        return redirect(url_for("admin.roles"))

    if role.role_type == 'site':
        SiteUserRole.query.filter_by(
            steam_id=steam_id
        ).filter(
            SiteUserRole.role_code.in_(['developer', 'owner', 'admin', 'moderator', 'player'])
        ).delete()

    if role.role_type == 'special':
        existing_special = SiteUserRole.query.filter_by(
            steam_id=steam_id
        ).filter(
            SiteUserRole.role_code.in_(['vip', 'supporter'])
        ).count()

        if existing_special >= 2:
            flash("У пользователя уже есть две специальные роли.", "error")
            return redirect(url_for("admin.roles"))

    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            if days > 0:
                expires_at = moscow_now() + timedelta(days=days)
        except ValueError:
            pass

    current_steam_id = session.get("user", {}).get("steam_id")

    new_role = SiteUserRole(
        steam_id=steam_id,
        role_code=role_code,
        assigned_by=current_steam_id,
        assigned_at=moscow_now(),
        expires_at=expires_at,
    )
    db.session.add(new_role)

    history = SiteRoleHistory(
        steam_id=steam_id,
        role_code=role_code,
        action='assigned',
        changed_by=current_steam_id,
        changed_at=moscow_now(),
        comment=f"Назначена роль {role.display_name}",
    )
    db.session.add(history)

    db.session.commit()

    flash(f"Роль '{role.display_name}' назначена пользователю {steam_id}.", "success")
    return redirect(url_for("admin.roles"))


@bp.route("/roles/remove/<int:role_id>", methods=["POST"])
@owner_required
def remove_role(role_id):
    """Снять роль с пользователя."""
    user_role = SiteUserRole.query.get_or_404(role_id)

    current_steam_id = session.get("user", {}).get("steam_id")

    history = SiteRoleHistory(
        steam_id=user_role.steam_id,
        role_code=user_role.role_code,
        action='removed',
        changed_by=current_steam_id,
        changed_at=moscow_now(),
        comment="Роль снята",
    )
    db.session.add(history)

    db.session.delete(user_role)
    db.session.commit()

    flash("Роль снята.", "success")
    return redirect(url_for("admin.roles"))


# ══════════════════════════════════════════════════════════════
# ПРЕДУПРЕЖДЕНИЯ
# ══════════════════════════════════════════════════════════════

@bp.route("/warnings")
@admin_required
def warnings():
    """Страница управления предупреждениями."""
    active_warnings = (
        SiteWarning.query
        .filter_by(is_active=True)
        .order_by(SiteWarning.given_at.desc())
        .all()
    )

    return render_template(
        "admin/warnings.html",
        active_warnings=active_warnings,
    )


@bp.route("/warnings/add", methods=["POST"])
@admin_required
def add_warning():
    """Добавить предупреждение пользователю."""
    steam_id = request.form.get("steam_id")
    reason = request.form.get("reason")

    if not steam_id or not reason:
        flash("Не указаны необходимые параметры.", "error")
        return redirect(url_for("admin.warnings"))

    current_steam_id = session.get("user", {}).get("steam_id")

    warning = SiteWarning(
        steam_id=steam_id,
        given_by=current_steam_id,
        reason=reason,
        given_at=moscow_now(),
        is_active=True,
    )

    db.session.add(warning)
    db.session.commit()

    flash(f"Предупреждение добавлено пользователю {steam_id}.", "success")
    return redirect(url_for("admin.warnings"))


@bp.route("/warnings/remove/<int:warning_id>", methods=["POST"])
@admin_required
def remove_warning(warning_id):
    """Снять предупреждение."""
    warning = SiteWarning.query.get_or_404(warning_id)
    warning.is_active = False
    db.session.commit()

    flash("Предупреждение снято.", "success")
    return redirect(url_for("admin.warnings"))

# ══════════════════════════════════════════════════════════════
# РЕДАКТОР .ENV
# ══════════════════════════════════════════════════════════════

@bp.route("/env", methods=["GET"])
@owner_required
def env_editor_view():
    """Страница редактирования .env файла."""
    entries = env_editor.parse_env_file(env_editor.ENV_PATH)
    backups = env_editor.get_backups()

    # Маскируем чувствительные значения для отображения
    display_entries = []
    for entry in entries:
        display_entry = entry.copy()
        if entry.get('key') and not entry.get('is_comment') and not entry.get('is_empty'):
            display_entry['display_value'] = env_editor.mask_value(
                entry['key'], entry['value']
            )
        else:
            display_entry['display_value'] = entry.get('value') or ""
        display_entries.append(display_entry)

    return render_template(
        "admin/env_editor.html",
        entries=display_entries,
        backups=backups,
        env_path=str(env_editor.ENV_PATH),
        env_exists=env_editor.ENV_PATH.exists(),
    )


@bp.route("/env/save", methods=["POST"])
@owner_required
def env_save():
    """Сохранение изменений в .env."""
    current_steam_id = session.get("user", {}).get("steam_id")

    # Получаем текущие значения из файла (для логирования изменений)
    old_entries = {
        e['key']: e['value']
        for e in env_editor.parse_env_file(env_editor.ENV_PATH)
        if e.get('key') and not e.get('is_comment')
    }

    # Создаём бэкап перед сохранением
    backup_path = env_editor.create_backup()

    # Собираем новые значения из формы
    new_entries = []

    # Существующие переменные
    keys = request.form.getlist("env_key[]")
    values = request.form.getlist("env_value[]")
    originals = request.form.getlist("env_original[]")

    for key, value, original in zip(keys, values, originals):
        key = key.strip()
        if not key:
            continue

        value = value.strip()

        # Если это чувствительное поле и значение не менялось
        # (в форме показывались звёздочки) — оставляем оригинал
        if env_editor.is_sensitive(key) and value and '•' in value:
            value = original

        new_entries.append({
            'key': key,
            'value': value,
            'is_comment': False,
            'is_empty': False,
        })

    # Новые переменные (если добавили)
    new_keys = request.form.getlist("new_key[]")
    new_values = request.form.getlist("new_value[]")

    for key, value in zip(new_keys, new_values):
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        # Валидация имени переменной
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
            flash(f"Некорректное имя переменной: {key}", "error")
            return redirect(url_for("admin.env_editor_view"))

        new_entries.append({
            'key': key,
            'value': value,
            'is_comment': False,
            'is_empty': False,
        })

    # Сохраняем
    env_editor.save_env_file(new_entries)

    # Логируем изменения
    new_dict = {e['key']: e['value'] for e in new_entries}

    # Удалённые переменные
    for key in set(old_entries.keys()) - set(new_dict.keys()):
        env_editor.log_change(current_steam_id, "DELETE", key, old_entries[key], "")

    # Изменённые / добавленные
    for key, new_value in new_dict.items():
        old_value = old_entries.get(key, "")
        if key not in old_entries:
            env_editor.log_change(current_steam_id, "ADD", key, "", new_value)
        elif old_value != new_value:
            env_editor.log_change(current_steam_id, "UPDATE", key, old_value, new_value)

    backup_msg = f" Бэкап: {backup_path.name}" if backup_path else ""
    flash(
        f"✅ Файл .env сохранён.{backup_msg}\n"
        f"⚠️ Для применения изменений ПЕРЕЗАПУСТИТЕ сайт!",
        "success"
    )

    return redirect(url_for("admin.env_editor_view"))


@bp.route("/env/restore/<filename>", methods=["POST"])
@owner_required
def env_restore(filename):
    """Восстановление .env из бэкапа."""
    current_steam_id = session.get("user", {}).get("steam_id")

    if env_editor.restore_backup(filename):
        env_editor.log_change(current_steam_id, "RESTORE", f"from:{filename}", "", "")
        flash(
            f"✅ .env восстановлен из {filename}.\n"
            f"⚠️ Для применения изменений ПЕРЕЗАПУСТИТЕ сайт!",
            "success"
        )
    else:
        flash("Бэкап не найден.", "error")

    return redirect(url_for("admin.env_editor_view"))


@bp.route("/env/download", methods=["GET"])
@owner_required
def env_download():
    """Скачать текущий .env файл."""
    from flask import send_file

    if not env_editor.ENV_PATH.exists():
        flash("Файл .env не найден.", "error")
        return redirect(url_for("admin.env_editor_view"))

    return send_file(
        env_editor.ENV_PATH,
        as_attachment=True,
        download_name=".env",
    )
# ══════════════════════════════════════════════════════════════
# ЛОГИ С FTP
# ══════════════════════════════════════════════════════════════

def is_owner_level():
    """Проверяет, является ли пользователь владельцем или разработчиком."""
    from auth.roles import get_user_site_role, ROLE_LEVELS
    steam_id = session.get("user", {}).get("steam_id")
    if not steam_id:
        return False
    role = get_user_site_role(steam_id)
    return ROLE_LEVELS.get(role, 1) >= ROLE_LEVELS.get('owner', 4)


@bp.route("/logs")
@role_required('moderator')
def logs():
    """Страница управления источниками логов."""
    from database.models import SiteLogSource

    sources = SiteLogSource.query.order_by(SiteLogSource.id.asc()).all()

    return render_template(
        "admin/logs.html",
        sources=sources,
        is_owner=is_owner_level(),
    )


@bp.route("/logs/source/add", methods=["POST"])
@owner_required
def logs_source_add():
    """Добавить источник логов (только developer/owner)."""
    from database.models import SiteLogSource

    name = request.form.get("name", "").strip()
    ftp_path = request.form.get("ftp_path", "").strip()

    if not name or not ftp_path:
        flash("Название и путь не могут быть пустыми.", "error")
        return redirect(url_for("admin.logs"))

    if not ftp_path.startswith("/"):
        flash("Путь должен начинаться с /", "error")
        return redirect(url_for("admin.logs"))

    # Проверка дубликатов
    existing = SiteLogSource.query.filter_by(ftp_path=ftp_path).first()
    if existing:
        flash("Источник с таким путём уже существует.", "error")
        return redirect(url_for("admin.logs"))

    source = SiteLogSource(
        name=name,
        ftp_path=ftp_path,
        added_by=session.get("user", {}).get("steam_id"),
        created_at=moscow_now(),
        is_active=True,
    )
    db.session.add(source)
    db.session.commit()

    flash(f"Источник «{name}» добавлен.", "success")
    return redirect(url_for("admin.logs"))


@bp.route("/logs/source/delete/<int:source_id>", methods=["POST"])
@owner_required
def logs_source_delete(source_id):
    """Удалить источник логов (только developer/owner)."""
    from database.models import SiteLogSource

    source = SiteLogSource.query.get_or_404(source_id)
    db.session.delete(source)
    db.session.commit()

    flash(f"Источник «{source.name}» удалён.", "success")
    return redirect(url_for("admin.logs"))


@bp.route("/logs/<int:source_id>")
@role_required('moderator')
def logs_browser(source_id):
    """Просмотр файлов логов на FTP."""
    import ftplib
    import os
    import ssl
    from database.models import SiteLogSource

    # ── Локальные функции FTP (вместо отдельного модуля) ──────

    def get_ftp_config():
        return {
            'host': os.getenv("FTP_HOST", "").strip(),
            'port': int(os.getenv("FTP_PORT", "21").strip() or "21"),
            'username': os.getenv("FTP_USERNAME", "").strip(),
            'password': os.getenv("FTP_PASSWORD", "").strip(),
            'use_ssl': os.getenv("FTP_USE_SSL", "True").strip().lower() in ('true', '1', 'yes'),
            'verify_cert': os.getenv("ssl_verify_cert", "False").strip().lower() in ('true', '1', 'yes'),
        }

    def ftp_connect(cfg):
        if not cfg['host']:
            raise Exception("FTP_HOST не задан в .env")

        if cfg['use_ssl']:
            ctx = ssl.create_default_context()
            if not cfg['verify_cert']:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            ftp = ftplib.FTP_TLS(context=ctx)
        else:
            ftp = ftplib.FTP()

        ftp.connect(cfg['host'], cfg['port'], timeout=30)

        if cfg['username']:
            ftp.login(cfg['username'], cfg['password'])
        else:
            ftp.login()

        if cfg['use_ssl']:
            ftp.prot_p()

        return ftp

    def parse_list_line(line):
        line = line.rstrip()
        if not line:
            return None

        # Unix формат
        if line[0] in 'dl-bcps':
            parts = line.split(None, 8)
            if len(parts) >= 9:
                size = int(parts[4]) if parts[4].isdigit() else 0
                return {'name': parts[8], 'is_dir': parts[0].startswith('d'), 'size': size}
            return None

        # Windows формат
        parts = line.split(None, 3)
        if len(parts) >= 4:
            token3 = parts[2]
            name = parts[3]

            if token3.upper() == '<DIR>':
                return {'name': name, 'is_dir': True, 'size': 0}

            size = int(token3.replace(',', '')) if token3.replace(',', '').isdigit() else 0
            return {'name': name, 'is_dir': False, 'size': size}

        return None

    def list_remote(ftp, path):
        lines = []
        ftp.retrlines(f"LIST {path}", lines.append)

        items = []
        for line in lines:
            parsed = parse_list_line(line)
            if not parsed or parsed['name'] in ('.', '..'):
                continue
            parsed['path'] = f"{path.rstrip('/')}/{parsed['name']}"
            items.append(parsed)

        items.sort(key=lambda x: (not x['is_dir'], x['name']))
        return items

    def read_remote_file(ftp, path, max_lines=500):
        lines = []
        ftp.retrlines(f"RETR {path}", lines.append)
        total = len(lines)
        return {
            'total_lines': total,
            'shown_lines': lines[-max_lines:],
            'truncated': total > max_lines,
        }

    # ── Основной код маршрута ─────────────────────────────────

    source = SiteLogSource.query.get_or_404(source_id)

    base = source.ftp_path.rstrip('/')
    current_dir = request.args.get("dir", base)
    file_path = request.args.get("file")

    # Защита от выхода за пределы источника
    if not current_dir.startswith(base):
        current_dir = base
    if file_path and not file_path.startswith(base + "/"):
        file_path = None

    items = []
    file_content = None
    error = None

    try:
        cfg = get_ftp_config()
        ftp = ftp_connect(cfg)
        try:
            items = list_remote(ftp, current_dir)
            if file_path:
                file_content = read_remote_file(ftp, file_path)
        finally:
            ftp.quit()
    except Exception as e:
        error = str(e)

    # Родительская папка (не выше базовой)
    parent_dir = None
    if current_dir != base:
        parent_dir = current_dir.rsplit('/', 1)[0]
        if not parent_dir.startswith(base):
            parent_dir = base

    return render_template(
        "admin/logs_browser.html",
        source=source,
        items=items,
        current_dir=current_dir,
        parent_dir=parent_dir,
        file_path=file_path,
        file_content=file_content,
        error=error,
    )