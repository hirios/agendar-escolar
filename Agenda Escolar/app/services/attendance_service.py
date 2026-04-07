from flask import current_app
from ..repositories.attendance_repository import AttendanceRepository
from ..repositories.user_repository import UserRepository
from .notification_service import NotificationService


class AttendanceService:
    def __init__(self):
        self.att_repo = AttendanceRepository()
        self.user_repo = UserRepository()
        self.notif_service = NotificationService()

    def take_attendance(self, class_id, class_subject_id, teacher_id, session_date, records, lesson_number=1):
        """
        records: lista de dicts {student_id, status, justification (opcional)}
        """
        session = self.att_repo.get_or_create_session(
            class_id=class_id,
            class_subject_id=class_subject_id,
            teacher_id=teacher_id,
            session_date=session_date,
            lesson_number=lesson_number,
        )
        saved = []
        for rec in records:
            record = self.att_repo.upsert_record(
                session_id=session.id,
                student_id=rec["student_id"],
                status=rec["status"],
                justification=rec.get("justification"),
            )
            saved.append(record)
            if rec["status"] == "absent":
                self._check_absence_threshold(rec["student_id"], class_subject_id)
        return session, saved

    def _check_absence_threshold(self, student_id, class_subject_id):
        max_percent = current_app.config.get("MAX_ABSENCE_PERCENT", 25.0)
        total, absences, percent = self.att_repo.get_student_rate(student_id, class_subject_id)
        if total > 0 and percent >= max_percent:
            student = self.user_repo.get_by_id(student_id)
            if student:
                self.notif_service.create(
                    user_id=student_id,
                    title="Alerta de Frequência",
                    message=f"Sua frequência atingiu {percent:.1f}% de faltas em uma disciplina. Limite: {max_percent}%.",
                    type="attendance_alert",
                )

    def get_summary_for_student(self, student_id, school_year_id=None):
        return self.att_repo.get_student_summary(student_id, school_year_id)

    def get_sessions_for_class_subject(self, class_subject_id):
        return self.att_repo.get_sessions_by_class_subject(class_subject_id)
