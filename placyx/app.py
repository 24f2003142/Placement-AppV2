import os
from flask import Flask
from config import Config
from models import db, User, College, Admin, Company, Student, JobPost, Blog, Application
from flask import request, render_template, redirect, url_for, flash
from flask_login import login_user, login_required, current_user, logout_user, LoginManager
from werkzeug.security import check_password_hash,generate_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import func



login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "info"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    

    with app.app_context():
        # Create instance folder if missing
        os.makedirs("instance", exist_ok=True)
        UPLOAD_FOLDER = "static/uploads"
        ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

        app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        def allowed_file(filename):
            return "." in filename and \
                filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        # CREATE DATABASE & TABLES PROGRAMMATICALLY
        db.create_all()

        # Create default college + admin ONLY if not exists
        if not College.query.first():
            college = College(name="Default College", email="placement@college.edu")
            db.session.add(college)
            db.session.commit()

        if not User.query.filter_by(role="ADMIN").first():
            admin_user = User(
                email="admin@placyx.com",
                password_hash=generate_password_hash("admin123"),
                role="ADMIN"
            )
            db.session.add(admin_user)
            db.session.commit()

            admin = Admin(user_id=admin_user.id, college_id=1)
            db.session.add(admin)
            db.session.commit()

    @app.route("/")
    def index():
        return render_template("index.html")
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.route("/login", methods=["GET", "POST"])
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            user = User.query.filter_by(email=email).first()

            if not user:
                flash("Invalid credentials")
                return redirect(url_for("login"))

            if not user.is_active:
                flash("Account deactivated")
                return redirect(url_for("login"))

            if not check_password_hash(user.password_hash, password):
                flash("Invalid credentials")
                return redirect(url_for("login"))

            # Company approval gate
            if user.role == "COMPANY":
                if user.company.approval_status != "APPROVED":
                    flash("Company not approved yet")
                    return redirect(url_for("login"))

            login_user(user)

            # Role-based redirect
            if user.role == "ADMIN":
                return redirect(url_for("admin_dashboard"))
            elif user.role == "COMPANY":
                return redirect(url_for("company_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))

        return render_template("login.html")
        
    @app.route("/admin/dashboard")
    @login_required
    def admin_dashboard():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        total_students = Student.query.count()
        total_companies = Company.query.count()
        total_jobs = JobPost.query.count()

        placed_students = Student.query.filter_by(is_placed=True).count()

        pending_jobs = JobPost.query.filter_by(status="PENDING").count()
        approved_jobs = JobPost.query.filter_by(status="APPROVED").count()
        closed_jobs = JobPost.query.filter_by(status="CLOSED").count()

        return render_template(
            "admin_dashboard.html",
            total_students=total_students,
            total_companies=total_companies,
            total_jobs=total_jobs,
            placed_students=placed_students,
            pending_jobs=pending_jobs,
            approved_jobs=approved_jobs,
            closed_jobs=closed_jobs
        )
    
    @app.route("/admin/placements")
    @login_required
    def admin_placements():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        placed_students = Student.query.filter_by(is_placed=True).all()
        return render_template(
            "admin_placements.html",
            students=placed_students
        )
    

    
    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))
    
    @app.route("/register/student", methods=["GET", "POST"])
    def register_student():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            name = request.form["name"]
            roll_no = request.form["roll_no"]
            branch = request.form["branch"]
            cgpa = request.form["cgpa"]

            if User.query.filter_by(email=email).first():
                flash("Email already registered")
                return redirect(url_for("register_student"))

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="STUDENT"
            )
            db.session.add(user)
            db.session.commit()

            # Assuming single college (default college id = 1)
            student = Student(
                user_id=user.id,
                college_id=1,
                name=name,
                roll_no=roll_no,
                branch=branch,
                cgpa=cgpa
            )
            db.session.add(student)
            db.session.commit()

            flash("Student registered successfully. Please login.")
            return redirect(url_for("login"))

        return render_template("register_student.html")

    @app.route("/register/company", methods=["GET", "POST"])
    def register_company():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            company_name = request.form["company_name"]
            hr_email = request.form["hr_email"]
            website = request.form["website"]

            if User.query.filter_by(email=email).first():
                flash("Email already registered")
                return redirect(url_for("register_company"))

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="COMPANY"
            )
            db.session.add(user)
            db.session.commit()

            company = Company(
                user_id=user.id,
                college_id=1,
                name=company_name,
                hr_email=hr_email,
                website=website,
                approval_status="PENDING"
            )
            db.session.add(company)
            db.session.commit()

            flash("Company registered. Await admin approval.")
            return redirect(url_for("login"))

        return render_template("register_company.html")
    
    @app.route("/admin/companies")
    @login_required
    def admin_company_approval():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        pending_companies = Company.query.filter_by(approval_status="PENDING").all()
        return render_template(
            "admin_company_approval.html",
            companies=pending_companies
        )
    
    @app.route("/admin/company/approve/<int:company_id>")
    @login_required
    def approve_company(company_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(company_id)
        company.approval_status = "APPROVED"
        db.session.commit()

        return redirect(url_for("admin_company_approval"))

    @app.route("/admin/company/reject/<int:company_id>")
    @login_required
    def reject_company(company_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(company_id)
        company.approval_status = "REJECTED"
        db.session.commit()

        return redirect(url_for("admin_company_approval"))
    
    @app.route("/admin/students")
    @login_required
    def admin_manage_students():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        query = request.args.get("q", "").strip()

        students_query = Student.query
        if query:
            students_query = students_query.filter(
                (Student.name.ilike(f"%{query}%")) |
                (Student.roll_no.ilike(f"%{query}%"))
            )

        students = students_query.all()
        return render_template("admin_manage_students.html", students=students, q=query)
    
    @app.route("/admin/student/deactivate/<int:student_id>")
    @login_required
    def deactivate_student(student_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        student = Student.query.get_or_404(student_id)
        student.user.is_active = False
        db.session.commit()

        return redirect(url_for("admin_manage_students"))
    
    @app.route("/admin/student/activate/<int:student_id>")
    @login_required
    def activate_student(student_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        student = Student.query.get_or_404(student_id)
        student.user.is_active = True
        db.session.commit()

        return redirect(url_for("admin_manage_students"))

    @app.route("/admin/manage-companies")
    @login_required
    def admin_manage_companies():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        query = request.args.get("q", "").strip()

        companies_query = Company.query
        if query:
            companies_query = companies_query.filter(
                (Company.name.ilike(f"%{query}%")) |
                (Company.hr_email.ilike(f"%{query}%")) |
                (Company.website.ilike(f"%{query}%"))
            )

        companies = companies_query.all()
        return render_template("admin_manage_companies.html", companies=companies, q=query)

    @app.route("/admin/company/deactivate/<int:company_id>")
    @login_required
    def deactivate_company(company_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(company_id)
        company.user.is_active = False
        db.session.commit()

        return redirect(url_for("admin_manage_companies"))

    @app.route("/admin/company/activate/<int:company_id>")
    @login_required
    def activate_company(company_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(company_id)
        company.user.is_active = True
        company.approval_status = "APPROVED"
        db.session.commit()

        return redirect(url_for("admin_manage_companies"))

    @app.route("/admin/job-posts")
    @login_required
    def admin_job_approvals():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        pending_jobs = JobPost.query.filter_by(status="PENDING").all()
        return render_template(
            "admin_job_approval.html",
            job_posts=pending_jobs
        )

    @app.route("/admin/job/approve/<int:job_id>")
    @login_required
    def approve_job(job_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)
        job.status = "APPROVED"
        db.session.commit()

        return redirect(url_for("admin_job_approvals"))
    

    @app.route("/admin/job/reject/<int:job_id>")
    @login_required
    def reject_job(job_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)
        job.status = "REJECTED"
        db.session.commit()

        return redirect(url_for("admin_job_approvals"))
    
    @app.route("/admin/jobs")
    @login_required
    def admin_all_jobs():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        jobs = JobPost.query.order_by(JobPost.created_at.desc()).all()

        return render_template(
            "admin_all_jobs.html",
            jobs=jobs,
            back_url=url_for("admin_dashboard")
        )
    @app.route("/admin/applications")
    @login_required
    def admin_applications():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        applications = Application.query.all()

        return render_template(
            "admin_applications.html",
            applications=applications,
            back_url=url_for("admin_dashboard")
        )
    
    @app.route("/admin/students/search")
    @login_required
    def admin_search_students():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        query = request.args.get("q")

        students = []

        if query:
            students = Student.query.filter(
                (Student.name.ilike(f"%{query}%")) |
                (Student.roll_no.ilike(f"%{query}%")) |
                (Student.branch.ilike(f"%{query}%")) |
                (func.cast(Student.cgpa, db.String).ilike(f"%{query}%"))
            ).all()

        return render_template(
            "admin_search_students.html",
            students=students
        )

    @app.route("/company/dashboard")
    @login_required
    def company_dashboard():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        company = current_user.company

        jobs = JobPost.query.filter_by(company_id=company.id).all()

        total_jobs = len(jobs)
        total_applications = Application.query.join(JobPost).filter(
            JobPost.company_id == company.id
        ).count()

        shortlisted = Application.query.join(JobPost).filter(
            JobPost.company_id == company.id,
            Application.status == "SHORTLISTED"
        ).count()

        selected = Application.query.join(JobPost).filter(
            JobPost.company_id == company.id,
            Application.status == "SELECTED"
        ).count()

        rejected = Application.query.join(JobPost).filter(
            JobPost.company_id == company.id,
            Application.status == "REJECTED"
        ).count()

        return render_template(
            "company_dashboard.html",
            company=company,
            total_jobs=total_jobs,
            total_applications=total_applications,
            shortlisted=shortlisted,
            selected=selected,
            rejected=rejected
        )


    @app.route("/company/job/create", methods=["GET", "POST"])
    @login_required
    def create_job():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        if request.method == "POST":
            job = JobPost(
                company_id=current_user.company.id,
                college_id=current_user.company.college_id,
                title=request.form["title"],
                description=request.form["description"],
                eligibility=request.form["eligibility"],
                application_deadline = datetime.strptime(request.form["deadline"], "%Y-%m-%d").date(),
                status="PENDING"
            )
            db.session.add(job)
            db.session.commit()

            return redirect(url_for("company_dashboard"))

        return render_template("company_create_job.html")

    @app.route("/company/jobs")
    @login_required
    def company_jobs():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        jobs = JobPost.query.filter_by(company_id=current_user.company.id).all()
        return render_template("company_jobs.html", jobs=jobs)

    @app.route("/company/job/<int:job_id>/applications")
    @login_required
    def view_applicants(job_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)
        if job.company_id != current_user.company.id:
            return "Unauthorized", 403

        applications = Application.query.filter_by(job_post_id=job_id).all()
        return render_template(
            "company_view_applicants.html",
            job=job,
            applications=applications
        )
    
    @app.route("/company/application/<int:app_id>/<status>")
    @login_required
    def update_application_status(app_id, status):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)

        if application.job_post.company_id != current_user.company.id:
            return "Unauthorized", 403

        status = status.upper()

        if status in ["SHORTLISTED", "REJECTED", "SELECTED"]:
            application.status = status

            # 🔑 PLACEMENT LOGIC
            if status == "SELECTED":
                application.student.is_placed = True

            db.session.commit()

        return redirect(
            url_for("view_applicants", job_id=application.job_post_id)
        )

    @app.route("/company/application/<int:app_id>/shortlist")
    @login_required
    def shortlist_application(app_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)

        if application.job_post.company_id != current_user.company.id:
            return "Unauthorized", 403

        application.status = "SHORTLISTED"
        db.session.commit()

        return redirect(
            url_for("view_applicants", job_id=application.job_post_id)
        )

    @app.route("/company/application/<int:app_id>/reject")
    @login_required
    def reject_application(app_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)

        if application.job_post.company_id != current_user.company.id:
            return "Unauthorized", 403

        application.status = "REJECTED"
        db.session.commit()

        return redirect(
            url_for("view_applicants", job_id=application.job_post_id)
        )
    @app.route("/company/profile", methods=["GET", "POST"])
    @login_required
    def company_profile():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        company = current_user.company

        if request.method == "POST":

            company.website = request.form.get("website")
            company.hr_email = request.form.get("hr_email")

            new_password = request.form.get("password")
            if new_password:
                current_user.password_hash = generate_password_hash(new_password)

            file = request.files.get("logo")
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                company.logo = filename

            db.session.commit()
            return redirect(url_for("company_dashboard"))

        return render_template("company_profile.html", company=company)



    @app.route("/student/dashboard")
    @login_required
    def student_dashboard():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        jobs = JobPost.query.filter_by(
            status="APPROVED",
            college_id=current_user.student.college_id
        ).all()

        return render_template(
            "student_dashboard.html",
            jobs=jobs
        )
    @app.route("/student/profile", methods=["GET", "POST"])
    @login_required
    def student_profile():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        student = current_user.student

        if request.method == "POST":

            # Update branch and CGPA
            student.branch = request.form.get("branch")
            student.cgpa = request.form.get("cgpa")

            # Password change
            new_password = request.form.get("password")
            if new_password:
                current_user.password_hash = generate_password_hash(new_password)

            # Photo upload
            file = request.files.get("photo")
            if file and allowed_file(file.filename):
                filename = student.name+student.roll_no+secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                student.profile_photo = filename

            file2 = request.files.get("resume")
            if file2:
                filename = student.name+student.roll_no+secure_filename(file2.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file2.save(file_path)
                student.resume_path = filename

            db.session.commit()
            return redirect(url_for("student_dashboard"))

        return render_template("student_profile.html", student=student)

    @app.route("/student/job/apply/<int:job_id>")
    @login_required
    def apply_job(job_id):
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)

        # 🚫 Prevent applying to closed jobs
        if job.status != "APPROVED":
            return redirect(url_for("student_dashboard"))

        if current_user.student.is_placed:
            return redirect(url_for("student_dashboard"))

        existing = Application.query.filter_by(
            student_id=current_user.student.id,
            job_post_id=job_id
        ).first()

        if existing:
            return redirect(url_for("student_applications"))

        application = Application(
            student_id=current_user.student.id,
            job_post_id=job_id,
            status="APPLIED"
        )

        db.session.add(application)
        db.session.commit()

        return redirect(url_for("student_applications"))
    
    @app.route("/student/job/<int:job_id>")
    @login_required
    def student_view_job(job_id):
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        job = JobPost.query.filter_by(
            id=job_id,
            status="APPROVED",
            college_id=current_user.student.college_id
        ).first_or_404()

        return render_template(
            "student_job_details.html",
            job=job,
            back_url=url_for("student_dashboard")
        )

    @app.route("/student/applications")
    @login_required
    def student_applications():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        applications = Application.query.filter_by(
            student_id=current_user.student.id
        ).all()

        return render_template(
            "student_applications.html",
            applications=applications
        )
    @app.route("/company/application/<int:app_id>/select")
    @login_required
    def select_student(app_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)
        job = application.job_post

        # Ensure company owns the job
        if job.company_id != current_user.company.id:
            return "Unauthorized", 403

        student = application.student

        # Mark this student as selected
        application.status = "SELECTED"
        student.is_placed = True

        # Reject all OTHER applications for this SPECIFIC JOB (not all student jobs)
        Application.query.filter(
            Application.job_post_id == job.id,
            Application.id != application.id
        ).update({Application.status: "REJECTED"})

        # Close the job posting
        job.status = "CLOSED"

        db.session.commit()

        return redirect(url_for("view_applicants", job_id=job.id))
    
    @app.route("/company/application/<int:app_id>")
    @login_required
    def company_view_candidate(app_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)

        if application.job_post.company_id != current_user.company.id:
            return "Unauthorized", 403

        return render_template(
            "company_candidate_details.html",
            application=application,
            back_url=url_for("view_applicants", job_id=application.job_post_id)
        )

    @app.route("/company/job/<int:job_id>/close")
    @login_required
    def close_job(job_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)

        if job.company_id != current_user.company.id:
            return "Unauthorized", 403

        job.status = "CLOSED"
        db.session.commit()

        return redirect(url_for("company_jobs"))
    
    @app.route("/admin/companies/search")
    @login_required
    def admin_search_companies():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        return redirect(url_for("admin_manage_companies", q=request.args.get("q", "")))
    
    @app.route("/admin/company/<int:id>/toggle")
    @login_required
    def toggle_company(id):

        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(id)

        company.user.is_active = not company.user.is_active

        db.session.commit()

        return redirect(url_for("admin_manage_companies"))

    

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
