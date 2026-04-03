from flask import render_template, current_app
from .grade_service import GradeService
from .attendance_service import AttendanceService
from ..repositories.user_repository import UserRepository
from ..repositories.class_repository import ClassRepository


class ReportService:
    def __init__(self):
        self.grade_service = GradeService()
        self.att_service = AttendanceService()
        self.user_repo = UserRepository()
        self.class_repo = ClassRepository()

    def get_boletim_data(self, student_id, school_year_id):
        student = self.user_repo.get_by_id(student_id)
        boletim, periods = self.grade_service.get_boletim(student_id, school_year_id)
        attendance = self.att_service.get_summary_for_student(student_id, school_year_id)
        gpa = self.grade_service.get_student_gpa(student_id, school_year_id)
        return {
            "student": student,
            "boletim": boletim,
            "periods": periods,
            "attendance": attendance,
            "gpa": gpa,
        }

    def render_boletim_html(self, student_id, school_year_id):
        data = self.get_boletim_data(student_id, school_year_id)
        return render_template("reports/boletim.html", **data)

    def generate_boletim_pdf(self, student_id, school_year_id):
        try:
            from weasyprint import HTML
            html_content = self.render_boletim_html(student_id, school_year_id)
            return HTML(string=html_content, base_url=current_app.root_path).write_pdf()
        except ImportError:
            raise RuntimeError("WeasyPrint não instalado. Execute: pip install weasyprint")
