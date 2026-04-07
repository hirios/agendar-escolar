"""
seed.py — Popula o banco de dados com dados de teste.

Execute após criar o banco:
    flask db upgrade     (ou python seed.py diretamente)
    python seed.py
"""
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    User, UserProfile, SchoolYear, GradePeriod, Subject,
    Class, ClassStudent, ClassSubject, Grade, AttendanceSession,
    AttendanceRecord, Assignment, ParentStudent, CalendarEvent,
)

app = create_app()

SUBJECTS = [
    ("Matemática", "MAT", 200),
    ("Português", "PORT", 200),
    ("História", "HIST", 120),
    ("Geografia", "GEO", 120),
    ("Ciências", "CIEN", 120),
    ("Educação Física", "EF", 80),
    ("Inglês", "ING", 80),
    ("Artes", "ART", 80),
]

STUDENTS = [
    "Ana Lima", "Bruno Costa", "Carla Souza", "Diego Alves", "Elena Martins",
    "Felipe Santos", "Gabriela Ramos", "Henrique Oliveira", "Isabela Ferreira", "João Pedro Gomes",
    "Karen Nunes", "Lucas Mendes", "Mariana Vieira", "Nicolás Rocha", "Olivia Carvalho",
    "Pedro Araújo", "Quéren Dias", "Rafael Moreira", "Sara Barbosa", "Thiago Nascimento",
]


def seed():
    with app.app_context():
        print("Limpando banco de dados…")
        db.drop_all()
        db.create_all()

        # ── Diretor ────────────────────────────────────────────────────────
        print("Criando diretor…")
        director = User(name="Diretora Maria Silva", email="diretor@escola.com", role="director")
        director.set_password("Escola@2025")
        db.session.add(director)
        db.session.flush()
        db.session.add(UserProfile(user_id=director.id, phone="(11) 99999-0001"))

        # ── Ano letivo ─────────────────────────────────────────────────────
        print("Criando ano letivo 2026…")
        sy = SchoolYear(
            name="2026",
            start_date=date(2026, 2, 3),
            end_date=date(2026, 12, 12),
            is_active=True,
        )
        db.session.add(sy)
        db.session.flush()

        # Bimestres
        periods = []
        bimestres = [
            ("1º Bimestre", date(2026, 2, 3), date(2026, 4, 25)),
            ("2º Bimestre", date(2026, 4, 28), date(2026, 7, 11)),
            ("3º Bimestre", date(2026, 7, 28), date(2026, 10, 3)),
            ("4º Bimestre", date(2026, 10, 6), date(2026, 12, 12)),
        ]
        for i, (name, start, end) in enumerate(bimestres, 1):
            gp = GradePeriod(school_year_id=sy.id, name=name, start_date=start, end_date=end, order_index=i)
            db.session.add(gp)
            periods.append(gp)
        db.session.flush()

        # ── Disciplinas ────────────────────────────────────────────────────
        print("Criando disciplinas…")
        subjects = []
        for name, code, wl in SUBJECTS:
            s = Subject(name=name, code=code, workload_hours=wl)
            db.session.add(s)
            subjects.append(s)
        db.session.flush()

        # ── Professores ────────────────────────────────────────────────────
        print("Criando professores…")
        teacher_data = [
            ("Prof. Carlos Andrade", "professor1@escola.com"),
            ("Profa. Fernanda Lima", "professor2@escola.com"),
            ("Prof. Ricardo Souza", "professor3@escola.com"),
        ]
        teachers = []
        for name, email in teacher_data:
            t = User(name=name, email=email, role="teacher")
            t.set_password("Escola@2025")
            db.session.add(t)
            teachers.append(t)
        db.session.flush()
        for t in teachers:
            db.session.add(UserProfile(user_id=t.id))

        # ── Turmas ─────────────────────────────────────────────────────────
        print("Criando turmas…")
        turma_9a = Class(school_year_id=sy.id, name="9A", grade_level="9º Ano EF", shift="morning", room="101", max_students=30)
        turma_9b = Class(school_year_id=sy.id, name="9B", grade_level="9º Ano EF", shift="afternoon", room="102", max_students=30)
        db.session.add_all([turma_9a, turma_9b])
        db.session.flush()

        # ── Alunos ─────────────────────────────────────────────────────────
        print("Criando alunos…")
        students = []
        parents = []
        for i, name in enumerate(STUDENTS):
            email = f"aluno{i+1:02d}@escola.com"
            s = User(name=name, email=email, role="student")
            s.set_password("Escola@2025")
            db.session.add(s)
            students.append(s)

            # Responsável
            parent_email = f"resp{i+1:02d}@escola.com"
            p = User(name=f"Responsável de {name.split()[0]}", email=parent_email, role="parent")
            p.set_password("Escola@2025")
            db.session.add(p)
            parents.append(p)
        db.session.flush()

        for s in students:
            db.session.add(UserProfile(user_id=s.id))
        for p in parents:
            db.session.add(UserProfile(user_id=p.id))

        # Matricula alunos 1-10 em 9A, 11-20 em 9B
        for s in students[:10]:
            db.session.add(ClassStudent(class_id=turma_9a.id, student_id=s.id))
        for s in students[10:]:
            db.session.add(ClassStudent(class_id=turma_9b.id, student_id=s.id))

        # Vincula responsáveis
        for i, (s, p) in enumerate(zip(students, parents)):
            db.session.add(ParentStudent(parent_id=p.id, student_id=s.id, relationship="mãe" if i % 2 == 0 else "pai"))

        # ── Atribuição de professores às disciplinas ───────────────────────
        print("Atribuindo professores…")
        class_subjects_9a = []
        class_subjects_9b = []

        # prof1: MAT, PORT; prof2: HIST, GEO, CIEN; prof3: EF, ING, ART
        teacher_subj_map = {0: [0, 1], 1: [2, 3, 4], 2: [5, 6, 7]}
        for t_idx, subj_idxs in teacher_subj_map.items():
            for s_idx in subj_idxs:
                cs_a = ClassSubject(class_id=turma_9a.id, subject_id=subjects[s_idx].id, teacher_id=teachers[t_idx].id, school_year_id=sy.id)
                cs_b = ClassSubject(class_id=turma_9b.id, subject_id=subjects[s_idx].id, teacher_id=teachers[t_idx].id, school_year_id=sy.id)
                db.session.add_all([cs_a, cs_b])
                class_subjects_9a.append(cs_a)
                class_subjects_9b.append(cs_b)
        db.session.flush()

        # ── Notas ─────────────────────────────────────────────────────────
        print("Lançando notas…")
        import random
        random.seed(42)
        for cs in class_subjects_9a + class_subjects_9b:
            students_in_class = students[:10] if cs.class_id == turma_9a.id else students[10:]
            for student in students_in_class:
                for period in periods[:2]:  # apenas 1º e 2º bimestres
                    score = round(random.uniform(4.0, 10.0), 1)
                    db.session.add(Grade(
                        student_id=student.id,
                        class_subject_id=cs.id,
                        grade_period_id=period.id,
                        grade_type="prova",
                        score=score,
                    ))
                    score_trab = round(random.uniform(5.0, 10.0), 1)
                    db.session.add(Grade(
                        student_id=student.id,
                        class_subject_id=cs.id,
                        grade_period_id=period.id,
                        grade_type="trabalho",
                        score=score_trab,
                    ))

        # ── Chamadas ───────────────────────────────────────────────────────
        print("Gerando chamadas…")
        today = date.today()
        for cs in class_subjects_9a[:3]:  # chamadas apenas em 3 disciplinas da 9A
            students_in_class = students[:10]
            for delta in range(10):  # 10 aulas
                session_date = today - timedelta(days=delta * 2)
                if session_date < sy.start_date:
                    break
                att_sess = AttendanceSession(
                    class_id=turma_9a.id,
                    class_subject_id=cs.id,
                    teacher_id=cs.teacher_id,
                    date=session_date,
                    lesson_number=1,
                )
                db.session.add(att_sess)
                db.session.flush()
                for student in students_in_class:
                    status = "present" if random.random() > 0.15 else "absent"
                    db.session.add(AttendanceRecord(
                        session_id=att_sess.id,
                        student_id=student.id,
                        status=status,
                    ))

        # ── Atividades ─────────────────────────────────────────────────────
        print("Criando atividades…")
        from datetime import datetime, timezone
        cs_mat = class_subjects_9a[0]  # Matemática 9A
        a1 = Assignment(
            class_subject_id=cs_mat.id,
            teacher_id=cs_mat.teacher_id,
            title="Lista de Exercícios — Equações",
            description="Resolva os exercícios 1 a 15 do livro.",
            due_date=datetime.now(timezone.utc) + timedelta(days=7),
            max_score=10,
            type="homework",
        )
        a2 = Assignment(
            class_subject_id=cs_mat.id,
            teacher_id=cs_mat.teacher_id,
            title="Trabalho em Grupo — Geometria",
            description="Apresentação sobre figuras geométricas.",
            due_date=datetime.now(timezone.utc) + timedelta(days=14),
            max_score=10,
            type="project",
        )
        db.session.add_all([a1, a2])

        # ── Calendário ─────────────────────────────────────────────────────
        print("Criando calendário…")
        calendar_events = [
            ("Recesso de Julho", date(2026, 7, 13), date(2026, 7, 25), "holiday"),
            ("Conselho de Classe", date(2026, 4, 27), None, "meeting"),
            ("Simulado ENEM", date(2026, 9, 12), None, "exam"),
            ("Festa Junina", date(2026, 6, 13), None, "event"),
            ("Prazo — Notas 1º Bimestre", date(2026, 4, 25), None, "deadline"),
        ]
        for title, ev_date, end_date, ev_type in calendar_events:
            db.session.add(CalendarEvent(
                school_year_id=sy.id,
                title=title,
                event_date=ev_date,
                end_date=end_date,
                type=ev_type,
                is_public=True,
                created_by=director.id,
            ))

        db.session.commit()
        print("\nSeed concluído com sucesso!")
        print(f"   Diretor:     diretor@escola.com / Escola@2025")
        print(f"   Professores: professor1@escola.com, professor2@escola.com, professor3@escola.com")
        print(f"   Alunos:      aluno01@escola.com … aluno20@escola.com")
        print(f"   Responsáveis:resp01@escola.com … resp20@escola.com")
        print(f"   Senha de todos: Escola@2025")
        print(f"\nPara iniciar: python run.py")


if __name__ == "__main__":
    seed()
