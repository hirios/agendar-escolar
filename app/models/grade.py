from datetime import datetime, timezone
from ..extensions import db


class Grade(db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=False)
    grade_period_id = db.Column(db.Integer, db.ForeignKey("grade_periods.id"), nullable=False)
    score = db.Column(db.Numeric(5, 2), nullable=False)
    max_score = db.Column(db.Numeric(5, 2), default=10.0, nullable=False)
    grade_type = db.Column(
        db.Enum(
            "prova", "trabalho", "participacao", "recuperacao", "final",
            name="grade_type",
        ),
        default="prova",
        nullable=False,
    )
    description = db.Column(db.String(200))
    graded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("student_id", "class_subject_id", "grade_period_id", "grade_type"),
    )

    student = db.relationship("User", foreign_keys=[student_id])
    class_subject = db.relationship("ClassSubject", back_populates="grades")
    grade_period = db.relationship("GradePeriod", back_populates="grades")

    @property
    def score_float(self):
        return float(self.score) if self.score is not None else None

    @property
    def grade_type_label(self):
        labels = {
            "prova": "Prova",
            "trabalho": "Trabalho",
            "participacao": "Participação",
            "recuperacao": "Recuperação",
            "final": "Final",
        }
        return labels.get(self.grade_type, self.grade_type)

    def __repr__(self):
        return f"<Grade student={self.student_id} score={self.score}>"
