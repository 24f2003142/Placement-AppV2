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
    resume_path = db.Column(db.String(200))
    is_placed = db.Column(db.Boolean, default=False)

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
    application_deadline = db.Column(db.Date)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="PENDING"  # PENDING | APPROVED | CLOSED
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("Application", backref="job_post", lazy=True)


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
        # APPLIED | SHORTLISTED | SELECTED | REJECTED
    )

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
