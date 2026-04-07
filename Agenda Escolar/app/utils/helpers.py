from datetime import datetime


def format_date(d, fmt="%d/%m/%Y"):
    if d is None:
        return "-"
    if isinstance(d, datetime):
        return d.strftime(fmt)
    return d.strftime(fmt)


def format_score(score):
    if score is None:
        return "-"
    return f"{float(score):.1f}"


def grade_color_class(score, min_passing=5.0, warning=7.0):
    """Retorna classe CSS Tailwind baseada na nota."""
    if score is None:
        return "text-gray-400"
    score = float(score)
    if score < min_passing:
        return "text-red-600 font-semibold"
    if score < warning:
        return "text-yellow-600 font-semibold"
    return "text-green-600 font-semibold"


def attendance_color_class(percent_absent, threshold=25.0):
    """Retorna classe CSS Tailwind baseada no percentual de faltas."""
    if percent_absent >= threshold:
        return "text-red-600 font-semibold"
    if percent_absent >= threshold * 0.75:
        return "text-yellow-600"
    return "text-green-600"


def active_school_year():
    """Retorna o ano letivo ativo ou None."""
    from ..models.school_year import SchoolYear
    from ..extensions import db
    return db.session.execute(
        db.select(SchoolYear).where(SchoolYear.is_active == True)
    ).scalar_one_or_none()


_MONTH_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def format_month(d):
    """Retorna 'Mês Ano' em português, ex: 'Abril 2025'."""
    if d is None:
        return "-"
    return f"{_MONTH_PT[d.month]} {d.year}"


def register_template_filters(app):
    """Registra filtros Jinja2 customizados."""
    app.jinja_env.filters["format_date"] = format_date
    app.jinja_env.filters["format_month"] = format_month
    app.jinja_env.filters["format_score"] = format_score
    app.jinja_env.filters["grade_color"] = grade_color_class
    app.jinja_env.filters["attendance_color"] = attendance_color_class
    app.jinja_env.globals["active_school_year"] = active_school_year
