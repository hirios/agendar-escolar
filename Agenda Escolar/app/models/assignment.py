from datetime import datetime, timezone
from ..extensions import db


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    class_subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    max_score = db.Column(db.Numeric(5, 2))
    type = db.Column(
        db.Enum("homework", "project", "test", "activity", name="assignment_type"),
        default="homework",
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    class_subject = db.relationship("ClassSubject", back_populates="assignments")
    teacher = db.relationship("User", foreign_keys=[teacher_id])
    submissions = db.relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")

    @property
    def type_label(self):
        labels = {
            "homework": "Tarefa",
            "project": "Projeto",
            "test": "Avaliação",
            "activity": "Atividade",
        }
        return labels.get(self.type, self.type)

    @property
    def is_overdue(self):
        if self.due_date:
            return datetime.now(timezone.utc) > self.due_date.replace(tzinfo=timezone.utc)
        return False

    def __repr__(self):
        return f"<Assignment {self.title}>"


class AssignmentSubmission(db.Model):
    __tablename__ = "assignment_submissions"

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Numeric(5, 2))
    feedback = db.Column(db.Text)
    status = db.Column(
        db.Enum("pending", "submitted", "graded", "late", name="submission_status"),
        default="pending",
    )

    __table_args__ = (db.UniqueConstraint("assignment_id", "student_id"),)

    assignment = db.relationship("Assignment", back_populates="submissions")
    student = db.relationship("User", foreign_keys=[student_id])

    @property
    def status_label(self):
        labels = {
            "pending": "Pendente",
            "submitted": "Entregue",
            "graded": "Corrigido",
            "late": "Atrasado",
        }
        return labels.get(self.status, self.status)

    def __repr__(self):
        return f"<Submission assignment={self.assignment_id} student={self.student_id}>"
