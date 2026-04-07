# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server
python run.py

# Database migrations
FLASK_APP=run.py flask db migrate -m "description"
FLASK_APP=run.py flask db upgrade

# Populate test data (drops and recreates all tables)
python seed.py

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_api.py -v

# Run a single test by name
python -m pytest tests/test_services.py::test_grade_calculation -v
```

## Architecture

The app uses a strict 3-layer call chain:

```
Blueprint route  →  Service  →  Repository  →  SQLAlchemy ORM  →  DB
```

Blueprints **never** call repositories directly. Repositories **never** contain business logic.

### Database abstraction

Changing database engine = changing `DATABASE_URL` in `.env` only. No code changes needed. SQLite for dev, PostgreSQL/MySQL in prod via SQLAlchemy dialect abstraction.

### Key entry points

- `app/__init__.py` — `create_app()` factory; registers all blueprints and extensions
- `app/extensions.py` — shared `db`, `login_manager`, `csrf`, `limiter` instances
- `app/config.py` — `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`; business rules (`MIN_PASSING_GRADE`, `MAX_ABSENCE_PERCENT`) live here
- `app/utils/decorators.py` — `@role_required(*roles)` RBAC decorator used on every protected route

### Roles and blueprints

| Role | Blueprint prefix | Scope |
|------|-----------------|-------|
| `director` | `/director` | Full CRUD on everything |
| `teacher` | `/teacher` | Only their assigned `ClassSubject` records |
| `student` | `/student` | Read-only, own data |
| `parent` | `/parent` | Read-only, linked children via `ParentStudent` |

The `api` blueprint (`/api/v1`) serves JSON for Chart.js and AJAX (attendance bulk-save, grade bulk-save, notification polling). All API routes send `X-CSRFToken` from the `<meta name="csrf-token">` tag injected by `base.html`.

### Core models

- `ClassSubject` is the pivot table linking `Class` + `Subject` + `User (teacher)` + `SchoolYear`. Attendance sessions, grades, assignments, and schedules all hang off `ClassSubject.id`.
- `AttendanceSession` → `AttendanceRecord` (one session per class/subject/date/lesson_number, one record per student)
- `Grade` has a unique constraint on `(student_id, class_subject_id, grade_period_id, grade_type)` — upsert via `GradeRepository.upsert()`

### Frontend

Templates use Jinja2 server-side rendering. AJAX is used selectively:
- Attendance bulk-save: `POST /api/v1/attendance/bulk-save`
- Grade bulk-save: `POST /api/v1/grades/bulk-save`
- Notification polling: `GET /api/v1/notifications/unread` every 60 s

JS helpers in `static/js/main.js`: `getCsrfToken()` reads from `<meta name="csrf-token">` in `base.html`. `static/js/charts.js` contains `createBarChart()`, `createRadarChart()`, `createAttendanceDonut()` — all fetch from `/api/v1/`.

### Test setup

`tests/conftest.py` uses `TestingConfig` (in-memory SQLite, CSRF disabled). The `client` fixture is an authenticated Flask test client. Seed helpers create minimal data per test without relying on the full `seed.py` script.
