from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

# --------------------------------------------------
# COLLEGE (ROOT / SUPERSET ENTITY)
# --------------------------------------------------
class College(db.Model):
    __tablename__ = "colleges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    admins = db.relationship("Admin", backref="college", lazy=True)
    students = db.relationship("Student", backref="college", lazy=True)
    companies = db.relationship("Company", backref="college", lazy=True)
    job_posts = db.relationship("JobPost", backref="college", lazy=True)
    blogs = db.relationship("Blog", backref="college", lazy=True)


# --------------------------------------------------
# USERS (AUTHENTICATION BASE TABLE)
# --------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-one role relationships
    admin = db.relationship("Admin", backref="user", uselist=False)
    student = db.relationship("Student", backref="user", uselist=False)
    company = db.relationship("Company", backref="user", uselist=False)


# --------------------------------------------------
# ADMIN (PRE-DEFINED SUPERUSER)
# --------------------------------------------------
class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    college_id = db.Column(
        db.Integer,
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False
    )
    notification_email = db.Column(db.String(120))
    receive_notifications = db.Column(db.Boolean, default=True)

    blogs = db.relationship("Blog", backref="admin", lazy=True)


# --------------------------------------------------
# STUDENT
# --------------------------------------------------
class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    college_id = db.Column(
        db.Integer,
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(50))
    branch = db.Column(db.String(100))
    cgpa = db.Column(db.Float)
    year_of_study = db.Column(db.Integer)
    resume_path = db.Column(db.String(200))
    is_placed = db.Column(db.Boolean, default=False)
    notification_email = db.Column(db.String(120))
    receive_notifications = db.Column(db.Boolean, default=True)

    applications = db.relationship("Application", backref="student", lazy=True)
    profile_photo = db.Column(db.String(200))


# --------------------------------------------------
# COMPANY
# --------------------------------------------------
class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    college_id = db.Column(
        db.Integer,
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    hr_email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    approval_status = db.Column(
        db.String(20),
        nullable=False,
        default="PENDING"  # PENDING | APPROVED | REJECTED
    )
    is_blacklisted = db.Column(db.Boolean, default=False)

    job_posts = db.relationship("JobPost", backref="company", lazy=True)
    logo = db.Column(db.String(200))


# --------------------------------------------------
# JOB POSTS / PLACEMENT DRIVES
# --------------------------------------------------
class JobPost(db.Model):
    __tablename__ = "job_posts"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False
    )
    college_id = db.Column(
        db.Integer,
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False
    )

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    min_cgpa = db.Column(db.Float)
    eligible_branches = db.Column(db.Text)
    eligible_years = db.Column(db.Text)
    application_deadline = db.Column(db.Date)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="PENDING"  # PENDING | APPROVED | CLOSED
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("Application", backref="job_post", lazy=True)

    def _normalize_tokens(self, value):
        if not value:
            return set()
        return {token.strip().upper() for token in str(value).split(",") if token and token.strip()}

    def get_eligibility_reasons(self, student):
        reasons = []

        if self.min_cgpa is not None:
            student_cgpa = getattr(student, "cgpa", None)
            if student_cgpa is None or float(student_cgpa) < float(self.min_cgpa):
                reasons.append(f"Minimum CGPA of {self.min_cgpa:.2f} is required.")

        if self.eligible_branches:
            student_branch = getattr(student, "branch", None)
            allowed_branches = self._normalize_tokens(self.eligible_branches)
            if not student_branch or student_branch.strip().upper() not in allowed_branches:
                reasons.append(f"Eligible branches: {self.eligible_branches}.")

        if self.eligible_years:
            student_year = getattr(student, "year_of_study", None)
            allowed_years = set()
            for token in str(self.eligible_years).split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    allowed_years.add(int(token))
                except ValueError:
                    continue
            if student_year is None or int(student_year) not in allowed_years:
                reasons.append(f"Eligible years: {self.eligible_years}.")

        return reasons

    def is_eligible_for(self, student):
        return len(self.get_eligibility_reasons(student)) == 0


# --------------------------------------------------
# APPLICATIONS (STUDENT ↔ JOB POST)
# --------------------------------------------------
class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False
    )
    job_post_id = db.Column(
        db.Integer,
        db.ForeignKey("job_posts.id", ondelete="CASCADE"),
        nullable=False
    )

    applied_on = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(
        db.String(30),
        nullable=False,
        default="APPLIED"
        # APPLIED | SHORTLISTED | INTERVIEW_SCHEDULED | SELECTED | REJECTED
    )
    interview_date = db.Column(db.DateTime)
    interview_mode = db.Column(db.String(50))
    interview_notes = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "job_post_id",
            name="uq_student_job_application"
        ),
    )


# --------------------------------------------------
# BLOGS / ANNOUNCEMENTS (ADMIN CONTROLLED)
# --------------------------------------------------
class ExportJob(db.Model):
    __tablename__ = "export_jobs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False
    )
    task_id = db.Column(db.String(100), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="PENDING")
    file_path = db.Column(db.String(300))
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    student = db.relationship("Student", backref="export_jobs", lazy=True)


class Blog(db.Model):
    __tablename__ = "blogs"

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(
        db.Integer,
        db.ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False
    )
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False
    )

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
