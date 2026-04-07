from ..extensions import db
from ..models.user import User
from ..models.class_ import Class, ClassStudent, ClassSubject
from ..models.grade import Grade
from ..models.attendance import AttendanceRecord, AttendanceSession
from ..repositories.grade_repository import GradeRepository
from ..repositories.attendance_repository import AttendanceRepository


class AnalyticsService:
    def __init__(self):
        self.grade_repo = GradeRepository()
        self.att_repo = AttendanceRepository()

    def get_director_stats(self, school_year_id=None):
        """KPIs para o dashboard da direção."""
        students_count = db.session.execute(
            db.select(db.func.count(User.id)).where(User.role == "student", User.is_active == True)
        ).scalar() or 0

        teachers_count = db.session.execute(
            db.select(db.func.count(User.id)).where(User.role == "teacher", User.is_active == True)
        ).scalar() or 0

        stmt = db.select(db.func.count(Class.id))
        if school_year_id:
            stmt = stmt.where(Class.school_year_id == school_year_id)
        classes_count = db.session.execute(stmt).scalar() or 0

        return {
            "students": students_count,
            "teachers": teachers_count,
            "classes": classes_count,
        }

    def get_class_performance_chart(self, class_id, school_year_id):
        """Dados para gráfico de barras: média da turma por disciplina."""
        return self.grade_repo.get_class_averages(class_id, school_year_id)

    def get_student_performance_chart(self, student_id, school_year_id):
        """Dados para gráfico radar: média do aluno por disciplina."""
        return self.grade_repo.get_student_average_per_subject(student_id, school_year_id)

    def get_student_attendance_chart(self, student_id, school_year_id=None):
        """Dados para gráfico rosca: frequência do aluno por disciplina."""
        summary = self.att_repo.get_student_summary(student_id, school_year_id)
        return [
            {
                "label": s["subject_name"],
                "presences": s["presences"],
                "absences": s["absences"],
                "percent_absent": s["percent_absent"],
            }
            for s in summary
        ]

    def get_teacher_stats(self, teacher_id, school_year_id):
        """KPIs para o dashboard do professor."""
        from ..models.class_ import ClassStudent
        from ..models.assignment import Assignment
        from datetime import date, timedelta

        # Total de alunos únicos nas turmas do professor
        students_count = db.session.execute(
            db.select(db.func.count(db.distinct(ClassStudent.student_id)))
            .join(ClassSubject, ClassSubject.class_id == ClassStudent.class_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
                ClassStudent.status == "active",
            )
        ).scalar() or 0

        # Atividades com prazo nos próximos 7 dias
        today = date.today()
        upcoming_assignments = db.session.execute(
            db.select(db.func.count(Assignment.id))
            .join(ClassSubject, ClassSubject.id == Assignment.class_subject_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
                Assignment.due_date >= today,
                Assignment.due_date <= today + timedelta(days=7),
            )
        ).scalar() or 0

        # Alunos em risco (média < passing grade) nas turmas do professor
        from flask import current_app
        min_grade = current_app.config.get("MIN_PASSING_GRADE", 5.0)
        at_risk_rows = db.session.execute(
            db.select(Grade.student_id, db.func.avg(Grade.score).label("avg"))
            .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(Grade.student_id, Grade.class_subject_id)
        ).all()
        at_risk_ids = {r.student_id for r in at_risk_rows if r.avg and float(r.avg) < min_grade}
        at_risk_count = len(at_risk_ids)

        return {
            "students": students_count,
            "upcoming_assignments": upcoming_assignments,
            "at_risk": at_risk_count,
        }

    def get_teacher_at_risk_students(self, teacher_id, school_year_id):
        """Lista detalhada de alunos em risco nas turmas do professor, com score e razões."""
        from flask import current_app
        from sqlalchemy import func
        from ..models.subject import Subject

        min_grade = current_app.config.get("MIN_PASSING_GRADE", 5.0)
        max_absent = current_app.config.get("MAX_ABSENCE_PERCENT", 25.0)

        # Pior média por aluno por disciplina (nas turmas do professor)
        grade_rows = db.session.execute(
            db.select(
                Grade.student_id,
                ClassSubject.id.label("cs_id"),
                Subject.name.label("subject"),
                func.avg(Grade.score).label("avg"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(Grade.student_id, ClassSubject.id)
        ).all()

        # worst_avg[student_id] = (pior_avg, disciplina, cs_id)
        worst_avg = {}
        for r in grade_rows:
            avg = float(r.avg)
            if r.student_id not in worst_avg or avg < worst_avg[r.student_id][0]:
                worst_avg[r.student_id] = (avg, r.subject, r.cs_id)

        # % de faltas por aluno (nas turmas do professor)
        att_rows = db.session.execute(
            db.select(
                AttendanceRecord.student_id,
                func.count(AttendanceRecord.id).label("total"),
                func.sum(db.case((AttendanceRecord.status == "absent", 1), else_=0)).label("absences"),
            )
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(ClassSubject, ClassSubject.id == AttendanceSession.class_subject_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(AttendanceRecord.student_id)
        ).all()
        absence_pcts = {}
        for r in att_rows:
            if r.total:
                absence_pcts[r.student_id] = round(r.absences / r.total * 100, 1)

        at_risk_ids = set()
        for sid, (avg, _, _cs) in worst_avg.items():
            if avg < min_grade:
                at_risk_ids.add(sid)
        for sid, pct in absence_pcts.items():
            if pct >= max_absent:
                at_risk_ids.add(sid)

        if not at_risk_ids:
            return []

        students = db.session.execute(
            db.select(User).where(User.id.in_(at_risk_ids), User.is_active == True)
        ).scalars().all()

        result = []
        for student in students:
            avg_val, subject, cs_id = worst_avg.get(student.id, (None, None, None))
            pct_absent = absence_pcts.get(student.id, 0.0)
            score, reasons = self._compute_risk_score(avg_val, pct_absent, min_grade, max_absent)
            result.append({
                "student": student,
                "score": score,
                "reasons": reasons,
                "worst_subject": subject,
                "worst_cs_id": cs_id,
                "avg_grade": round(avg_val, 1) if avg_val is not None else None,
                "pct_absent": pct_absent,
            })

        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    def get_teacher_class_subject_stats(self, teacher_id, school_year_id):
        """Por class_subject: nº alunos, média, data da última chamada."""
        from ..models.class_ import ClassStudent
        from sqlalchemy import func

        # Alunos por turma
        students_per_class = {
            row.class_id: row.count
            for row in db.session.execute(
                db.select(ClassStudent.class_id, func.count(ClassStudent.student_id).label("count"))
                .where(ClassStudent.status == "active")
                .group_by(ClassStudent.class_id)
            ).all()
        }

        # Média por class_subject
        avg_per_cs = {
            row.cs_id: round(float(row.avg), 1) if row.avg else None
            for row in db.session.execute(
                db.select(Grade.class_subject_id.label("cs_id"), func.avg(Grade.score).label("avg"))
                .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
                .where(ClassSubject.teacher_id == teacher_id, ClassSubject.school_year_id == school_year_id)
                .group_by(Grade.class_subject_id)
            ).all()
        }

        # Última chamada por class_subject
        last_att_per_cs = {
            row.cs_id: row.last_date
            for row in db.session.execute(
                db.select(
                    AttendanceSession.class_subject_id.label("cs_id"),
                    func.max(AttendanceSession.date).label("last_date"),
                )
                .join(ClassSubject, ClassSubject.id == AttendanceSession.class_subject_id)
                .where(ClassSubject.teacher_id == teacher_id, ClassSubject.school_year_id == school_year_id)
                .group_by(AttendanceSession.class_subject_id)
            ).all()
        }

        return {
            "students_per_class": students_per_class,
            "avg_per_cs": avg_per_cs,
            "last_att_per_cs": last_att_per_cs,
        }

    def get_upcoming_assignments(self, teacher_id, school_year_id, days=14):
        """Atividades do professor com prazo nos próximos N dias."""
        from ..models.assignment import Assignment
        from datetime import date, timedelta
        today = date.today()
        return db.session.execute(
            db.select(Assignment)
            .join(ClassSubject, ClassSubject.id == Assignment.class_subject_id)
            .where(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.school_year_id == school_year_id,
                Assignment.due_date >= today,
                Assignment.due_date <= today + timedelta(days=days),
            )
            .order_by(Assignment.due_date)
        ).scalars().all()

    def get_upcoming_calendar_events(self, school_year_id, days=30):
        """Próximos eventos do calendário acadêmico."""
        from ..models.calendar_event import CalendarEvent
        from datetime import date, timedelta
        today = date.today()
        return db.session.execute(
            db.select(CalendarEvent)
            .where(
                CalendarEvent.school_year_id == school_year_id,
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= today + timedelta(days=days),
            )
            .order_by(CalendarEvent.event_date)
            .limit(5)
        ).scalars().all()

    def get_overall_average(self, school_year_id):
        """Média geral de todas as notas do ano letivo."""
        result = db.session.execute(
            db.select(db.func.avg(Grade.score))
            .join(ClassSubject, ClassSubject.id == Grade.class_subject_id)
            .where(ClassSubject.school_year_id == school_year_id)
        ).scalar()
        return round(float(result), 1) if result else None

    def get_students_at_risk(self, school_year_id=None, max_absence_percent=25.0, min_passing_grade=5.0):
        """Retorna alunos com alta frequência de faltas ou notas baixas."""
        return [
            item["student"]
            for item in self.get_at_risk_with_scores(school_year_id, max_absence_percent, min_passing_grade)
        ]

    def get_at_risk_with_scores(self, school_year_id=None, max_absence_percent=25.0, min_passing_grade=5.0):
        """Retorna alunos em risco com score 0-100 e razões detalhadas."""
        from sqlalchemy import func

        # Média por aluno por disciplina → detecta risco em qualquer matéria
        grade_stmt = (
            db.select(
                Grade.student_id,
                ClassSubject.subject_id,
                func.avg(Grade.score).label("avg"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .group_by(Grade.student_id, ClassSubject.subject_id)
        )
        if school_year_id:
            grade_stmt = grade_stmt.where(ClassSubject.school_year_id == school_year_id)

        # Guarda a pior média de cada aluno (mínimo entre as disciplinas)
        grade_avgs = {}  # student_id → pior média
        for r in db.session.execute(grade_stmt).all():
            avg = float(r.avg)
            if r.student_id not in grade_avgs or avg < grade_avgs[r.student_id]:
                grade_avgs[r.student_id] = avg

        # % de faltas por aluno
        att_stmt = (
            db.select(
                AttendanceRecord.student_id,
                func.count(AttendanceRecord.id).label("total"),
                func.sum(db.case((AttendanceRecord.status == "absent", 1), else_=0)).label("absences"),
            )
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        )
        if school_year_id:
            att_stmt = att_stmt.join(
                ClassSubject, ClassSubject.id == AttendanceSession.class_subject_id
            ).where(ClassSubject.school_year_id == school_year_id)
        att_stmt = att_stmt.group_by(AttendanceRecord.student_id)
        absence_pcts = {}
        for r in db.session.execute(att_stmt).all():
            if r.total:
                absence_pcts[r.student_id] = round(r.absences / r.total * 100, 1)

        # Identifica alunos em risco
        at_risk_ids = set()
        for sid, avg in grade_avgs.items():
            if avg < min_passing_grade:
                at_risk_ids.add(sid)
        for sid, pct in absence_pcts.items():
            if pct >= max_absence_percent:
                at_risk_ids.add(sid)

        if not at_risk_ids:
            return []

        students = db.session.execute(
            db.select(User).where(User.id.in_(at_risk_ids), User.is_active == True)
        ).scalars().all()

        result = []
        for student in students:
            avg = grade_avgs.get(student.id)
            pct_absent = absence_pcts.get(student.id, 0.0)
            score, reasons = self._compute_risk_score(avg, pct_absent, min_passing_grade, max_absence_percent)
            result.append({
                "student": student,
                "score": score,
                "reasons": reasons,
                "avg_grade": round(avg, 1) if avg is not None else None,
                "pct_absent": pct_absent,
            })

        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    def _compute_risk_score(self, avg_grade, pct_absent, min_passing=5.0, max_absent=25.0):
        """Retorna (score 0–100, lista de razões legíveis)."""
        reasons = []

        # Componente de nota (peso 60%)
        if avg_grade is None:
            grade_risk = 0
        elif avg_grade >= 7:
            grade_risk = 0
        elif avg_grade >= min_passing:
            grade_risk = (7 - avg_grade) / (7 - min_passing) * 40
            reasons.append(f"Média {avg_grade:.1f}")
        else:
            grade_risk = 40 + (min_passing - avg_grade) / min_passing * 60
            reasons.append(f"Média {avg_grade:.1f}")

        # Componente de faltas (peso 40%)
        if pct_absent >= max_absent:
            abs_risk = min(100, 50 + (pct_absent - max_absent) / max_absent * 50)
            reasons.append(f"{pct_absent:.0f}% de faltas")
        elif pct_absent >= 15:
            abs_risk = (pct_absent - 15) / (max_absent - 15) * 50
            if pct_absent >= 20:
                reasons.append(f"{pct_absent:.0f}% de faltas")
        else:
            abs_risk = 0

        score = round(grade_risk * 0.6 + abs_risk * 0.4)
        return max(0, min(100, score)), reasons

    def get_insights(self, school_year_id):
        """Motor de insights: detecta quedas de desempenho e turmas críticas."""
        from ..models.class_ import Class
        from ..models.subject import Subject
        from ..models.school_year import GradePeriod
        from sqlalchemy import func
        from collections import defaultdict

        rows = db.session.execute(
            db.select(
                ClassSubject.id.label("cs_id"),
                Class.name.label("class_name"),
                Subject.name.label("subject"),
                GradePeriod.name.label("period"),
                GradePeriod.order_index,
                func.avg(Grade.score).label("avg"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .join(GradePeriod, GradePeriod.id == Grade.grade_period_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(Class, Class.id == ClassSubject.class_id)
            .where(ClassSubject.school_year_id == school_year_id)
            .group_by(ClassSubject.id, GradePeriod.id)
            .order_by(ClassSubject.id, GradePeriod.order_index)
        ).all()

        cs_data = defaultdict(list)
        for r in rows:
            cs_data[r.cs_id].append({
                "class_name": r.class_name,
                "subject": r.subject,
                "period": r.period,
                "order": r.order_index,
                "avg": round(float(r.avg), 1),
            })

        insights = []
        seen_failing = set()

        for cs_id, periods in cs_data.items():
            periods.sort(key=lambda x: x["order"])
            last = periods[-1]

            # Média crítica no período mais recente
            if last["avg"] < 5.0 and cs_id not in seen_failing:
                seen_failing.add(cs_id)
                insights.append({
                    "type": "failing_class",
                    "severity": "high" if last["avg"] < 3.0 else "medium",
                    "title": f"Média crítica em {last['subject']}",
                    "detail": f"Turma {last['class_name']} — {last['avg']:.1f} no {last['period']}",
                })

            # Queda entre bimestres consecutivos
            for i in range(1, len(periods)):
                prev, curr = periods[i - 1], periods[i]
                if prev["avg"] > 0:
                    drop_pct = (prev["avg"] - curr["avg"]) / prev["avg"] * 100
                    if drop_pct >= 15:
                        insights.append({
                            "type": "grade_drop",
                            "severity": "high" if drop_pct >= 25 else "medium",
                            "title": f"Queda de {drop_pct:.0f}% em {curr['subject']}",
                            "detail": (
                                f"Turma {curr['class_name']}: "
                                f"{prev['avg']:.1f} → {curr['avg']:.1f} "
                                f"({prev['period']} → {curr['period']})"
                            ),
                        })

        severity_order = {"high": 0, "medium": 1}
        insights.sort(key=lambda x: severity_order.get(x["severity"], 9))
        return insights[:8]

    def get_student_grade_evolution(self, student_id, school_year_id):
        """Evolução de notas por bimestre, formatada para gráfico de linha multi-série."""
        from ..models.subject import Subject
        from ..models.school_year import GradePeriod
        from sqlalchemy import func
        from collections import defaultdict

        periods = db.session.execute(
            db.select(GradePeriod)
            .where(GradePeriod.school_year_id == school_year_id)
            .order_by(GradePeriod.order_index)
        ).scalars().all()

        if not periods:
            return {"periods": [], "series": []}

        period_names = [p.name for p in periods]
        pid_to_name = {p.id: p.name for p in periods}

        rows = db.session.execute(
            db.select(
                Subject.name.label("subject"),
                Grade.grade_period_id,
                func.avg(Grade.score).label("avg"),
            )
            .select_from(ClassSubject)
            .join(Grade, Grade.class_subject_id == ClassSubject.id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(
                Grade.student_id == student_id,
                ClassSubject.school_year_id == school_year_id,
            )
            .group_by(ClassSubject.subject_id, Grade.grade_period_id)
        ).all()

        subject_data = defaultdict(dict)
        for r in rows:
            pname = pid_to_name.get(r.grade_period_id)
            if pname:
                subject_data[r.subject][pname] = round(float(r.avg), 1)

        series = sorted(
            [
                {"label": subj, "data": [subject_data[subj].get(p) for p in period_names]}
                for subj in subject_data
            ],
            key=lambda x: x["label"],
        )
        return {"periods": period_names, "series": series}
