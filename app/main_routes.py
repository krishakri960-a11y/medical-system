from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import User

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("staff.dashboard"))
    return render_template("landing.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if not user or not user.is_active:
            flash("Invalid credentials or inactive account.", "danger")
        elif not user.check_password(password):
            flash("Invalid credentials.", "danger")
        else:
            login_user(user, remember=True)
            nxt = request.args.get("next")
            if user.role == "admin":
                return redirect(nxt or url_for("admin.dashboard"))
            return redirect(nxt or url_for("staff.dashboard"))
    return render_template("login.html")


@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
