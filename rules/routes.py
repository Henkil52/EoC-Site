"""
rules/routes.py

Раздел правил: публичный просмотр и админ-управление.
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
)

from auth.roles import admin_required
from database.models import moscow_now
from database.models import db, SiteRulesSection, SiteRule
from rules.service import record_change


bp = Blueprint(
    "rules",
    __name__,
    url_prefix="/rules",
    template_folder="templates",
)


def get_sections_data():
    """Возвращает разделы с правилами для шаблонов."""
    sections = (
        SiteRulesSection.query
        .order_by(SiteRulesSection.order.asc(), SiteRulesSection.id.asc())
        .all()
    )

    sections_data = []
    for section in sections:
        rules = (
            SiteRule.query
            .filter_by(section_id=section.id)
            .order_by(SiteRule.order.asc(), SiteRule.id.asc())
            .all()
        )
        sections_data.append({
            'section': section,
            'rules': rules,
        })

    return sections_data


def get_current_steam_id():
    return session.get("user", {}).get("steam_id")


def is_admin():
    return session.get("user", {}).get("is_admin", False)


# ══════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ ПРОСМОТР
# ══════════════════════════════════════════════════════════════

@bp.route("/")
def index():
    """Страница правил."""
    from flask import render_template, session, redirect, url_for
    from database.models import SiteRulesSection, SiteRule

    user = session.get("user")
    if not user or not user.get("steam_id"):
        return redirect(url_for("auth.login"))

    is_admin = False
    try:
        from auth.roles import has_role
        is_admin = bool(has_role(session.get("user", {}).get("steam_id"), "admin"))
    except Exception:
        is_admin = False

    sections = SiteRulesSection.query.order_by(SiteRulesSection.order).all()
    sections_data = [
        {"section": s, "rules": s.rules.order_by(SiteRule.order).all()}
        for s in sections
    ]

    return render_template("rules/index.html", is_admin=is_admin, sections_data=sections_data)


@bp.route("/admin")
@admin_required
def admin():
    """Страница управления правилами."""
    return render_template(
        "rules/admin.html",
        sections_data=get_sections_data(),
    )


# ══════════════════════════════════════════════════════════════
# РАЗДЕЛЫ
# ══════════════════════════════════════════════════════════════

@bp.route("/section/create", methods=["POST"])
@admin_required
def section_create():
    """Создать раздел."""
    title = request.form.get("title", "").strip()

    if not title:
        flash("Название раздела не может быть пустым.", "error")
        return redirect(url_for("rules.admin"))

    max_order = db.session.query(db.func.max(SiteRulesSection.order)).scalar() or 0

    section = SiteRulesSection(
        title=title,
        order=max_order + 1,
        created_at=moscow_now(),
        updated_at=moscow_now(),
    )
    db.session.add(section)
    db.session.flush()

    record_change(
        action='section_create',
        target_type='section',
        section_title=title,
        old_text=None,
        new_text=title,
        changed_by=get_current_steam_id(),
        target_id=section.id,
    )

    db.session.commit()

    flash(f"Раздел «{title}» создан.", "success")
    return redirect(url_for("rules.admin"))


@bp.route("/section/<int:section_id>/edit", methods=["POST"])
@admin_required
def section_edit(section_id):
    """Переименовать раздел."""
    section = SiteRulesSection.query.get_or_404(section_id)

    new_title = request.form.get("title", "").strip()

    if not new_title:
        flash("Название раздела не может быть пустым.", "error")
        return redirect(url_for("rules.admin"))

    old_title = section.title

    if old_title != new_title:
        section.title = new_title
        section.updated_at = moscow_now()

        record_change(
            action='section_update',
            target_type='section',
            section_title=new_title,
            old_text=old_title,
            new_text=new_title,
            changed_by=get_current_steam_id(),
            target_id=section.id,
        )

        db.session.commit()

        flash(f"Раздел переименован в «{new_title}».", "success")
    else:
        flash("Название не изменилось.", "info")

    return redirect(url_for("rules.admin"))


@bp.route("/section/<int:section_id>/delete", methods=["POST"])
@admin_required
def section_delete(section_id):
    """Удалить раздел и все его правила."""
    section = SiteRulesSection.query.get_or_404(section_id)

    title = section.title

    # Удаляем правила раздела
    SiteRule.query.filter_by(section_id=section_id).delete()

    db.session.delete(section)
    db.session.flush()

    record_change(
        action='section_delete',
        target_type='section',
        section_title=title,
        old_text=title,
        new_text=None,
        changed_by=get_current_steam_id(),
        target_id=section_id,
    )

    db.session.commit()

    flash(f"Раздел «{title}» удалён.", "success")
    return redirect(url_for("rules.admin"))


# ══════════════════════════════════════════════════════════════
# ПРАВИЛА
# ══════════════════════════════════════════════════════════════

@bp.route("/section/<int:section_id>/rule/create", methods=["POST"])
@admin_required
def rule_create(section_id):
    """Добавить правило в раздел."""
    section = SiteRulesSection.query.get_or_404(section_id)

    text = request.form.get("text", "").strip()

    if not text:
        flash("Текст правила не может быть пустым.", "error")
        return redirect(url_for("rules.admin"))

    max_order = (
        db.session.query(db.func.max(SiteRule.order))
        .filter_by(section_id=section_id)
        .scalar()
    ) or 0

    rule = SiteRule(
        section_id=section_id,
        text=text,
        order=max_order + 1,
        created_at=moscow_now(),
        updated_at=moscow_now(),
    )
    db.session.add(rule)
    db.session.flush()

    section.updated_at = moscow_now()

    record_change(
        action='create',
        target_type='rule',
        section_title=section.title,
        old_text=None,
        new_text=text,
        changed_by=get_current_steam_id(),
        target_id=rule.id,
    )

    db.session.commit()

    flash("Правило добавлено.", "success")
    return redirect(url_for("rules.admin"))


@bp.route("/rule/<int:rule_id>/edit", methods=["POST"])
@admin_required
def rule_edit(rule_id):
    """Изменить правило."""
    rule = SiteRule.query.get_or_404(rule_id)

    new_text = request.form.get("text", "").strip()

    if not new_text:
        flash("Текст правила не может быть пустым.", "error")
        return redirect(url_for("rules.admin"))

    old_text = rule.text

    if old_text != new_text:
        rule.text = new_text
        rule.updated_at = moscow_now()
        rule.section.updated_at = moscow_now()

        record_change(
            action='update',
            target_type='rule',
            section_title=rule.section.title,
            old_text=old_text,
            new_text=new_text,
            changed_by=get_current_steam_id(),
            target_id=rule.id,
        )

        db.session.commit()

        flash("Правило изменено.", "success")
    else:
        flash("Текст не изменился.", "info")

    return redirect(url_for("rules.admin"))


@bp.route("/rule/<int:rule_id>/delete", methods=["POST"])
@admin_required
def rule_delete(rule_id):
    """Удалить правило."""
    rule = SiteRule.query.get_or_404(rule_id)

    old_text = rule.text
    section_title = rule.section.title

    rule.section.updated_at = moscow_now()

    db.session.delete(rule)
    db.session.flush()

    record_change(
        action='delete',
        target_type='rule',
        section_title=section_title,
        old_text=old_text,
        new_text=None,
        changed_by=get_current_steam_id(),
        target_id=rule_id,
    )

    db.session.commit()

    flash("Правило удалено.", "success")
    return redirect(url_for("rules.admin"))