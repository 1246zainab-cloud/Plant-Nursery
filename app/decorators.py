from functools import wraps

from flask import abort, redirect, url_for, flash, request
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.admin_login"))
        if current_user.user_type not in ("admin", "staff"):
            abort(403)
        if current_user.user_type == "staff" and not current_user.is_active:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.admin_login"))
        if current_user.user_type != "admin" or not getattr(current_user, "is_super", False):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def staff_permission(permission_key):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.admin_login"))
            if current_user.user_type == "admin":
                return f(*args, **kwargs)
            if current_user.user_type == "staff":
                if current_user.has_permission(permission_key):
                    return f(*args, **kwargs)
                abort(403)
            abort(403)
        return decorated
    return decorator


def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        if current_user.user_type != "customer":
            abort(403)
        return f(*args, **kwargs)
    return decorated
