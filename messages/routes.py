"""
messages/routes.py

Система личных сообщений (ЛС).
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)

from auth.decorators import login_required
from database.models import (
    db, SiteMessage, SitePrivacySettings, SiteUser, Player,
)


bp = Blueprint(
    "messages",
    __name__,
    url_prefix="/messages",
    template_folder="templates",
)


def get_nickname(steam_id):
    """Ник игрока (игровая БД, затем сайт)."""
    if not steam_id:
        return "—"
    p = Player.query.filter_by(SteamID=steam_id).first()
    if p and p.Nickname:
        return p.Nickname
    su = SiteUser.query.get(steam_id)
    if su and su.nickname:
        return su.nickname
    return f"Player{steam_id[-4:]}"


def messages_allowed(steam_id):
    """Разрешены ли пользователю ЛС (настройка приватности)."""
    s = SitePrivacySettings.query.get(steam_id)
    return s.allow_messages if s else True


def get_all_users_list():
    """Все пользователи сайта для пикера."""
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


@bp.app_context_processor
def inject_messages_helpers():
    """Хелперы для всех шаблонов: бейдж непрочитанных + проверка приватности."""

    def unread_messages():
        user = session.get("user") or {}
        sid = user.get("steam_id")
        if not sid:
            return 0
        return SiteMessage.query.filter_by(
            recipient_steam_id=sid, is_read=False
        ).count()

    def can_message(steam_id):
        if not steam_id:
            return False
        me = (session.get("user") or {}).get("steam_id")
        if steam_id == me:
            return False
        return messages_allowed(steam_id)

    return {
        "unread_messages": unread_messages,
        "can_message": can_message,
    }


@bp.route("/")
@login_required
def index():
    """Список всех моих чатов."""
    my_id = (session.get("user") or {}).get("steam_id")

    messages = (
        SiteMessage.query
        .filter(
            (SiteMessage.sender_steam_id == my_id) |
            (SiteMessage.recipient_steam_id == my_id)
        )
        .order_by(SiteMessage.created_at.asc())
        .all()
    )

    chats = {}
    for m in messages:
        other = m.recipient_steam_id if m.sender_steam_id == my_id else m.sender_steam_id
        chat = chats.setdefault(other, {"user_id": other, "last": m, "unread": 0})
        chat["last"] = m
        if m.recipient_steam_id == my_id and not m.is_read:
            chat["unread"] += 1

    chats_list = []
    for chat in chats.values():
        chat["nickname"] = get_nickname(chat["user_id"])
        chats_list.append(chat)

    chats_list.sort(key=lambda c: c["last"].created_at, reverse=True)

    return render_template(
        "messages/index.html",
        chats=chats_list,
        all_users=get_all_users_list(),
    )


@bp.route("/chat/<steam_id>")
@login_required
def chat(steam_id):
    """Диалог с пользователем."""
    my_id = (session.get("user") or {}).get("steam_id")

    if steam_id == my_id:
        flash("Нельзя открыть чат с самим собой.", "error")
        return redirect(url_for("messages.index"))

    messages = (
        SiteMessage.query
        .filter(
            ((SiteMessage.sender_steam_id == my_id) & (SiteMessage.recipient_steam_id == steam_id)) |
            ((SiteMessage.sender_steam_id == steam_id) & (SiteMessage.recipient_steam_id == my_id))
        )
        .order_by(SiteMessage.created_at.asc())
        .all()
    )

    # Помечаем входящие прочитанными
    changed = False
    for m in messages:
        if m.recipient_steam_id == my_id and not m.is_read:
            m.is_read = True
            changed = True
    if changed:
        db.session.commit()

    return render_template(
        "messages/chat.html",
        messages=messages,
        other_id=steam_id,
        other_nickname=get_nickname(steam_id),
        my_id=my_id,
        can_write=messages_allowed(steam_id),
    )


@bp.route("/send", methods=["POST"])
@bp.route("/send/<steam_id>", methods=["POST"])
@login_required
def send(steam_id=None):
    """Отправка сообщения (из чата или новая переписка)."""
    my_id = (session.get("user") or {}).get("steam_id")
    recipient = steam_id or request.form.get("recipient", "").strip()

    back = request.referrer or url_for("messages.index")

    if not recipient:
        flash("Не выбран получатель.", "error")
        return redirect(back)

    if recipient == my_id:
        flash("Нельзя писать сообщения самому себе.", "error")
        return redirect(back)

    # Получатель должен существовать
    if not (Player.query.filter_by(SteamID=recipient).first() or SiteUser.query.get(recipient)):
        flash("Пользователь не найден.", "error")
        return redirect(back)

    # ── Приватность: запрет ЛС ──────────────────────────────
    if not messages_allowed(recipient):
        flash("🔒 Пользователь запретил личные сообщения в настройках профиля.", "error")
        return redirect(back)

    content = request.form.get("content", "").strip()
    if not content:
        flash("Сообщение не может быть пустым.", "error")
        return redirect(back)

    db.session.add(SiteMessage(
        sender_steam_id=my_id,
        recipient_steam_id=recipient,
        content=content,
    ))
    db.session.commit()

    return redirect(url_for("messages.chat", steam_id=recipient))


@bp.route("/api/chat/<steam_id>")
@login_required
def api_chat(steam_id):
    """JSON: новые сообщения чата (для живого обновления)."""
    from flask import jsonify, render_template_string

    my_id = (session.get("user") or {}).get("steam_id")
    after = request.args.get("after", 0, type=int)

    msgs = (
        SiteMessage.query
        .filter(
            ((SiteMessage.sender_steam_id == my_id) & (SiteMessage.recipient_steam_id == steam_id)) |
            ((SiteMessage.sender_steam_id == steam_id) & (SiteMessage.recipient_steam_id == my_id))
        )
        .filter(SiteMessage.id > after)
        .order_by(SiteMessage.id.asc())
        .all()
    )

    changed = False
    out = []
    for m in msgs:
        if m.recipient_steam_id == my_id and not m.is_read:
            m.is_read = True
            changed = True
        out.append({
            "id": m.id,
            "out": m.sender_steam_id == my_id,
            "html": render_template_string("{{ c|bb }}", c=m.content),
            "time": m.created_at.strftime("%d.%m.%Y %H:%M"),
            "avatar": get_avatar_url(m.sender_steam_id),
            "nick": get_nickname(m.sender_steam_id),
        })

    if changed:
        db.session.commit()

    return jsonify(out)


@bp.route("/api/unread")
@login_required
def api_unread():
    """JSON: число непрочитанных сообщений (для бейджа)."""
    from flask import jsonify

    my_id = (session.get("user") or {}).get("steam_id")
    count = SiteMessage.query.filter_by(
        recipient_steam_id=my_id, is_read=False
    ).count()

    return jsonify({"count": count})


def get_avatar_url(steam_id):
    """Аватар пользователя: кастомный → Steam → None."""
    from database.models import SitePlayerAvatar
    rec = SitePlayerAvatar.query.get(steam_id)
    if rec:
        from flask import url_for as _url_for
        return _url_for("static", filename="avatars/" + rec.filename)
    su = SiteUser.query.get(steam_id)
    if su and su.avatar_url:
        return su.avatar_url
    try:
        from steam_utils import fetch_steam_avatar
        url = fetch_steam_avatar(steam_id)
        if url:
            return url
    except Exception:
        pass
    return None


@bp.app_context_processor
def inject_messages_avatar_helpers():
    """Даёт шаблонам avatar_url_for() и nickname_for()."""
    return {
        "avatar_url_for": get_avatar_url,
        "nickname_for": get_nickname,
    }
