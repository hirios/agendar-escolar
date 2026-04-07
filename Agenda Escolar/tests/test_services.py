"""
test_services.py — Testes unitários de GradeService e AttendanceService.
"""
import pytest
from helpers import (
    make_user, make_school_year, make_subject, make_class,
    make_class_subject,
)
from app.models import ClassStudent
from app.services.grade_service import GradeService
from app.services.attendance_service import AttendanceService
from datetime import date


@pytest.fixture
def base(db):
    teacher = make_user(db, email="t@svc.com", role="teacher")
    student = make_user(db, email="s@svc.com", role="student")
    sy, periods = make_school_year(db)
    subject = make_subject(db)
    class_ = make_class(db, sy.id)
    cs = make_class_subject(db, class_.id, subject.id, teacher.id, sy.id)
    db.session.add(ClassStudent(class_id=class_.id, student_id=student.id))
    db.session.commit()
    return {
        "teacher": teacher,
        "student": student,
        "sy": sy,
        "periods": periods,
        "subject": subject,
        "class_": class_,
        "cs": cs,
    }


class TestGradeService:
    def test_save_grade(self, base):
        svc = GradeService()
        period = base["periods"][0]
        grade = svc.save_grade(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=8.0,
        )
        assert grade is not None
        assert float(grade.score) == 8.0

    def test_save_grade_upsert(self, base):
        """Salvar nota duas vezes deve atualizar, não duplicar."""
        svc = GradeService()
        period = base["periods"][0]
        kwargs = dict(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=6.0,
        )
        svc.save_grade(**kwargs)
        updated = svc.save_grade(**{**kwargs, "score": 9.0})
        assert float(updated.score) == 9.0

    def test_save_bulk_grades(self, base):
        svc = GradeService()
        period = base["periods"][0]
        entries = [
            {
                "student_id": base["student"].id,
                "class_subject_id": base["cs"].id,
                "grade_period_id": period.id,
                "grade_type": "prova",
                "score": 7.5,
            },
            {
                "student_id": base["student"].id,
                "class_subject_id": base["cs"].id,
                "grade_period_id": period.id,
                "grade_type": "trabalho",
                "score": 8.5,
            },
        ]
        saved = svc.save_bulk_grades(entries)
        assert len(saved) == 2

    def test_get_boletim_returns_dict(self, base):
        svc = GradeService()
        period = base["periods"][0]
        svc.save_grade(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=7.0,
        )
        boletim, periods = svc.get_boletim(base["student"].id, base["sy"].id)
        assert isinstance(boletim, dict)
        assert isinstance(periods, list)
        assert len(periods) == 4  # 4 bimestres criados no make_school_year

    def test_get_student_gpa_none_if_no_grades(self, base):
        svc = GradeService()
        gpa = svc.get_student_gpa(base["student"].id, base["sy"].id)
        assert gpa is None

    def test_get_student_gpa_with_grades(self, base):
        svc = GradeService()
        period = base["periods"][0]
        svc.save_grade(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=8.0,
        )
        gpa = svc.get_student_gpa(base["student"].id, base["sy"].id)
        assert gpa is not None
        assert gpa == 8.0

    def test_status_aprovado_above_threshold(self, base):
        svc = GradeService()
        period = base["periods"][0]
        svc.save_grade(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=7.0,
        )
        boletim, _ = svc.get_boletim(base["student"].id, base["sy"].id)
        subject_name = base["subject"].name
        assert boletim[subject_name]["status"] == "aprovado"

    def test_status_reprovado_below_threshold(self, base):
        svc = GradeService()
        period = base["periods"][0]
        svc.save_grade(
            student_id=base["student"].id,
            class_subject_id=base["cs"].id,
            grade_period_id=period.id,
            grade_type="prova",
            score=3.0,
        )
        boletim, _ = svc.get_boletim(base["student"].id, base["sy"].id)
        subject_name = base["subject"].name
        assert boletim[subject_name]["status"] == "reprovado"


class TestAttendanceService:
    def test_take_attendance_creates_session(self, base):
        svc = AttendanceService()
        session, records = svc.take_attendance(
            class_id=base["class_"].id,
            class_subject_id=base["cs"].id,
            teacher_id=base["teacher"].id,
            session_date=date(2026, 3, 1),
            records=[{"student_id": base["student"].id, "status": "present"}],
        )
        assert session is not None
        assert session.id is not None
        assert len(records) == 1

    def test_take_attendance_absent_record(self, base):
        svc = AttendanceService()
        session, records = svc.take_attendance(
            class_id=base["class_"].id,
            class_subject_id=base["cs"].id,
            teacher_id=base["teacher"].id,
            session_date=date(2026, 3, 2),
            records=[{"student_id": base["student"].id, "status": "absent"}],
        )
        assert records[0].status == "absent"

    def test_take_attendance_idempotent(self, base):
        """Fazer chamada duas vezes na mesma data/aula deve atualizar, não duplicar sessão."""
        svc = AttendanceService()
        common_args = dict(
            class_id=base["class_"].id,
            class_subject_id=base["cs"].id,
            teacher_id=base["teacher"].id,
            session_date=date(2026, 3, 3),
            records=[{"student_id": base["student"].id, "status": "present"}],
        )
        sess1, _ = svc.take_attendance(**common_args)
        common_args["records"] = [{"student_id": base["student"].id, "status": "absent"}]
        sess2, records2 = svc.take_attendance(**common_args)
        assert sess1.id == sess2.id
        assert records2[0].status == "absent"

    def test_get_summary_for_student(self, base):
        svc = AttendanceService()
        svc.take_attendance(
            class_id=base["class_"].id,
            class_subject_id=base["cs"].id,
            teacher_id=base["teacher"].id,
            session_date=date(2026, 3, 4),
            records=[{"student_id": base["student"].id, "status": "absent"}],
        )
        summary = svc.get_summary_for_student(base["student"].id, base["sy"].id)
        assert isinstance(summary, list)
        assert len(summary) >= 1
        assert "absences" in summary[0]
        assert "total" in summary[0]
