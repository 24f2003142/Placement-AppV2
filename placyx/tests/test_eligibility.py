import unittest
from flask import Flask
from models import db, College, Student, JobPost, Company, User


class EligibilityValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

            college = College(name="Test College")
            db.session.add(college)
            db.session.commit()

            user = User(email="student@example.com", password_hash="x", role="STUDENT")
            db.session.add(user)
            db.session.commit()

            student = Student(
                user_id=user.id,
                college_id=college.id,
                name="Test Student",
                roll_no="123",
                branch="CSE",
                cgpa=8.7,
                year_of_study=3,
            )
            db.session.add(student)
            db.session.commit()

            company_user = User(email="company@example.com", password_hash="x", role="COMPANY")
            db.session.add(company_user)
            db.session.commit()

            company = Company(
                user_id=company_user.id,
                college_id=college.id,
                name="Test Company",
                approval_status="APPROVED",
            )
            db.session.add(company)
            db.session.commit()

            self.student_id = student.id
            self.job = JobPost(
                company_id=company.id,
                college_id=college.id,
                title="Software Engineer",
                description="Example",
                min_cgpa=7.5,
                eligible_branches="CSE, ECE",
                eligible_years="2,3,4",
            )
            db.session.add(self.job)
            db.session.commit()
            self.job_id = self.job.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_job_requires_branch_cgpa_and_year(self):
        with self.app.app_context():
            job = JobPost.query.get(self.job_id)
            student = Student.query.get(self.student_id)

            self.assertTrue(job.is_eligible_for(student))

            student.branch = "MECH"
            self.assertFalse(job.is_eligible_for(student))

            student.branch = "CSE"
            student.cgpa = 6.5
            self.assertFalse(job.is_eligible_for(student))

            student.cgpa = 8.7
            student.year_of_study = 1
            self.assertFalse(job.is_eligible_for(student))


if __name__ == "__main__":
    unittest.main()
