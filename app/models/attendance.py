from datetime import datetime, timezone, date
from ..extensions import db


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    class_subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    lesson_number = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("class_id", "class_subject_id", "date", "lesson_number"),
    )

    class_ = db.relationship("Class", back_populates="attendance_sessions")
    class_subject = db.relationship("ClassSubject", back_populates="attendance_sessions")
    teacher = db.relationship("User", foreign_keys=[teacher_id])
    records = db.relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AttendanceSession class={self.class_id} date={self.date}>"


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.Enum("present", "absent", "justified", name="attendance_status"),
        default="absent",
        nullable=False,
    )
    justification = db.Column(db.Text)

    __table_args__ = (db.UniqueConstraint("session_id", "student_id"),)

    session = db.relationship("AttendanceSession", back_populates="records")
    student = db.relationship("User", foreign_keys=[student_id])

    @property
    def status_label(self):
        labels = {"present": "Presente", "absent": "Falta", "justified": "Justificada"}
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {"present": "green", "absent": "red", "justified": "yellow"}
        return colors.get(self.status, "gray")

    def __repr__(self):
        return f"<AttendanceRecord session={self.session_id} student={self.student_id} status={self.status}>"
