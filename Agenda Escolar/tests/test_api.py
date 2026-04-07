"""
test_api.py — Testes para o blueprint /api/v1.
"""
import json
import pytest
from helpers import (
    make_user, make_school_year, make_subject, make_class,
    make_class_subject, login,
)


@pytest.fixture
def setup_data(db):
    """Cria estrutura mínima: diretor, professor, aluno, turma, disciplina."""
    director = make_user(db, name="Dir", email="dir@api.com", role="director")
    teacher = make_user(db, name="Prof", email="prof@api.com", role="teacher")
    student = make_user(db, name="Stu", email="stu@api.com", role="student")
    sy, periods = make_school_year(db)
    subject = make_subject(db)
    class_ = make_class(db, sy.id)
    cs = make_class_subject(db, class_.id, subject.id, teacher.id, sy.id)
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


class TestDashboardStats:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/dashboard/stats")
        assert resp.status_code in (302, 401)

    def test_forbidden_for_non_director(self, client, db, setup_data):
        login(client, "prof@api.com")
        resp = client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 403

    def test_returns_json_for_director(self, client, db, setup_data):
        login(client, "dir@api.com")
        resp = client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, dict)


class TestSubjectsAverages:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/subjects/averages")
        assert resp.status_code in (302, 401)

    def test_returns_list_for_director(self, client, db, setup_data):
        login(client, "dir@api.com")
        resp = client.get("/api/v1/subjects/averages")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_returns_list_for_teacher(self, client, db, setup_data):
        login(client, "prof@api.com")
        resp = client.get("/api/v1/subjects/averages")
        assert resp.status_code == 200


class TestClassPerformance:
    def test_requires_auth(self, client, db, setup_data):
        class_id = setup_data["class_"].id
        resp = client.get(f"/api/v1/classes/{class_id}/performance")
        assert resp.status_code in (302, 401)

    def test_returns_list(self, client, db, setup_data):
        login(client, "dir@api.com")
        class_id = setup_data["class_"].id
        resp = client.get(f"/api/v1/classes/{class_id}/performance")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)


class TestStudentPerformance:
    def test_requires_auth(self, client, db, setup_data):
        student_id = setup_data["student"].id
        resp = client.get(f"/api/v1/students/{student_id}/performance")
        assert resp.status_code in (302, 401)

    def test_returns_list(self, client, db, setup_data):
        login(client, "dir@api.com")
        student_id = setup_data["student"].id
        resp = client.get(f"/api/v1/students/{student_id}/performance")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)


class TestNotificationsUnread:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/notifications/unread")
        assert resp.status_code in (302, 401)

    def test_returns_count_and_list(self, client, db, setup_data):
        login(client, "dir@api.com")
        resp = client.get("/api/v1/notifications/unread")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "count" in data
        assert "notifications" in data
        assert isinstance(data["notifications"], list)


class TestNotificationsMarkRead:
    def test_requires_auth(self, client):
        resp = client.post("/api/v1/notifications/mark-read")
        assert resp.status_code in (302, 401, 403, 400)

    def test_mark_read_ok(self, client, db, setup_data):
        login(client, "dir@api.com")
        resp = client.post("/api/v1/notifications/mark-read")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get("status") == "ok"


class TestAttendanceBulkSave:
    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/attendance/bulk-save",
            json={"date": "2026-03-01", "class_id": 1, "class_subject_id": 1, "records": []},
        )
        assert resp.status_code in (302, 401)

    def test_missing_body_returns_400(self, client, db, setup_data):
        login(client, "prof@api.com")
        resp = client.post("/api/v1/attendance/bulk-save", data="not json", content_type="text/plain")
        assert resp.status_code in (400, 415)

    def test_saves_attendance(self, client, db, setup_data):
        login(client, "prof@api.com")
        data = setup_data
        student = data["student"]
        # Matricula aluno na turma
        from app.models import ClassStudent
        db.session.add(ClassStudent(class_id=data["class_"].id, student_id=student.id))
        db.session.commit()

        payload = {
            "date": "2026-03-01",
            "class_id": data["class_"].id,
            "class_subject_id": data["cs"].id,
            "records": [{"student_id": student.id, "status": "present"}],
        }
        resp = client.post("/api/v1/attendance/bulk-save", json=payload)
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"


class TestGradesBulkSave:
    def test_requires_auth(self, client):
        resp = client.post("/api/v1/grades/bulk-save", json={"grades": []})
        assert resp.status_code in (302, 401)

    def test_missing_body_returns_400(self, client, db, setup_data):
        login(client, "prof@api.com")
        resp = client.post("/api/v1/grades/bulk-save", data="not json", content_type="text/plain")
        assert resp.status_code in (400, 415)

    def test_saves_grades(self, client, db, setup_data):
        login(client, "prof@api.com")
        data = setup_data
        period = data["periods"][0]
        payload = {
            "grades": [
                {
                    "student_id": data["student"].id,
                    "class_subject_id": data["cs"].id,
                    "grade_period_id": period.id,
                    "grade_type": "prova",
                    "score": 7.5,
                }
            ]
        }
        resp = client.post("/api/v1/grades/bulk-save", json=payload)
        assert resp.status_code == 200
        result = json.loads(resp.data)
        assert result["status"] == "ok"
        assert result["saved"] == 1
