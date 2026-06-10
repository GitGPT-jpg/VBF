"""Auth routes — DB-backed login/logout with throttling."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import UserMixin, login_required, login_user, logout_user

from app.services import user_service

bp = Blueprint("auth", __name__)


class WebUser(UserMixin):
    """flask-login adapter around the DB user."""

    def __init__(self, user_id: str, username: str, role: str,
                 display_name: str = "") -> None:
        self.id = user_id
        self.username = username
        self.role = role
        self.display_name = display_name or username


def load_web_user(user_id: str) -> WebUser | None:
    user = user_service.get_user(user_id)
    if not user:
        return None
    return WebUser(user.id, user.username, user.role, user.display_name)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = user_service.authenticate(
            username, password, remote_addr=request.remote_addr or "")
        if user:
            login_user(WebUser(user.id, user.username, user.role,
                               user.display_name), remember=True)
            return redirect(url_for("pages.index"))
        return render_template("login.html", error_key="error_invalid_credentials")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
