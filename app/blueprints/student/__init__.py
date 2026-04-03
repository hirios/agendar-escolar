from flask import Blueprint

student_bp = Blueprint("student", __name__, template_folder="../../templates/student")

from . import routes  # noqa: F401, E402
