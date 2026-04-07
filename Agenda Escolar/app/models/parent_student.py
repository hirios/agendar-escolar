from ..extensions import db


class ParentStudent(db.Model):
    __tablename__ = "parent_students"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    relationship = db.Column(db.String(50), default="responsável")

    __table_args__ = (db.UniqueConstraint("parent_id", "student_id"),)

    parent = db.relationship("User", foreign_keys=[parent_id])
    student = db.relationship("User", foreign_keys=[student_id])

    def __repr__(self):
        return f"<ParentStudent parent={self.parent_id} student={self.student_id}>"
