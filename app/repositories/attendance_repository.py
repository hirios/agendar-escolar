from datetime import date
from sqlalchemy import func
from ..extensions import db
from ..models.attendance import AttendanceSession, AttendanceRecord
from .base_repository import BaseRepository


class AttendanceRepository(BaseRepository):
    def __init__(self):
        super().__init__(AttendanceSession)

    def get_session(self, class_id, class_subject_id, session_date, lesson_number=1):
        return self.session.execute(
            db.select(AttendanceSession).where(
                AttendanceSession.class_id == class_id,
                AttendanceSession.class_subject_id == class_subject_id,
                AttendanceSession.date == session_date,
                AttendanceSession.lesson_number == lesson_number,
            )
        ).scalar_one_or_none()

    def get_or_create_session(self, class_id, class_subject_id, teacher_id, session_date, lesson_number=1):
        sess = self.get_session(class_id, class_subject_id, session_date, lesson_number)
        if not sess:
            sess = AttendanceSession(
                class_id=class_id,
                class_subject_id=class_subject_id,
                teacher_id=teacher_id,
                date=session_date,
                lesson_number=lesson_number,
            )
            self.session.add(sess)
            self.session.commit()
        return sess

    def get_sessions_by_class_subject(self, class_subject_id):
        return self.session.execute(
            db.select(AttendanceSession)
            .where(AttendanceSession.class_subject_id == class_subject_id)
            .order_by(AttendanceSession.date.desc())
        ).scalars().all()

    def upsert_record(self, session_id, student_id, status, justification=None):
        record = self.session.execute(
            db.select(AttendanceRecord).where(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == student_id,
            )
        ).scalar_one_or_none()
        if record:
            record.status = status
            record.justification = justification
        else:
            record = AttendanceRecord(
                session_id=session_id,
                student_id=student_id,
                status=status,
                justification=justification,
            )
            self.session.add(record)
        self.session.commit()
        return record

    def get_student_rate(self, student_id, class_subject_id):
        """Retorna (total_aulas, total_faltas, percentual_faltas)."""
        total = self.session.execute(
            db.select(func.count(AttendanceRecord.id))
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(
                AttendanceSession.class_subject_id == class_subject_id,
                AttendanceRecord.student_id == student_id,
            )
        ).scalar() or 0

        absences = self.session.execute(
            db.select(func.count(AttendanceRecord.id))
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(
                AttendanceSession.class_subject_id == class_subject_id,
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.status == "absent",
            )
        ).scalar() or 0

        percent = (absences / total * 100) if total > 0 else 0.0
        return total, absences, round(percent, 1)

    def get_student_summary(self, student_id, school_year_id=None):
        """Retorna lista de dicts com resumo por class_subject."""
        from ..models.class_ import ClassSubject, Class
        from ..models.subject import Subject

        stmt = (
            db.select(
                ClassSubject.id.label("cs_id"),
                Subject.name.label("subject_name"),
                Class.name.label("class_name"),
                func.count(AttendanceRecord.id).label("total"),
                func.sum(
                    db.case((AttendanceRecord.status == "absent", 1), else_=0)
                ).label("absences"),
            )
            .join(AttendanceSession, AttendanceSession.class_subject_id == ClassSubject.id)
            .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(Class, Class.id == ClassSubject.class_id)
            .where(AttendanceRecord.student_id == student_id)
            .group_by(ClassSubject.id, Subject.name, Class.name)
        )
        if school_year_id:
            stmt = stmt.where(ClassSubject.school_year_id == school_year_id)

        rows = self.session.execute(stmt).all()
        result = []
        for r in rows:
            total = r.total or 0
            absences = r.absences or 0
            percent = round(absences / total * 100, 1) if total > 0 else 0.0
            result.append({
                "cs_id": r.cs_id,
                "subject_name": r.subject_name,
                "class_name": r.class_name,
                "total": total,
                "absences": absences,
                "presences": total - absences,
                "percent_absent": percent,
            })
        return result
