"""
info/routes.py

Страницы "О сайте" и "Справка".
"""

from flask import Blueprint, render_template

bp = Blueprint(
    "info",
    __name__,
    url_prefix="/info",
    template_folder="templates",
)


@bp.route("/about")
def about():
    """Страница о сайте."""
    return render_template("info/about.html")


@bp.route("/help")
def help_page():
    """Страница справки."""
    return render_template("info/help.html")
