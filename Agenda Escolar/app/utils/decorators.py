from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    """
    Decorator de RBAC. Uso:
        @role_required("director")
        @role_required("teacher", "director")
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask import redirect, url_for
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def director_required(f):
    return role_required("director")(f)


def teacher_required(f):
    return role_required("teacher", "director")(f)


def student_required(f):
    return role_required("student")(f)


def parent_required(f):
    return role_required("parent")(f)
