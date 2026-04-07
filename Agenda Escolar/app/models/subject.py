from ..extensions import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    workload_hours = db.Column(db.Integer)

    class_subjects = db.relationship("ClassSubject", back_populates="subject", lazy="dynamic")

    def __repr__(self):
        return f"<Subject {self.code} - {self.name}>"
