"""
test_reports.py — Testes para o blueprint /reports.

Cobre: RBAC, preview HTML e geração de PDF (boletim).
"""
import pytest
from helpers import (
    make_user, make_school_year, make_subject, make_class,
    make_class_subject, login,
)
from app.models import ClassStudent
from app.services.grade_service import GradeService


@pytest.fixture
def base(db):
    director = make_user(db, name="Diretora", email="dir@r.com", role="director")
    teacher = make_user(db, name="Professor", email="prof@r.com", role="teacher")
    student = make_user(db, name="Ana Lima", email="ana@r.com", role="student")
    parent = make_user(db, name="Mae Ana", email="mae@r.com", role="parent")
    other_student = make_user(db, name="Bruno Costa", email="bruno@r.com", role="student")
    sy, periods = make_school_year(db)
    subject = make_subject(db)
    class_ = make_class(db, sy.id)
    cs = make_class_subject(db, class_.id, subject.id, teacher.id, sy.id)
    db.session.add(ClassStudent(class_id=class_.id, student_id=student.id))

    # Vincula responsável ao aluno
    from app.models import ParentStudent
    db.session.add(ParentStudent(parent_id=parent.id, student_id=student.id, relationship="mãe"))

    # Adiciona algumas notas para o boletim ter conteúdo
    db.session.commit()
    svc = GradeService()
    svc.save_grade(
        student_id=student.id,
        class_subject_id=cs.id,
        grade_period_id=periods[0].id,
        grade_type="prova",
        score=8.0,
    )

    return {
        "director": director,
        "teacher": teacher,
        "student": student,
        "parent": parent,
        "other_student": other_student,
        "sy": sy,
        "periods": periods,
        "cs": cs,
    }


class TestBoletimPreview:
    def test_requires_auth(self, client, db, base):
        resp = client.get(f"/reports/boletim/{base['student'].id}", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_director_can_view(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}")
        assert resp.status_code == 200

    def test_teacher_can_view(self, client, db, base):
        login(client, "prof@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}")
        assert resp.status_code == 200

    def test_student_can_view_own(self, client, db, base):
        login(client, "ana@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}")
        assert resp.status_code == 200

    def test_student_cannot_view_other(self, client, db, base):
        login(client, "ana@r.com")
        resp = client.get(f"/reports/boletim/{base['other_student'].id}")
        assert resp.status_code == 403

    def test_parent_can_view_child(self, client, db, base):
        login(client, "mae@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}")
        assert resp.status_code == 200

    def test_parent_cannot_view_unlinked_student(self, client, db, base):
        login(client, "mae@r.com")
        resp = client.get(f"/reports/boletim/{base['other_student'].id}")
        assert resp.status_code == 403

    def test_preview_contains_student_name(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}")
        assert "Ana Lima".encode() in resp.data

    def test_unknown_student_returns_404(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get("/reports/boletim/99999")
        assert resp.status_code == 404


def _weasyprint_available():
    """Retorna True só se WeasyPrint E as libs de sistema (GTK) estiverem prontas."""
    try:
        from weasyprint import HTML
        HTML(string="<p>ok</p>").write_pdf()
        return True
    except Exception:
        return False


weasyprint_ready = pytest.mark.skipif(
    not _weasyprint_available(),
    reason="WeasyPrint ou libs GTK de sistema não disponíveis neste ambiente",
)


class TestBoletimPDF:
    def test_requires_auth(self, client, db, base):
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf", follow_redirects=False)
        assert resp.status_code == 302

    def test_weasyprint_package_installed(self):
        """Garante que o pacote weasyprint está instalado (pip).
        OSError indica que o pacote existe mas faltam libs de sistema (GTK) — aceitável em CI/dev Windows.
        """
        try:
            import weasyprint  # noqa: F401
        except ImportError:
            pytest.fail("WeasyPrint não instalado. Execute: pip install weasyprint")
        except OSError:
            pytest.skip("WeasyPrint instalado mas libs GTK ausentes — instale o runtime GTK3")

    def test_student_cannot_download_other_pdf(self, client, db, base):
        login(client, "ana@r.com")
        resp = client.get(f"/reports/boletim/{base['other_student'].id}/pdf")
        assert resp.status_code == 403

    def test_parent_cannot_download_unlinked_pdf(self, client, db, base):
        login(client, "mae@r.com")
        resp = client.get(f"/reports/boletim/{base['other_student'].id}/pdf")
        assert resp.status_code == 403

    def test_unknown_student_returns_404(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get("/reports/boletim/99999/pdf")
        assert resp.status_code == 404

    @weasyprint_ready
    def test_director_downloads_pdf(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    @weasyprint_ready
    def test_pdf_has_content(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf")
        assert len(resp.data) > 1000

    @weasyprint_ready
    def test_student_downloads_own_pdf(self, client, db, base):
        login(client, "ana@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    @weasyprint_ready
    def test_parent_downloads_child_pdf(self, client, db, base):
        login(client, "mae@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    @weasyprint_ready
    def test_filename_contains_student_name(self, client, db, base):
        login(client, "dir@r.com")
        resp = client.get(f"/reports/boletim/{base['student'].id}/pdf")
        assert resp.status_code == 200
        disposition = resp.headers.get("Content-Disposition", "")
        assert "Ana_Lima" in disposition
