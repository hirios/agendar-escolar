from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ...services.auth_service import AuthService
from ...services.notification_service import NotificationService
from ...extensions import limiter

auth_service = AuthService()
notification_service = NotificationService()


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = auth_service.authenticate(email, password)
        if user:
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            return redirect(next_page or url_for(f"{user.role}.dashboard"))
        flash("Email ou senha incorretos.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu com sucesso.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pwd = request.form.get("current_password", "")
        new_pwd = request.form.get("new_password", "")
        confirm_pwd = request.form.get("confirm_password", "")

        if new_pwd != confirm_pwd:
            flash("A nova senha e a confirmação não coincidem.", "error")
        elif len(new_pwd) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "error")
        else:
            try:
                auth_service.change_password(current_user, current_pwd, new_pwd)
                flash("Senha alterada com sucesso!", "success")
                return redirect(url_for(f"{current_user.role}.dashboard"))
            except ValueError as e:
                flash(str(e), "error")

    return render_template("auth/change_password.html")


@auth_bp.route("/notifications/")
@login_required
def notifications():
    notifications = notification_service.get_for_user(current_user.id, limit=50)
    notification_service.mark_all_read(current_user.id)
    return render_template("notifications/index.html", notifications=notifications)
