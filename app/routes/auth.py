from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.activity_log import log_activity
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            log_activity("login", "auth", f"User {username} logged in", username, user=user)
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    if current_user.is_authenticated:
        log_activity("logout", "auth", f"User {current_user.username} logged out", current_user.username)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
