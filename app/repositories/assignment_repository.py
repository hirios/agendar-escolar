from datetime import datetime, timezone
from ..extensions import db
from ..models.assignment import Assignment, AssignmentSubmission
from ..models.class_ import ClassSubject
from .base_repository import BaseRepository


class AssignmentRepository(BaseRepository):
    def __init__(self):
        super().__init__(Assignment)

    def get_by_class_subject(self, class_subject_id):
        return self.session.execute(
            db.select(Assignment)
            .where(Assignment.class_subject_id == class_subject_id)
            .order_by(Assignment.due_date)
        ).scalars().all()

    def get_for_student(self, student_id, school_year_id=None):
        from ..models.class_ import ClassStudent
        stmt = (
            db.select(Assignment)
            .join(ClassSubject, ClassSubject.id == Assignment.class_subject_id)
            .join(ClassStudent, ClassStudent.class_id == ClassSubject.class_id)
            .where(ClassStudent.student_id == student_id, ClassStudent.status == "active")
            .order_by(Assignment.due_date)
        )
        if school_year_id:
            stmt = stmt.where(ClassSubject.school_year_id == school_year_id)
        return self.session.execute(stmt).scalars().all()

    def get_submission(self, assignment_id, student_id):
        return self.session.execute(
            db.select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student_id,
            )
        ).scalar_one_or_none()

    def submit(self, assignment_id, student_id):
        sub = self.get_submission(assignment_id, student_id)
        now = datetime.now(timezone.utc)
        if sub:
            sub.submitted_at = now
            sub.status = "submitted"
        else:
            sub = AssignmentSubmission(
                assignment_id=assignment_id,
                student_id=student_id,
                submitted_at=now,
                status="submitted",
            )
            self.session.add(sub)
        self.session.commit()
        return sub

    def grade_submission(self, assignment_id, student_id, score, feedback=None):
        sub = self.get_submission(assignment_id, student_id)
        if sub:
            sub.score = score
            sub.feedback = feedback
            sub.status = "graded"
            self.session.commit()
        return sub
