from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session
)
from flask_login import login_user, logout_user, current_user

from app.extensions import db
from app.models import Customer, Admin, Staff
from app.utils import slugify

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Public login is for customers only. Admin/staff use /admin-login.
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        if not identifier or not password:
            flash("Please enter your credentials.", "error")
        else:
            user = db.session.execute(
                db.select(Customer).where(
                    (Customer.username == identifier) | (Customer.email == identifier)
                )
            ).scalar_one_or_none()
            if user and user.check_password(password) and getattr(user, "is_active", True):
                login_user(user)
                flash(f"Welcome back, {getattr(user, 'full_name', None) or getattr(user, 'username', 'user')}!", "success")
                return _redirect_after_login(user)
            flash("Invalid credentials or account disabled.", "error")
    return render_template("auth/login.html")


@bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    # Dedicated login for admin and staff accounts only.
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        if not identifier or not password:
            flash("Please enter your credentials.", "error")
        else:
            user = (
                db.session.execute(
                    db.select(Admin).where(
                        (Admin.username == identifier) | (Admin.email == identifier)
                    )
                ).scalar_one_or_none()
                or db.session.execute(
                    db.select(Staff).where(
                        (Staff.username == identifier) | (Staff.email == identifier)
                    )
                ).scalar_one_or_none()
            )
            if user and user.check_password(password) and getattr(user, "is_active", True):
                login_user(user)
                flash(f"Welcome back, {getattr(user, 'full_name', None) or getattr(user, 'username', 'user')}!", "success")
                return _redirect_after_login(user)
            flash("Invalid admin/staff credentials or account disabled.", "error")
    return render_template("auth/admin_login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()

        errors = []
        if not username or not email or not password:
            errors.append("All required fields must be filled.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if db.session.execute(db.select(Customer).where(Customer.username == username)).scalar_one_or_none():
            errors.append("Username already taken.")
        if db.session.execute(db.select(Customer).where(Customer.email == email)).scalar_one_or_none():
            errors.append("Email already registered.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            customer = Customer(
                username=username, email=email, full_name=full_name, phone=phone,
            )
            customer.set_password(password)
            db.session.add(customer)
            db.session.commit()
            login_user(customer)
            flash("Account created successfully. Welcome!", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/register.html")


@bp.route("/logout")
def logout():
    logout_user()
    session.pop("cart", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


def _redirect_after_login(user):
    if user.user_type == "admin":
        return redirect(url_for("admin.dashboard"))
    if user.user_type == "staff":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("customer.profile"))
