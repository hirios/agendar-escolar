"""
helpers.py — Funções auxiliares para criação de dados nos testes.
"""
from app.models import (
    User, UserProfile, SchoolYear, GradePeriod, Subject,
    Class, ClassStudent, ClassSubject,
)
from datetime import date


def make_user(db, name="Test User", email="test@test.com", role="student", password="senha123"):
    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    db.session.add(UserProfile(user_id=u.id))
    return u


def make_school_year(db, name="2026", active=True):
    sy = SchoolYear(
        name=name,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 12, 15),
        is_active=active,
    )
    db.session.add(sy)
    db.session.flush()
    periods = []
    for i, pname in enumerate(["1º Bimestre", "2º Bimestre", "3º Bimestre", "4º Bimestre"], 1):
        gp = GradePeriod(school_year_id=sy.id, name=pname, order_index=i)
        db.session.add(gp)
        periods.append(gp)
    db.session.flush()
    return sy, periods


def make_subject(db, name="Matemática", code="MAT"):
    s = Subject(name=name, code=code, workload_hours=200)
    db.session.add(s)
    db.session.flush()
    return s


def make_class(db, school_year_id, name="9A"):
    c = Class(school_year_id=school_year_id, name=name, shift="morning")
    db.session.add(c)
    db.session.flush()
    return c


def make_class_subject(db, class_id, subject_id, teacher_id, school_year_id):
    cs = ClassSubject(
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        school_year_id=school_year_id,
    )
    db.session.add(cs)
    db.session.flush()
    return cs


def login(client, email, password="senha123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.get("/auth/logout", follow_redirects=True)
