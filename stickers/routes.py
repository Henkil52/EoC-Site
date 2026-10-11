"""
stickers/routes.py

Стикеры: три категории с разными правами доступа.
"""

import os
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session

from auth.decorators import login_required
from auth.roles import admin_required

bp = Blueprint(
    "stickers",
    __name__,
    url_prefix="/stickers",
    template_folder="templates",
)

STICKERS_DIR = Path(__file__).resolve().parent.parent / "static" / "stickers"

CATEGORIES = [
    {"key": "common", "icon": "🌐", "title": "Общие стикеры",
     "hint": "Доступны всем пользователям."},
    {"key": "vip", "icon": "⭐", "title": "VIP стикеры",
     "hint": "Доступны игрокам с VIP-статусом и администрации."},
    {"key": "admin", "icon": "🛡", "title": "Админ-стикеры",
     "hint": "Доступны только администрации."},
]


def _current_sid():
    return session.get("user", {}).get("steam_id")


def _is_admin():
    """Админ и выше (admin/owner/developer)."""
    try:
        from auth.roles import has_role
        return bool(has_role(_current_sid(), "admin"))
    except Exception:
        return False


def _is_vip():
    """VIP или админ."""
    try:
        if _is_admin():
            return True
        from auth.roles import get_user_special_roles
        return any(
            getattr(r, "role_code", "") == "vip"
            for r in get_user_special_roles(_current_sid())
        )
    except Exception:
        return False


def list_stickers(category):
    """Сканирует папку категории и возвращает список стикеров."""
    folder = STICKERS_DIR / category
    folder.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(folder.glob("*.webp")):
        items.append({
            "filename": f.name,
            "url": url_for("static", filename=f"stickers/{category}/{f.name}"),
            "size": f.stat().st_size,
        })
    return items


def available_categories():
    """Категории, доступные текущему пользователю."""
    cats = ["common"]
    if _is_vip():
        cats.append("vip")
    if _is_admin():
        cats.append("admin")
    return cats


@bp.route("/admin")
@login_required
@admin_required
def admin():
    """Панель управления стикерами (все категории)."""
    cats = []
    for c in CATEGORIES:
        cats.append({**c, "stickers": list_stickers(c["key"])})
    return render_template("stickers/admin.html", categories=cats)


@bp.route("/delete", methods=["POST"])
@login_required
@admin_required
def delete():
    """Удаляет стикер из папки и с сайта."""
    category = request.form.get("category", "common")
    if category not in ("common", "vip", "admin"):
        flash("❌ Неизвестная категория", "error")
        return redirect(url_for("stickers.admin"))

    filename = request.form.get("filename", "")
    safe = os.path.basename(filename)
    path = STICKERS_DIR / category / safe

    if safe and path.exists() and path.suffix.lower() == ".webp":
        path.unlink()
        flash(f"🗑 Стикер {safe} удалён", "success")
    else:
        flash("❌ Стикер не найден", "error")

    return redirect(url_for("stickers.admin"))


@bp.route("/api/my")
@login_required
def api_my():
    """Стикеры, доступные текущему пользователю (для чата)."""
    cats = available_categories()
    out = []
    for cat in cats:
        for s in list_stickers(cat):
            s["category"] = cat
            out.append(s)
    return jsonify({"stickers": out})
