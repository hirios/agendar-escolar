from sqlalchemy import func
from ..extensions import db
from ..models.grade import Grade
from ..models.class_ import ClassSubject
from ..models.subject import Subject
from ..models.school_year import GradePeriod
from .base_repository import BaseRepository


class GradeRepository(BaseRepository):
    def __init__(self):
        super().__init__(Grade)

    def upsert(self, student_id, class_subject_id, grade_period_id, grade_type, score, description=None):
        existing = self.session.execute(
            db.select(Grade).where(
                Grade.student_id == student_id,
                Grade.class_subject_id == class_subject_id,
                Grade.grade_period_id == grade_period_id,
                Grade.grade_type == grade_type,
            )
        ).scalar_one_or_none()

        # score=None significa "apagar a nota"
        if score is None:
            if existing:
                self.session.delete(existing)
                self.session.commit()
            return None

        if existing:
            existing.score = score
            existing.description = description
            self.session.commit()
            return existing

        grade = Grade(
            student_id=student_id,
            class_subject_id=class_subject_id,
            grade_period_id=grade_period_id,
            grade_type=grade_type,
            score=score,
            description=description,
        )
        self.session.add(grade)
        self.session.commit()
        return grade

    def get_student_grades_by_period(self, student_id, school_year_id):
        """Retorna todas as notas de um aluno em um ano letivo, agrupadas por disciplina."""
        rows = self.session.execute(
            db.select(Grade)
            .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
            .join(GradePeriod, GradePeriod.id == Grade.grade_period_id)
            .where(
                Grade.student_id == student_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .order_by(ClassSubject.subject_id, GradePeriod.order_index)
        ).scalars().all()
        return rows

    def get_grades_for_class_subject(self, class_subject_id, grade_period_id=None):
        stmt = db.select(Grade).where(Grade.class_subject_id == class_subject_id)
        if grade_period_id:
            stmt = stmt.where(Grade.grade_period_id == grade_period_id)
        return self.session.execute(stmt).scalars().all()

    def get_class_averages(self, class_id, school_year_id):
        """Média da turma por disciplina."""
        rows = self.session.execute(
            db.select(
                Subject.name.label("subject_name"),
                func.avg(Grade.score).label("avg_score"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(
                ClassSubject.class_id == class_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(Subject.id, Subject.name)
            .order_by(Subject.name)
        ).all()
        return [{"subject": r.subject_name, "avg": round(float(r.avg_score), 2)} for r in rows]

    def get_student_average_per_subject(self, student_id, school_year_id):
        """Média geral do aluno por disciplina no ano letivo."""
        rows = self.session.execute(
            db.select(
                Subject.name.label("subject_name"),
                ClassSubject.id.label("cs_id"),
                func.avg(Grade.score).label("avg_score"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(
                Grade.student_id == student_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(Subject.id, Subject.name, ClassSubject.id)
        ).all()
        return [
            {"subject": r.subject_name, "cs_id": r.cs_id, "avg": round(float(r.avg_score), 2)}
            for r in rows
        ]
