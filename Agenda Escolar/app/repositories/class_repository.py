from ..extensions import db
from ..models.class_ import Class, ClassStudent, ClassSubject
from .base_repository import BaseRepository


class ClassRepository(BaseRepository):
    def __init__(self):
        super().__init__(Class)

    def get_active(self, school_year_id=None):
        stmt = db.select(Class)
        if school_year_id:
            stmt = stmt.where(Class.school_year_id == school_year_id)
        return self.session.execute(stmt.order_by(Class.name)).scalars().all()

    def get_teacher_classes(self, teacher_id, school_year_id=None):
        stmt = (
            db.select(Class)
            .join(ClassSubject, ClassSubject.class_id == Class.id)
            .where(ClassSubject.teacher_id == teacher_id)
            .distinct()
        )
        if school_year_id:
            stmt = stmt.where(Class.school_year_id == school_year_id)
        return self.session.execute(stmt.order_by(Class.name)).scalars().all()

    def get_teacher_class_subjects(self, teacher_id, school_year_id=None):
        stmt = db.select(ClassSubject).where(ClassSubject.teacher_id == teacher_id)
        if school_year_id:
            stmt = stmt.where(ClassSubject.school_year_id == school_year_id)
        return self.session.execute(stmt).scalars().all()

    def enroll_student(self, class_id, student_id):
        existing = self.session.execute(
            db.select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == student_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.status != "active":
                existing.status = "active"
                self.session.commit()
            return existing
        enrollment = ClassStudent(class_id=class_id, student_id=student_id)
        self.session.add(enrollment)
        self.session.commit()
        return enrollment

    def remove_student(self, class_id, student_id):
        enrollment = self.session.execute(
            db.select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == student_id,
            )
        ).scalar_one_or_none()
        if enrollment:
            enrollment.status = "withdrawn"
            self.session.commit()
        return enrollment

    def assign_teacher(self, class_id, subject_id, teacher_id, school_year_id):
        existing = self.session.execute(
            db.select(ClassSubject).where(
                ClassSubject.class_id == class_id,
                ClassSubject.subject_id == subject_id,
                ClassSubject.school_year_id == school_year_id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.teacher_id = teacher_id
            self.session.commit()
            return existing
        cs = ClassSubject(
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            school_year_id=school_year_id,
        )
        self.session.add(cs)
        self.session.commit()
        return cs

    def get_class_subject(self, class_id, subject_id, school_year_id=None):
        stmt = db.select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
        )
        if school_year_id:
            stmt = stmt.where(ClassSubject.school_year_id == school_year_id)
        return self.session.execute(stmt).scalar_one_or_none()
