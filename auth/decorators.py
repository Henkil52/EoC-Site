from functools import wraps

from flask import redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.path))

        return view(*args, **kwargs)

    return wrapped_view