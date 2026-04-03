from flask import current_app
from ..repositories.grade_repository import GradeRepository
from ..repositories.class_repository import ClassRepository
from ..repositories.user_repository import UserRepository
from ..models.school_year import GradePeriod
from ..extensions import db


class GradeService:
    def __init__(self):
        self.grade_repo = GradeRepository()
        self.class_repo = ClassRepository()
        self.user_repo = UserRepository()

    def save_grade(self, student_id, class_subject_id, grade_period_id, grade_type, score, description=None):
        return self.grade_repo.upsert(
            student_id=student_id,
            class_subject_id=class_subject_id,
            grade_period_id=grade_period_id,
            grade_type=grade_type,
            score=score,
            description=description,
        )

    def save_bulk_grades(self, entries):
        """entries: lista de dicts com student_id, class_subject_id, grade_period_id, grade_type, score."""
        saved = []
        for entry in entries:
            grade = self.grade_repo.upsert(**entry)
            saved.append(grade)
        return saved

    def get_boletim(self, student_id, school_year_id):
        """
        Retorna estrutura para o boletim do aluno:
        {
          subject_name: {
            period_name: {grade_type: score, ...},
            'media': float,
            'status': 'aprovado'|'reprovado'|'em_andamento'
          }
        }
        """
        grades = self.grade_repo.get_student_grades_by_period(student_id, school_year_id)
        periods = db.session.execute(
            db.select(GradePeriod)
            .where(GradePeriod.school_year_id == school_year_id)
            .order_by(GradePeriod.order_index)
        ).scalars().all()

        boletim = {}
        for grade in grades:
            subject = grade.class_subject.subject.name
            period = grade.grade_period.name
            if subject not in boletim:
                boletim[subject] = {p.name: {} for p in periods}
                boletim[subject]["media"] = None
                boletim[subject]["status"] = "em_andamento"
            boletim[subject][period][grade.grade_type] = float(grade.score)

        # Calcula média de cada disciplina
        min_grade = current_app.config.get("MIN_PASSING_GRADE", 5.0)
        for subject, data in boletim.items():
            scores = []
            for period in periods:
                period_data = data.get(period.name, {})
                period_scores = list(period_data.values())
                if period_scores:
                    scores.extend(period_scores)
            if scores:
                media = round(sum(scores) / len(scores), 2)
                data["media"] = media
                data["status"] = "aprovado" if media >= min_grade else "reprovado"

        return boletim, periods

    def get_student_gpa(self, student_id, school_year_id):
        """Retorna média geral do aluno no ano letivo."""
        averages = self.grade_repo.get_student_average_per_subject(student_id, school_year_id)
        if not averages:
            return None
        return round(sum(a["avg"] for a in averages) / len(averages), 2)

    def get_class_performance(self, class_id, school_year_id):
        return self.grade_repo.get_class_averages(class_id, school_year_id)
