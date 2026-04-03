from ..extensions import db


class Schedule(db.Model):
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    class_subject_id = db.Column(db.Integer, db.ForeignKey("class_subjects.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Seg, 1=Ter, ..., 4=Sex
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(20))

    class_subject = db.relationship("ClassSubject", back_populates="schedules")

    DAY_LABELS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    @property
    def day_label(self):
        return self.DAY_LABELS[self.day_of_week] if 0 <= self.day_of_week <= 6 else "?"

    def __repr__(self):
        return f"<Schedule cs={self.class_subject_id} day={self.day_of_week}>"
