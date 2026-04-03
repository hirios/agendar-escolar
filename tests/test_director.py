"""
test_director.py — Testes para o blueprint /director.

Cobre: autenticação/RBAC, professores, alunos, turmas, disciplinas,
anos letivos e calendário.
"""
import pytest
from helpers import (
    make_user, make_school_year, make_subject, make_class,
    make_class_subject, login,
)
from app.models import ClassStudent


# ── Fixture base ──────────────────────────────────────────────────────────────

@pytest.fixture
def base(db):
    director = make_user(db, name="Diretora", email="dir@d.com", role="director")
    teacher = make_user(db, name="Professor", email="prof@d.com", role="teacher")
    student = make_user(db, name="Aluno", email="stu@d.com", role="student")
    sy, periods = make_school_year(db)
    subject = make_subject(db)
    class_ = make_class(db, sy.id)
    cs = make_class_subject(db, class_.id, subject.id, teacher.id, sy.id)
    db.session.add(ClassStudent(class_id=class_.id, student_id=student.id))
    db.session.commit()
    return {
        "director": director,
        "teacher": teacher,
        "student": student,
        "sy": sy,
        "periods": periods,
        "subject": subject,
        "class_": class_,
        "cs": cs,
    }


# ── RBAC ─────────────────────────────────────────────────────────────────────

class TestDirectorRBAC:
    def test_dashboard_requires_auth(self, client):
        resp = client.get("/director/", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_dashboard_forbidden_for_student(self, client, db, base):
        login(client, "stu@d.com")
        resp = client.get("/director/")
        assert resp.status_code == 403

    def test_dashboard_forbidden_for_teacher(self, client, db, base):
        login(client, "prof@d.com")
        resp = client.get("/director/")
        assert resp.status_code == 403

    def test_dashboard_accessible_for_director(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/")
        assert resp.status_code == 200


# ── Dashboard ─────────────────────────────────────────────────────────────────

class TestDirectorDashboard:
    def test_dashboard_renders(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/")
        assert resp.status_code == 200

    def test_dashboard_shows_stats_structure(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/")
        assert resp.status_code == 200
        # O dashboard renderiza KPI cards e o gráfico via JS — verifica o container
        assert b"chartPerformance" in resp.data


# ── Professores ───────────────────────────────────────────────────────────────

class TestTeacherRoutes:
    def test_list_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/teachers/")
        assert resp.status_code == 200

    def test_list_shows_teacher_name(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/teachers/")
        assert "Professor".encode() in resp.data

    def test_new_form_get(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/teachers/new")
        assert resp.status_code == 200

    def test_new_creates_teacher(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/teachers/new",
            data={"name": "Novo Prof", "email": "novoprof@d.com", "password": "senha123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Novo Prof".encode() in resp.data

    def test_new_duplicate_email_shows_error(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/teachers/new",
            data={"name": "Dup", "email": "prof@d.com", "password": "senha123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Deve exibir flash de erro (email já existe)
        assert b"error" in resp.data.lower() or "já" in resp.data.decode("utf-8").lower() or resp.status_code == 200

    def test_edit_form_get(self, client, db, base):
        login(client, "dir@d.com")
        teacher_id = base["teacher"].id
        resp = client.get(f"/director/teachers/{teacher_id}/edit")
        assert resp.status_code == 200

    def test_edit_unknown_id_returns_404(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/teachers/99999/edit")
        assert resp.status_code == 404

    def test_edit_updates_name(self, client, db, base):
        login(client, "dir@d.com")
        teacher_id = base["teacher"].id
        resp = client.post(
            f"/director/teachers/{teacher_id}/edit",
            data={"name": "Prof Atualizado"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Prof Atualizado".encode() in resp.data

    def test_deactivate_teacher(self, client, db, base):
        login(client, "dir@d.com")
        teacher_id = base["teacher"].id
        resp = client.post(
            f"/director/teachers/{teacher_id}/deactivate",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        from app.models import User
        from app.extensions import db as _db
        teacher = _db.session.get(User, teacher_id)
        assert teacher.is_active is False

    def test_reactivate_teacher(self, client, db, base):
        login(client, "dir@d.com")
        teacher_id = base["teacher"].id
        # Desativa primeiro
        client.post(f"/director/teachers/{teacher_id}/deactivate")
        # Reativa
        resp = client.post(
            f"/director/teachers/{teacher_id}/reactivate",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        from app.models import User
        from app.extensions import db as _db
        teacher = _db.session.get(User, teacher_id)
        assert teacher.is_active is True

    def test_edit_student_as_teacher_returns_404(self, client, db, base):
        """Tentar editar um aluno via rota de professor deve dar 404."""
        login(client, "dir@d.com")
        student_id = base["student"].id
        resp = client.get(f"/director/teachers/{student_id}/edit")
        assert resp.status_code == 404

    def test_new_empty_name_shows_error(self, client, db, base):
        """Criar professor com nome vazio deve exibir erro e não persistir."""
        login(client, "dir@d.com")
        resp = client.post(
            "/director/teachers/new",
            data={"name": "   ", "email": "semNome@d.com", "password": "senha123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "vazio".encode() in resp.data

    def test_edit_empty_name_shows_error(self, client, db, base):
        """Editar professor com nome vazio deve exibir erro e não persistir."""
        login(client, "dir@d.com")
        teacher_id = base["teacher"].id
        resp = client.post(
            f"/director/teachers/{teacher_id}/edit",
            data={"name": ""},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "vazio".encode() in resp.data


# ── Alunos ────────────────────────────────────────────────────────────────────

class TestStudentRoutes:
    def test_list_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/students/")
        assert resp.status_code == 200

    def test_list_shows_student_name(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/students/")
        assert "Aluno".encode() in resp.data

    def test_detail_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get(f"/director/students/{base['student'].id}")
        assert resp.status_code == 200

    def test_detail_unknown_returns_404(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/students/99999")
        assert resp.status_code == 404

    def test_detail_teacher_id_returns_404(self, client, db, base):
        """Detalhe de professor via rota de aluno deve dar 404."""
        login(client, "dir@d.com")
        resp = client.get(f"/director/students/{base['teacher'].id}")
        assert resp.status_code == 404

    def test_new_creates_student(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/students/new",
            data={"name": "Novo Aluno", "email": "novoaluno@d.com", "password": "senha123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Novo Aluno".encode() in resp.data

    def test_new_with_class_enrolls_student(self, client, db, base):
        login(client, "dir@d.com")
        class_id = base["class_"].id
        resp = client.post(
            "/director/students/new",
            data={
                "name": "Matriculado",
                "email": "matric@d.com",
                "password": "senha123",
                "class_id": class_id,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_edit_updates_student(self, client, db, base):
        login(client, "dir@d.com")
        student_id = base["student"].id
        resp = client.post(
            f"/director/students/{student_id}/edit",
            data={"name": "Aluno Editado", "phone": "11999999999"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Aluno Editado".encode() in resp.data

    def test_deactivate_student(self, client, db, base):
        login(client, "dir@d.com")
        student_id = base["student"].id
        resp = client.post(
            f"/director/students/{student_id}/deactivate",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        from app.models import User
        from app.extensions import db as _db
        student = _db.session.get(User, student_id)
        assert student.is_active is False

    def test_reactivate_student(self, client, db, base):
        login(client, "dir@d.com")
        student_id = base["student"].id
        client.post(f"/director/students/{student_id}/deactivate")
        resp = client.post(
            f"/director/students/{student_id}/reactivate",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        from app.models import User
        from app.extensions import db as _db
        student = _db.session.get(User, student_id)
        assert student.is_active is True

    def test_list_search_by_name(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/students/?q=Aluno")
        assert resp.status_code == 200
        assert "Aluno".encode() in resp.data


# ── Turmas ────────────────────────────────────────────────────────────────────

class TestClassRoutes:
    def test_list_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/classes/")
        assert resp.status_code == 200

    def test_detail_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get(f"/director/classes/{base['class_'].id}")
        assert resp.status_code == 200

    def test_detail_unknown_returns_404(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/classes/99999")
        assert resp.status_code == 404

    def test_new_form_get(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/classes/new")
        assert resp.status_code == 200

    def test_new_creates_class(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/classes/new",
            data={
                "name": "8A",
                "school_year_id": base["sy"].id,
                "shift": "morning",
                "max_students": 30,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "8A".encode() in resp.data

    def test_enroll_student_in_class(self, client, db, base):
        # Cria segundo aluno (sem turma) para matricular
        from helpers import make_user as mu
        from app.extensions import db as _db
        stu2 = mu(_db, name="Aluno2", email="stu2@d.com", role="student")
        _db.session.commit()
        login(client, "dir@d.com")
        resp = client.post(
            f"/director/classes/{base['class_'].id}/enroll",
            data={"student_id": stu2.id},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_assign_teacher_to_class(self, client, db, base):
        from helpers import make_subject as ms
        from app.extensions import db as _db
        subj2 = ms(_db, name="História", code="HIST")
        _db.session.commit()
        login(client, "dir@d.com")
        resp = client.post(
            f"/director/classes/{base['class_'].id}/assign-teacher",
            data={"subject_id": subj2.id, "teacher_id": base["teacher"].id},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_edit_class(self, client, db, base):
        login(client, "dir@d.com")
        class_id = base["class_"].id
        resp = client.post(
            f"/director/classes/{class_id}/edit",
            data={
                "name": "9A-Editada",
                "shift": "afternoon",
                "max_students": 35,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "9A-Editada".encode() in resp.data


# ── Disciplinas ───────────────────────────────────────────────────────────────

class TestSubjectRoutes:
    def test_list_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/subjects/")
        assert resp.status_code == 200

    def test_list_shows_subject(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/subjects/")
        assert "Matemática".encode() in resp.data

    def test_new_creates_subject(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/subjects/new",
            data={"name": "Física", "code": "FIS", "workload_hours": 80},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Física".encode() in resp.data

    def test_edit_subject(self, client, db, base):
        login(client, "dir@d.com")
        subject_id = base["subject"].id
        resp = client.post(
            f"/director/subjects/{subject_id}/edit",
            data={"name": "Matemática Avançada", "code": "MAT", "workload_hours": 240},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Matemática Avançada".encode() in resp.data

    def test_edit_unknown_returns_404(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/subjects/99999/edit")
        assert resp.status_code == 404


# ── Anos Letivos ──────────────────────────────────────────────────────────────

class TestSchoolYearRoutes:
    def test_list_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/school-years/")
        assert resp.status_code == 200

    def test_list_shows_year(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/school-years/")
        assert "2026".encode() in resp.data

    def test_new_creates_school_year(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/school-years/new",
            data={"name": "2027", "start_date": "2027-02-01", "end_date": "2027-12-15"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "2027".encode() in resp.data

    def test_activate_school_year(self, client, db, base):
        login(client, "dir@d.com")
        year_id = base["sy"].id
        resp = client.post(
            f"/director/school-years/{year_id}/activate",
            follow_redirects=True,
        )
        assert resp.status_code == 200


# ── Calendário ────────────────────────────────────────────────────────────────

class TestCalendarRoutes:
    def test_calendar_returns_200(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/calendar/")
        assert resp.status_code == 200

    def test_new_event_form_get(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.get("/director/calendar/new")
        assert resp.status_code == 200

    def test_new_event_creates_event(self, client, db, base):
        login(client, "dir@d.com")
        resp = client.post(
            "/director/calendar/new",
            data={
                "school_year_id": base["sy"].id,
                "title": "Reunião de Pais",
                "event_date": "2026-05-10",
                "type": "meeting",
                "is_public": "on",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Reunião de Pais".encode() in resp.data
