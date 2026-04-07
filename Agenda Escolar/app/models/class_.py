from datetime import date
from ..extensions import db


class Class(db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_years.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    grade_level = db.Column(db.String(30))
    shift = db.Column(
        db.Enum("morning", "afternoon", "evening", name="class_shift"),
        nullable=False,
        default="morning",
    )
    room = db.Column(db.String(20))
    max_students = db.Column(db.Integer, default=40)
    created_at = db.Column(db.Date, default=date.today)

    school_year = db.relationship("SchoolYear", back_populates="classes")
    enrollments = db.relationship("ClassStudent", back_populates="class_", cascade="all, delete-orphan", lazy="dynamic")
    class_subjects = db.relationship("ClassSubject", back_populates="class_", cascade="all, delete-orphan", lazy="dynamic")
    attendance_sessions = db.relationship("AttendanceSession", back_populates="class_", lazy="dynamic")

    @property
    def active_students_count(self):
        return self.enrollments.filter_by(status="active").count()

    @property
    def shift_label(self):
        labels = {"morning": "Manhã", "afternoon": "Tarde", "evening": "Noite"}
        return labels.get(self.shift, self.shift)

    def __repr__(self):
        return f"<Class {self.name}>"


class ClassStudent(db.Model):
    __tablename__ = "class_students"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    enrollment_date = db.Column(db.Date, default=date.today)
    status = db.Column(
        db.Enum("active", "transferred", "withdrawn", name="enrollment_status"),
        default="active",
        nullable=False,
    )

    __table_args__ = (db.UniqueConstraint("class_id", "student_id"),)

    class_ = db.relationship("Class", back_populates="enrollments")
    student = db.relationship("User", foreign_keys=[student_id])

    def __repr__(self):
        return f"<ClassStudent class={self.class_id} student={self.student_id}>"


class ClassSubject(db.Model):
    __tablename__ = "class_subjects"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_years.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("class_id", "subject_id", "school_year_id"),
    )

    class_ = db.relationship("Class", back_populates="class_subjects")
    subject = db.relationship("Subject", back_populates="class_subjects")
    teacher = db.relationship("User", foreign_keys=[teacher_id])
    school_year = db.relationship("SchoolYear")
    grades = db.relationship("Grade", back_populates="class_subject", lazy="dynamic")
    assignments = db.relationship("Assignment", back_populates="class_subject", lazy="dynamic")
    attendance_sessions = db.relationship("AttendanceSession", back_populates="class_subject", lazy="dynamic")
    schedules = db.relationship("Schedule", back_populates="class_subject", lazy="dynamic")

    def __repr__(self):
        return f"<ClassSubject class={self.class_id} subject={self.subject_id}>"
