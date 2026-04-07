"""
conftest.py — Fixtures compartilhadas para todos os testes.

Usa banco SQLite in-memory e CSRF desativado (TestingConfig).
Cada teste recebe um banco limpo (function-scoped app + db).
"""
import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db

# Re-export helpers so they're importable from this module too
from helpers import (  # noqa: F401
    make_user, make_school_year, make_subject, make_class,
    make_class_subject, login, logout,
)


@pytest.fixture(scope="function")
def app():
    """Fresh in-memory DB for every test — fast with SQLite."""
    _app = create_app(TestingConfig)
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Yields the db bound to the current app context."""
    yield _db
    _db.session.remove()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()
