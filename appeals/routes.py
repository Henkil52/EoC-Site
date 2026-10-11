"""
appeals/routes.py

Система обращений (тикет-система).
"""

from datetime import datetime

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

from auth.decorators import login_required
from auth.roles import role_required, get_user_site_role, ROLE_LEVELS
from database.models import moscow_now
from database.models import (
    db,
    SiteAppeal,
    SiteAppealMessage,
    SiteAppealParticipant,
    Player,
)

from appeals.service import (
    APPEAL_CATEGORIES,
    APPEAL_STATUSES,
    APPEAL_PRIORITIES,
    PLAYER_PRIORITIES,
    is_participant,
    can_view_appeal,
    can_reply_appeal,
    can_manage_appeal,
)


bp = Blueprint(
    "appeals",
    __name__,
    url_prefix="/appeals",
    template_folder="templates",
)


def get_role_level(steam_id):
    """Возвращает уровень роли пользователя."""
    if not steam_id:
        return 0
    role = get_user_site_role(steam_id)
    return ROLE_LEVELS.get(role, 1)


def get_nickname(steam_id):
    """Возвращает никнейм игрока (игровая БД, затем сайт)."""
    if not steam_id:
        return "—"
    player = Player.query.filter_by(SteamID=steam_id).first()
    if player and player.Nickname:
        return player.Nickname
    from database.models import SiteUser
    su = SiteUser.query.get(steam_id)
    if su and su.nickname:
        return su.nickname
    return steam_id


def get_all_users_list():
    """Все пользователи сайта (игра + сайт) для пикера."""
    from database.models import SiteUser
    users = {}
    for p in Player.query.all():
        users[p.SteamID] = p.Nickname or f"Player{p.SteamID[-4:]}"
    for su in SiteUser.query.all():
        if su.steam_id not in users:
            users[su.steam_id] = su.nickname or f"Player{su.steam_id[-4:]}"
    return [
        {"id": sid, "nick": nick}
        for sid, nick in sorted(users.items(), key=lambda x: x[1].lower())
    ]


def get_staff_users_list():
    """Пользователи с ролью модератор+ для пикера исполнителя."""
    from database.models import SiteUser, SiteUserRole
    staff_ids = {
        ur.steam_id for ur in SiteUserRole.query.all()
        if ur.role_code in ('developer', 'owner', 'admin', 'moderator')
    }
    users = {}
    for sid in staff_ids:
        p = Player.query.filter_by(SteamID=sid).first()
        su = SiteUser.query.get(sid)
        users[sid] = (
            (p.Nickname if p and p.Nickname else None)
            or (su.nickname if su else None)
            or f"Player{sid[-4:]}"
        )
    return [
        {"id": sid, "nick": nick}
        for sid, nick in sorted(users.items(), key=lambda x: x[1].lower())
    ]


def parse_participants(raw):
    """Разбирает строку Steam ID через запятую/пробел в список."""
    if not raw:
        return []
    parts = raw.replace(',', ' ').split()
    return [p.strip() for p in parts if p.strip()]


# ══════════════════════════════════════════════════════════════
# СПИСОК МОИХ ОБРАЩЕНИЙ
# ══════════════════════════════════════════════════════════════

@bp.route("/")
@login_required
def index():
    """Список обращений, где пользователь автор или участник."""
    steam_id = session.get("user", {}).get("steam_id")

    # Обращения, где я автор
    authored = SiteAppeal.query.filter_by(author_steam_id=steam_id).all()

    # Обращения, где я участник
    participated_ids = [
        p.appeal_id for p in
        SiteAppealParticipant.query.filter_by(steam_id=steam_id).all()
    ]
    participated = []
    if participated_ids:
        participated = SiteAppeal.query.filter(
            SiteAppeal.id.in_(participated_ids)
        ).all()

    # Объединяем без дубликатов
    seen = set()
    appeals = []
    for a in authored + participated:
        if a.id not in seen:
            seen.add(a.id)
            appeals.append(a)

    appeals.sort(key=lambda x: x.updated_at, reverse=True)

    return render_template(
        "appeals/index.html",
        appeals=appeals,
        statuses=APPEAL_STATUSES,
        priorities=APPEAL_PRIORITIES,
        categories=APPEAL_CATEGORIES,
    )


# ══════════════════════════════════════════════════════════════
# СОЗДАНИЕ ОБРАЩЕНИЯ
# ══════════════════════════════════════════════════════════════

@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Создание обращения."""
    steam_id = session.get("user", {}).get("steam_id")

    if request.method == "POST":
        category = request.form.get("category", "other")
        subject = request.form.get("subject", "").strip()
        content = request.form.get("content", "").strip()
        target_steam_id = request.form.get("target_steam_id", "").strip() or None
        priority = request.form.get("priority", "normal")
        participants_raw = request.form.get("participants", "")

        if category not in APPEAL_CATEGORIES:
            category = "other"

        if priority not in PLAYER_PRIORITIES:
            priority = "normal"

        if not subject or not content:
            flash("Тема и описание не могут быть пустыми.", "error")
            return redirect(url_for("appeals.create"))

        appeal = SiteAppeal(
            author_steam_id=steam_id,
            category=category,
            subject=subject,
            content=content,
            target_steam_id=target_steam_id,
            status='new',
            priority=priority,
            created_at=moscow_now(),
            updated_at=moscow_now(),
        )
        db.session.add(appeal)
        db.session.commit()

        # Добавляем участников
        for pid in parse_participants(participants_raw):
            if pid == steam_id:
                continue
            from database.models import SiteUser
            if not (Player.query.filter_by(SteamID=pid).first() or SiteUser.query.get(pid)):
                flash(f"Пользователь {pid} не найден, пропущен.", "error")
                continue
            if is_participant(appeal.id, pid):
                continue

            db.session.add(SiteAppealParticipant(
                appeal_id=appeal.id,
                steam_id=pid,
                added_by=steam_id,
                added_at=moscow_now(),
            ))

        db.session.commit()

        flash(f"Обращение #{appeal.id} создано.", "success")
        return redirect(url_for("appeals.detail", appeal_id=appeal.id))

    return render_template(
        "appeals/create.html",
        categories=APPEAL_CATEGORIES,
        player_priorities=PLAYER_PRIORITIES,
        priorities=APPEAL_PRIORITIES,
        all_users=get_all_users_list(),
    )


# ══════════════════════════════════════════════════════════════
# ПРОСМОТР ОБРАЩЕНИЯ + ДИАЛОГ
# ══════════════════════════════════════════════════════════════

@bp.route("/<int:appeal_id>")
@login_required
def detail(appeal_id):
    """Просмотр обращения с диалогом."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if not can_view_appeal(appeal, steam_id, role_level):
        abort(403)

    messages = (
        SiteAppealMessage.query
        .filter_by(appeal_id=appeal_id)
        .order_by(SiteAppealMessage.created_at.asc())
        .all()
    )

    participants = (
        SiteAppealParticipant.query
        .filter_by(appeal_id=appeal_id)
        .order_by(SiteAppealParticipant.added_at.asc())
        .all()
    )

    messages_data = [
        {
            'message': m,
            'author_nickname': get_nickname(m.author_steam_id),
        }
        for m in messages
    ]

    participants_data = [
        {
            'participant': p,
            'nickname': get_nickname(p.steam_id),
            'added_by_nickname': get_nickname(p.added_by),
        }
        for p in participants
    ]

    return render_template(
        "appeals/detail.html",
        appeal=appeal,
        messages_data=messages_data,
        participants_data=participants_data,
        categories=APPEAL_CATEGORIES,
        statuses=APPEAL_STATUSES,
        priorities=APPEAL_PRIORITIES,
        can_reply=can_reply_appeal(appeal, steam_id, role_level),
        can_manage=can_manage_appeal(appeal, steam_id, role_level),
        is_moderator=role_level >= 2,
        current_steam_id=steam_id,
        author_nickname=get_nickname(appeal.author_steam_id),
        target_nickname=get_nickname(appeal.target_steam_id) if appeal.target_steam_id else None,
        all_users=get_all_users_list(),
        staff_users=get_staff_users_list(),
    )


# ══════════════════════════════════════════════════════════════
# ОТВЕТ В ДИАЛОГЕ
# ══════════════════════════════════════════════════════════════

@bp.route("/<int:appeal_id>/reply", methods=["POST"])
@login_required
def reply(appeal_id):
    """Ответ в диалоге обращения."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if not can_reply_appeal(appeal, steam_id, role_level):
        flash("Обращение закрыто или нет прав.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    content = request.form.get("content", "").strip()

    if not content:
        flash("Сообщение не может быть пустым.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    is_admin = role_level >= 2

    message = SiteAppealMessage(
        appeal_id=appeal_id,
        author_steam_id=steam_id,
        content=content,
        is_admin_reply=is_admin,
        created_at=moscow_now(),
    )
    db.session.add(message)

    # Автоматическая смена статуса
    if is_admin:
        appeal.status = 'waiting_player'
    else:
        if appeal.status == 'waiting_player':
            appeal.status = 'in_progress'

    appeal.updated_at = moscow_now()
    db.session.commit()

    flash("Ответ добавлен.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))


# ══════════════════════════════════════════════════════════════
# ЗАКРЫТИЕ ОБРАЩЕНИЯ
# ══════════════════════════════════════════════════════════════

@bp.route("/<int:appeal_id>/close", methods=["POST"])
@login_required
def close(appeal_id):
    """Закрыть обращение (автор или модератор+)."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if not can_manage_appeal(appeal, steam_id, role_level):
        abort(403)

    appeal.status = 'closed'
    appeal.closed_by = steam_id
    appeal.closed_at = moscow_now()
    appeal.updated_at = moscow_now()
    db.session.commit()

    flash("Обращение закрыто.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))


# ══════════════════════════════════════════════════════════════
# УЧАСТНИКИ
# ══════════════════════════════════════════════════════════════

@bp.route("/<int:appeal_id>/participant/add", methods=["POST"])
@login_required
def add_participant(appeal_id):
    """Добавить участника (автор или модератор+)."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if not can_manage_appeal(appeal, steam_id, role_level):
        abort(403)

    pid = request.form.get("steam_id", "").strip()

    if not pid:
        flash("Не указан Steam ID.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    if pid == appeal.author_steam_id:
        flash("Автор уже является участником.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    from database.models import SiteUser
    if not (Player.query.filter_by(SteamID=pid).first() or SiteUser.query.get(pid)):
        flash(f"Пользователь {pid} не найден.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    if is_participant(appeal_id, pid):
        flash("Игрок уже добавлен в обращение.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    db.session.add(SiteAppealParticipant(
        appeal_id=appeal_id,
        steam_id=pid,
        added_by=steam_id,
        added_at=moscow_now(),
    ))
    db.session.commit()

    flash(f"Игрок {get_nickname(pid)} добавлен в обращение.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))


@bp.route("/<int:appeal_id>/participant/remove/<int:participant_id>", methods=["POST"])
@login_required
def remove_participant(appeal_id, participant_id):
    """Удалить участника (автор или модератор+)."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)
    participant = SiteAppealParticipant.query.get_or_404(participant_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if not can_manage_appeal(appeal, steam_id, role_level):
        abort(403)

    if participant.appeal_id != appeal_id:
        abort(404)

    db.session.delete(participant)
    db.session.commit()

    flash("Участник удалён из обращения.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))


# ══════════════════════════════════════════════════════════════
# АДМИН: ВСЕ ОБРАЩЕНИЯ
# ══════════════════════════════════════════════════════════════

@bp.route("/admin")
@role_required('moderator')
def admin_list():
    """Список всех обращений для администрации."""
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    priority_filter = request.args.get('priority', '')

    query = SiteAppeal.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    appeals = query.order_by(SiteAppeal.updated_at.desc()).all()

    appeals_data = [
        {
            'appeal': a,
            'author_nickname': get_nickname(a.author_steam_id),
            'messages_count': SiteAppealMessage.query.filter_by(appeal_id=a.id).count(),
        }
        for a in appeals
    ]

    return render_template(
        "appeals/admin_list.html",
        appeals_data=appeals_data,
        statuses=APPEAL_STATUSES,
        categories=APPEAL_CATEGORIES,
        priorities=APPEAL_PRIORITIES,
        status_filter=status_filter,
        category_filter=category_filter,
        priority_filter=priority_filter,
    )


# ══════════════════════════════════════════════════════════════
# АДМИН: СМЕНА СТАТУСА / ПРИОРИТЕТА / ИСПОЛНИТЕЛЯ
# ══════════════════════════════════════════════════════════════

@bp.route("/<int:appeal_id>/update", methods=["POST"])
@role_required('moderator')
def update(appeal_id):
    """Смена статуса / приоритета / исполнителя (модератор+)."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    status = request.form.get("status")
    priority = request.form.get("priority")
    assigned_to = request.form.get("assigned_to", "").strip() or None

    if status and status in APPEAL_STATUSES:
        appeal.status = status
        if status == 'closed':
            appeal.closed_by = session.get("user", {}).get("steam_id")
            appeal.closed_at = moscow_now()
        else:
            appeal.closed_by = None
            appeal.closed_at = None

    if priority and priority in APPEAL_PRIORITIES:
        appeal.priority = priority

    appeal.assigned_to = assigned_to
    appeal.updated_at = moscow_now()
    db.session.commit()

    flash("Обращение обновлено.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))

@bp.route("/<int:appeal_id>/accept", methods=["POST"])
@login_required
def accept(appeal_id):
    """Принять обращение — текущий пользователь становится исполнителем."""
    appeal = SiteAppeal.query.get_or_404(appeal_id)

    steam_id = session.get("user", {}).get("steam_id")
    role_level = get_role_level(steam_id)

    if role_level < 2:
        abort(403)

    if appeal.status == 'closed':
        flash("Обращение уже закрыто.", "error")
        return redirect(url_for("appeals.detail", appeal_id=appeal_id))

    appeal.assigned_to = steam_id
    if appeal.status == 'new':
        appeal.status = 'in_progress'
    appeal.updated_at = moscow_now()
    db.session.commit()

    flash("✅ Вы приняли обращение и назначены исполнителем.", "success")
    return redirect(url_for("appeals.detail", appeal_id=appeal_id))


@bp.app_context_processor
def inject_appeals_helpers():
    """Даёт шаблонам функцию nickname_of(steam_id)."""
    def nickname_of(steam_id):
        return get_nickname(steam_id) if steam_id else None
    return {"nickname_of": nickname_of}
