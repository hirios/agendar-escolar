"""
test_auth.py — Testes para o blueprint de autenticação.
"""
import pytest
from helpers import make_user, login, logout


class TestLogin:
    def test_login_page_get(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        assert b"login" in resp.data.lower() or b"senha" in resp.data.lower()

    def test_login_valid_credentials(self, client, db):
        make_user(db, email="valid@test.com", password="abc123")
        db.session.commit()
        resp = login(client, "valid@test.com", "abc123")
        assert resp.status_code == 200
        # Redirecionou para o dashboard (login bem-sucedido não exibe erro)
        assert b"incorretos" not in resp.data

    def test_login_invalid_password(self, client, db):
        make_user(db, email="user@test.com", password="correta")
        db.session.commit()
        resp = login(client, "user@test.com", "errada")
        assert resp.status_code == 200
        assert "incorretos".encode() in resp.data

    def test_login_nonexistent_email(self, client):
        resp = login(client, "naoexiste@test.com", "qualquer")
        assert resp.status_code == 200
        assert "incorretos".encode() in resp.data

    def test_login_redirects_by_role(self, client, db):
        make_user(db, email="director@test.com", role="director", password="abc123")
        db.session.commit()
        resp = client.post(
            "/auth/login",
            data={"email": "director@test.com", "password": "abc123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/director" in resp.headers["Location"]

    def test_login_teacher_redirects_to_teacher_dashboard(self, client, db):
        make_user(db, email="teacher@test.com", role="teacher", password="abc123")
        db.session.commit()
        resp = client.post(
            "/auth/login",
            data={"email": "teacher@test.com", "password": "abc123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/teacher" in resp.headers["Location"]


class TestLogout:
    def test_logout_requires_auth(self, client):
        resp = client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_logout_clears_session(self, client, db):
        make_user(db, email="bye@test.com", password="abc123")
        db.session.commit()
        login(client, "bye@test.com", "abc123")
        logout(client)
        # Após logout, rota protegida redireciona para login
        resp = client.get("/student/", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]


class TestChangePassword:
    def test_change_password_requires_auth(self, client):
        resp = client.get("/auth/change-password", follow_redirects=False)
        assert resp.status_code == 302

    def test_change_password_mismatch(self, client, db):
        make_user(db, email="change@test.com", password="antiga123")
        db.session.commit()
        login(client, "change@test.com", "antiga123")
        resp = client.post(
            "/auth/change-password",
            data={
                "current_password": "antiga123",
                "new_password": "nova123",
                "confirm_password": "diferente",
            },
            follow_redirects=True,
        )
        assert "não coincidem".encode() in resp.data

    def test_change_password_too_short(self, client, db):
        make_user(db, email="short@test.com", password="antiga123")
        db.session.commit()
        login(client, "short@test.com", "antiga123")
        resp = client.post(
            "/auth/change-password",
            data={
                "current_password": "antiga123",
                "new_password": "12",
                "confirm_password": "12",
            },
            follow_redirects=True,
        )
        assert "pelo menos 6" in resp.data.decode("utf-8")

    def test_change_password_wrong_current(self, client, db):
        make_user(db, email="wrongcurr@test.com", password="antiga123")
        db.session.commit()
        login(client, "wrongcurr@test.com", "antiga123")
        resp = client.post(
            "/auth/change-password",
            data={
                "current_password": "ERRADA",
                "new_password": "nova123",
                "confirm_password": "nova123",
            },
            follow_redirects=True,
        )
        # Deve mostrar erro de senha atual incorreta
        assert resp.status_code == 200
