from flask import render_template, send_file, abort, request
from flask_login import login_required, current_user
from io import BytesIO
from . import reports_bp
from ...services.report_service import ReportService
from ...repositories.user_repository import UserRepository
from ...models.parent_student import ParentStudent
from ...utils.helpers import active_school_year
from ...extensions import db

report_service = ReportService()
user_repo = UserRepository()


def _can_view_student_report(student_id):
    """Verifica se o usuário atual pode ver o relatório deste aluno."""
    if current_user.role in ("director", "teacher"):
        return True
    if current_user.role == "student" and current_user.id == student_id:
        return True
    if current_user.role == "parent":
        link = db.session.execute(
            db.select(ParentStudent).where(
                ParentStudent.parent_id == current_user.id,
                ParentStudent.student_id == student_id,
            )
        ).scalar_one_or_none()
        return link is not None
    return False


@reports_bp.route("/boletim/<int:student_id>")
@login_required
def boletim_preview(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    if not _can_view_student_report(student_id):
        abort(403)
    school_year = active_school_year()
    if not school_year:
        abort(404)
    data = report_service.get_boletim_data(student_id, school_year.id)
    return render_template("reports/boletim.html", **data, preview=True)


@reports_bp.route("/boletim/<int:student_id>/pdf")
@login_required
def boletim_pdf(student_id):
    student = user_repo.get_by_id(student_id)
    if not student or student.role != "student":
        abort(404)
    if not _can_view_student_report(student_id):
        abort(403)
    school_year = active_school_year()
    if not school_year:
        abort(404)
    try:
        pdf_bytes = report_service.generate_boletim_pdf(student_id, school_year.id)
        student = user_repo.get_by_id(student_id)
        filename = f"boletim_{student.name.replace(' ', '_')}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except RuntimeError as e:
        abort(500, description=str(e))
