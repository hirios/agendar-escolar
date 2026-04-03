from ..extensions import db


class SchoolYear(db.Model):
    __tablename__ = "school_years"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    classes = db.relationship("Class", back_populates="school_year", lazy="dynamic")
    grade_periods = db.relationship("GradePeriod", back_populates="school_year", order_by="GradePeriod.order_index", cascade="all, delete-orphan")
    calendar_events = db.relationship("CalendarEvent", back_populates="school_year", lazy="dynamic")

    def __repr__(self):
        return f"<SchoolYear {self.name}>"


class GradePeriod(db.Model):
    __tablename__ = "grade_periods"

    id = db.Column(db.Integer, primary_key=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_years.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    order_index = db.Column(db.Integer, nullable=False, default=1)

    school_year = db.relationship("SchoolYear", back_populates="grade_periods")
    grades = db.relationship("Grade", back_populates="grade_period", lazy="dynamic")

    def __repr__(self):
        return f"<GradePeriod {self.name}>"
