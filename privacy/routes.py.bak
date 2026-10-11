"""
privacy/routes.py

Настройки профиля: приватность + аватар и баннер.
"""

from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session,
)

from auth.decorators import login_required
from database.models import moscow_now
from database.models import (
    db, SitePrivacySettings, SitePlayerAvatar, SitePlayerBanner,
)


bp = Blueprint(
    "privacy",
    __name__,
    url_prefix="/privacy",
    template_folder="templates",
)

SETTING_FIELDS = {
    'show_profile': 'Показывать профиль другим игрокам',
    'show_online': 'Показывать онлайн',
    'allow_messages': 'Разрешить личные сообщения',
}


def get_settings(steam_id):
    settings = SitePrivacySettings.query.get(steam_id)
    if not settings:
        settings = SitePrivacySettings(steam_id=steam_id)
        db.session.add(settings)
        db.session.commit()
    return settings


@bp.route("/")
@login_required
def index():
    """Страница настроек профиля."""
    steam_id = (session.get("user") or {}).get("steam_id")
    settings = get_settings(steam_id)

    avatar = SitePlayerAvatar.query.get(steam_id)
    banner = SitePlayerBanner.query.get(steam_id)

    privacy_settings = [
        {
            'key': key,
            'label': label,
            'enabled': getattr(settings, key),
        }
        for key, label in SETTING_FIELDS.items()
    ]

    return render_template(
        "privacy/index.html",
        privacy_settings=privacy_settings,
        custom_avatar=(
            url_for("static", filename="avatars/" + avatar.filename)
            if avatar else None
        ),
        custom_banner=(
            url_for("static", filename="banners/" + banner.filename)
            if banner else None
        ),
        steam_user=session.get("user") or {},
    )


@bp.route("/toggle", methods=["POST"])
@login_required
def toggle():
    """Переключение настройки приватности."""
    steam_id = (session.get("user") or {}).get("steam_id")
    key = request.form.get("key")

    if key not in SETTING_FIELDS:
        flash("Неизвестная настройка.", "error")
        return redirect(url_for("privacy.index"))

    settings = get_settings(steam_id)
    new_value = not getattr(settings, key)
    setattr(settings, key, new_value)
    settings.updated_at = moscow_now()
    db.session.commit()

    state = "включено" if new_value else "выключено"
    flash(f"«{SETTING_FIELDS[key]}» — {state}.", "success")
    return redirect(url_for("privacy.index"))
