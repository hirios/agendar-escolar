from flask import Blueprint

director_bp = Blueprint("director", __name__, template_folder="../../templates/director")

from . import routes  # noqa: F401, E402
