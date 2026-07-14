import os
from flask import Flask
from config import Config
from models import db, User, College, Admin, Company, Student, JobPost, Blog, Application, ExportJob
from tasks import generate_student_csv_export
from flask import request, render_template, redirect, url_for, flash, jsonify, send_file
from flask_login import login_user, login_required, current_user, logout_user, LoginManager
from flask_caching import Cache
from werkzeug.security import check_password_hash,generate_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import func, inspect, text



login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "info"
cache = Cache()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)

    def get_current_student():
        if current_user.is_authenticated and current_user.role == "STUDENT":
            return Student.query.filter_by(user_id=current_user.id).first()
        return None

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
        def ensure_eligibility_schema():
            db.create_all()

            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())

            if "students" in existing_tables:
                student_columns = {column["name"] for column in inspector.get_columns("students")}
                if "year_of_study" not in student_columns:
                    db.session.execute(text("ALTER TABLE students ADD COLUMN year_of_study INTEGER"))

            if "job_posts" in existing_tables:
                job_columns = {column["name"] for column in inspector.get_columns("job_posts")}
                if "min_cgpa" not in job_columns:
                    db.session.execute(text("ALTER TABLE job_posts ADD COLUMN min_cgpa FLOAT"))
                if "eligible_branches" not in job_columns:
                    db.session.execute(text("ALTER TABLE job_posts ADD COLUMN eligible_branches TEXT"))
                if "eligible_years" not in job_columns:
                    db.session.execute(text("ALTER TABLE job_posts ADD COLUMN eligible_years TEXT"))

            if "applications" in existing_tables:
                application_columns = {column["name"] for column in inspector.get_columns("applications")}
                if "interview_date" not in application_columns:
                    db.session.execute(text("ALTER TABLE applications ADD COLUMN interview_date DATETIME"))
                if "interview_mode" not in application_columns:
                    db.session.execute(text("ALTER TABLE applications ADD COLUMN interview_mode VARCHAR(50)"))
                if "interview_notes" not in application_columns:
                    db.session.execute(text("ALTER TABLE applications ADD COLUMN interview_notes TEXT"))

            db.session.commit()

        ensure_eligibility_schema()

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

            admin = Admin(user_id=admin_user.id, college_id=1, notification_email=admin_user.email)
            db.session.add(admin)
            db.session.commit()

    @app.route("/")
    def index():
        return render_template("index.html")
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

            user = User.query.filter_by(email=email).first()

            if not user:
                message = "Invalid credentials"
                if is_ajax:
                    return jsonify({"success": False, "message": message}), 401
                flash(message)
                return redirect(url_for("login"))

            if not user.is_active:
                message = "Account deactivated"
                if is_ajax:
                    return jsonify({"success": False, "message": message}), 403
                flash(message)
                return redirect(url_for("login"))

            if not check_password_hash(user.password_hash, password):
                message = "Invalid credentials"
                if is_ajax:
                    return jsonify({"success": False, "message": message}), 401
                flash(message)
                return redirect(url_for("login"))

            if user.role == "COMPANY":
                company = user.company
                if company is None:
                    message = "Company account is not available"
                    if is_ajax:
                        return jsonify({"success": False, "message": message}), 403
                    flash(message)
                    return redirect(url_for("login"))
                if company.is_blacklisted:
                    message = "Company account is blacklisted"
                    if is_ajax:
                        return jsonify({"success": False, "message": message}), 403
                    flash(message)
                    return redirect(url_for("login"))
                if company.approval_status != "APPROVED":
                    message = "Company account is not approved yet"
                    if is_ajax:
                        return jsonify({"success": False, "message": message}), 403
                    flash(message)
                    return redirect(url_for("login"))
            elif user.role == "STUDENT":
                student = user.student
                if student is not None and getattr(student, "is_blacklisted", False):
                    message = "Student account is blacklisted"
                    if is_ajax:
                        return jsonify({"success": False, "message": message}), 403
                    flash(message)
                    return redirect(url_for("login"))

            login_user(user)

            if user.role == "ADMIN":
                redirect_url = url_for("admin_dashboard")
            elif user.role == "COMPANY":
                redirect_url = url_for("company_dashboard")
            else:
                redirect_url = url_for("student_dashboard")

            if is_ajax:
                return jsonify({"success": True, "redirect": redirect_url})
            return redirect(redirect_url)

        return render_template("login.html")
        
    @app.route("/admin/profile", methods=["GET", "POST"])
    @login_required
    def admin_profile():
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        admin = current_user.admin
        if not admin:
            return "Admin profile missing", 404

        if request.method == "POST":
            try:
                notification_email = request.form.get("notification_email", "").strip()
                receive_notifications = request.form.get("receive_notifications") == "on"
                new_password = request.form.get("password", "").strip()

                admin.notification_email = notification_email
                admin.receive_notifications = receive_notifications
                if new_password:
                    current_user.password_hash = generate_password_hash(new_password)

                db.session.commit()
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": True, "message": "Profile updated successfully", "redirect": url_for("admin_dashboard")})
                return redirect(url_for("admin_dashboard"))
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": str(e)}), 400
                flash("Error updating profile", "error")

        return render_template("admin_profile.html", admin=admin)

    @app.route("/admin/dashboard")
    @login_required
    @cache.cached(timeout=120, key_prefix=lambda: f"admin_dashboard_{current_user.id}")
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
            branch = request.form.get("branch", "")
            cgpa = request.form.get("cgpa") or None
            year_of_study = request.form.get("year_of_study") or None

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
                cgpa=float(cgpa) if cgpa else None,
                year_of_study=int(year_of_study) if year_of_study else None
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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Company approved"})
        return redirect(url_for("admin_company_approval"))

    @app.route("/admin/company/reject/<int:company_id>")
    @login_required
    def reject_company(company_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        company = Company.query.get_or_404(company_id)
        company.approval_status = "REJECTED"
        db.session.commit()
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Company rejected"})
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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Student deactivated", "active": False})
        return redirect(url_for("admin_manage_students"))
    
    @app.route("/admin/student/activate/<int:student_id>")
    @login_required
    def activate_student(student_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        student = Student.query.get_or_404(student_id)
        student.user.is_active = True
        db.session.commit()
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Student activated", "active": True})
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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Company deactivated", "active": False})
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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Company activated", "active": True})
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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Job approved successfully"})
        return redirect(url_for("admin_job_approvals"))
    

    @app.route("/admin/job/reject/<int:job_id>")
    @login_required
    def reject_job(job_id):
        if current_user.role != "ADMIN":
            return "Unauthorized", 403

        job = JobPost.query.get_or_404(job_id)
        job.status = "REJECTED"
        db.session.commit()
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Job rejected successfully"})
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
    @cache.cached(timeout=120, key_prefix=lambda: f"company_dashboard_{current_user.id}")
    def company_dashboard():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        company = current_user.company

        jobs = JobPost.query.filter_by(company_id=company.id).all()
        
        print(f"[DEBUG] Company Dashboard - Company ID: {company.id}, Total Jobs: {len(jobs)}")
        if len(jobs) == 0:
            print(f"[DEBUG] No jobs found. All jobs in DB: {JobPost.query.count()}")
            for job in JobPost.query.all():
                print(f"[DEBUG] Job ID: {job.id}, Company ID: {job.company_id}, Title: {job.title}")

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

        interview_scheduled = Application.query.join(JobPost).filter(
            JobPost.company_id == company.id,
            Application.status == "INTERVIEW_SCHEDULED"
        ).count()

        return render_template(
            "company_dashboard.html",
            company=company,
            total_jobs=total_jobs,
            total_applications=total_applications,
            shortlisted=shortlisted,
            selected=selected,
            rejected=rejected,
            interview_scheduled=interview_scheduled
        )


    @app.route("/company/job/create", methods=["GET", "POST"])
    @login_required
    def create_job():
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        if request.method == "POST":
            try:
                # Verify company exists
                if not current_user.company:
                    raise ValueError("Company not found for this user")
                
                if not current_user.company.id:
                    raise ValueError("Company ID is not set")
                
                cgpa_value = request.form.get("min_cgpa") or None
                job = JobPost(
                    company_id=current_user.company.id,
                    college_id=current_user.company.college_id,
                    title=request.form["title"],
                    description=request.form["description"],
                    eligibility=request.form.get("eligibility", ""),
                    min_cgpa=float(cgpa_value) if cgpa_value else None,
                    eligible_branches=request.form.get("eligible_branches", ""),
                    eligible_years=request.form.get("eligible_years", ""),
                    application_deadline = datetime.strptime(request.form["deadline"], "%Y-%m-%d").date(),
                    status="PENDING"
                )
                db.session.add(job)
                db.session.commit()
                cache.clear()
                
                print(f"[DEBUG] Job created successfully: ID={job.id}, Company={current_user.company.id}")

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": True, "message": "Job posted successfully", "redirect": url_for("company_dashboard")})
                return redirect(url_for("company_dashboard"))
            except Exception as e:
                print(f"[ERROR] Job creation failed: {str(e)}")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": f"Error: {str(e)}"}), 400
                flash(f"Error creating job post: {str(e)}", "error")

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

        if application.job_post.status == "CLOSED":
            message = "Drive is closed and cannot be updated."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": message}), 400
            flash(message, "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        if application.student.is_placed and status in ["SHORTLISTED", "INTERVIEW_SCHEDULED", "SELECTED"]:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": "Student is already placed and cannot be shortlisted or interviewed."}), 400
            flash("Student is already placed and cannot be shortlisted or interviewed.", "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        if status in ["SHORTLISTED", "REJECTED", "SELECTED", "INTERVIEW_SCHEDULED"]:
            application.status = status
            job = application.job_post

            # 🔑 PLACEMENT LOGIC
            if status == "SELECTED":
                application.student.is_placed = True
                job.status = "CLOSED"
                Application.query.filter(
                    Application.job_post_id == application.job_post_id,
                    Application.id != application.id
                ).update({Application.status: "REJECTED"})
                Application.query.filter(
                    Application.job_post_id == application.job_post_id
                ).update({
                    Application.interview_date: None,
                    Application.interview_mode: None,
                    Application.interview_notes: None
                })

            db.session.commit()
            cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": True,
                "message": f"Application {status.lower()} successfully",
                "status": status,
                "job_closed": status == "SELECTED"
            })

        return redirect(
            url_for("view_applicants", job_id=application.job_post_id)
        )

    @app.route("/company/application/<int:app_id>/schedule-interview", methods=["POST"])
    @login_required
    def schedule_interview(app_id):
        if current_user.role != "COMPANY":
            return "Unauthorized", 403

        application = Application.query.get_or_404(app_id)

        if application.job_post.company_id != current_user.company.id:
            return "Unauthorized", 403

        if application.job_post.status == "CLOSED":
            message = "Drive is closed and cannot be scheduled for interview."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": message}), 400
            flash(message, "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        if application.student.is_placed:
            message = "Student is already placed and cannot be scheduled for interview."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": message}), 400
            flash(message, "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        interview_date = request.form.get("interview_date", "").strip()
        interview_mode = request.form.get("interview_mode", "").strip()
        interview_notes = request.form.get("interview_notes", "").strip()

        if not interview_date:
            message = "Interview date is required."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": message}), 400
            flash(message, "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        try:
            application.interview_date = datetime.strptime(interview_date, "%Y-%m-%dT%H:%M")
        except ValueError:
            message = "Interview date format is invalid."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": message}), 400
            flash(message, "error")
            return redirect(url_for("view_applicants", job_id=application.job_post_id))

        application.interview_mode = interview_mode or None
        application.interview_notes = interview_notes or None
        application.status = "INTERVIEW_SCHEDULED"
        db.session.commit()
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": True,
                "message": "Interview scheduled successfully",
                "status": "INTERVIEW_SCHEDULED"
            })

        return redirect(url_for("view_applicants", job_id=application.job_post_id))

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
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Application rejected", "status": "REJECTED"})

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
            try:
                # Only update fields that changed
                website = request.form.get("website", "").strip()
                hr_email = request.form.get("hr_email", "").strip()
                new_password = request.form.get("password", "").strip()
                
                if website and website != company.website:
                    company.website = website
                if hr_email and hr_email != company.hr_email:
                    company.hr_email = hr_email
                if new_password:
                    current_user.password_hash = generate_password_hash(new_password)

                file = request.files.get("logo")
                if file and allowed_file(file.filename):
                    filename = str(company.name) + "_" + secure_filename(file.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                    company.logo = filename

                db.session.commit()
                cache.clear()
                
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": True, "message": "Profile updated successfully", "redirect": url_for("company_dashboard")})
                return redirect(url_for("company_dashboard"))
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": str(e)}), 400
                flash("Error updating profile", "error")

        return render_template("company_profile.html", company=company)



    @app.route("/student/dashboard")
    @login_required
    @cache.cached(timeout=120, key_prefix=lambda: f"student_dashboard_{current_user.id}")
    def student_dashboard():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        student = get_current_student()
        if not student:
            return "Student profile not found", 404

        jobs = JobPost.query.filter_by(
            status="APPROVED",
            college_id=student.college_id
        ).all()

        applied_job_ids = [
            application.job_post_id
            for application in Application.query.filter_by(student_id=student.id).all()
        ]

        eligibility_map = {}
        for job in jobs:
            eligibility_map[job.id] = {
                "eligible": job.is_eligible_for(student),
                "reasons": job.get_eligibility_reasons(student),
            }

        return render_template(
            "student_dashboard.html",
            jobs=jobs,
            applied_job_ids=applied_job_ids,
            eligibility_map=eligibility_map
        )

    @app.route("/student/profile", methods=["GET", "POST"])
    @login_required
    def student_profile():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        student = get_current_student()
        if not student:
            return "Student profile not found", 404

        if request.method == "POST":
            try:
                student.branch = request.form.get("branch", "")
                student.cgpa = float(request.form.get("cgpa")) if request.form.get("cgpa") else None
                student.year_of_study = int(request.form.get("year_of_study")) if request.form.get("year_of_study") else None
                student.notification_email = request.form.get("notification_email", "")
                student.receive_notifications = request.form.get("receive_notifications") == "on"

                new_password = request.form.get("password", "")
                if new_password:
                    current_user.password_hash = generate_password_hash(new_password)

                file = request.files.get("photo")
                if file and file.filename and allowed_file(file.filename):
                    filename = student.name + student.roll_no + secure_filename(file.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                    student.profile_photo = filename

                file2 = request.files.get("resume")
                if file2 and file2.filename:
                    filename = student.name + student.roll_no + secure_filename(file2.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file2.save(file_path)
                    student.resume_path = filename

                db.session.commit()
                cache.clear()

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": True, "message": "Profile updated successfully", "redirect": url_for("student_dashboard")})
                return redirect(url_for("student_dashboard"))
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": str(e)}), 400
                flash("Error updating profile", "error")

        return render_template("student_profile.html", student=student)

    @app.route("/student/export-applications", methods=["POST"])
    @login_required
    def student_export_applications():
        if current_user.role != "STUDENT":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        student = get_current_student()
        if not student:
            return jsonify({"success": False, "message": "Student profile not found"}), 404

        export_job = ExportJob(
            student_id=student.id,
            task_id="",
            job_type="APPLICATION_CSV",
            status="PENDING"
        )
        db.session.add(export_job)
        db.session.commit()

        celery_task = generate_student_csv_export.delay(student.id, export_job.id)
        export_job.task_id = celery_task.id
        db.session.commit()

        return jsonify({"success": True, "job_id": export_job.id, "task_id": celery_task.id})

    @app.route("/student/export-applications/status/<int:job_id>")
    @login_required
    def student_export_status(job_id):
        if current_user.role != "STUDENT":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        export_job = ExportJob.query.get_or_404(job_id)
        if export_job.student_id != get_current_student().id:
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        return jsonify({
            "success": True,
            "status": export_job.status,
            "file_path": export_job.file_path,
            "error": export_job.error_message
        })

    @app.route("/student/export-applications/download/<int:job_id>")
    @login_required
    def student_export_download(job_id):
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        export_job = ExportJob.query.get_or_404(job_id)
        if export_job.student_id != get_current_student().id:
            return "Unauthorized", 403

        if export_job.status != "COMPLETED" or not export_job.file_path:
            return "File not available yet", 404

        return send_file(export_job.file_path, as_attachment=True)

    @app.route("/student/job/apply/<int:job_id>", methods=["POST"])
    @login_required
    def apply_job(job_id):
        if current_user.role != "STUDENT":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        student = get_current_student()
        if not student:
            return jsonify({"success": False, "message": "Student profile not found"}), 404

        job = JobPost.query.get_or_404(job_id)

        if job.status != "APPROVED":
            return jsonify({"success": False, "message": "This drive is no longer open."}), 400

        if student.is_placed:
            return jsonify({"success": False, "message": "You are already placed."}), 400

        if not job.is_eligible_for(student):
            reasons = " ".join(job.get_eligibility_reasons(student))
            message = "You do not meet the eligibility criteria for this drive." + (f" {reasons}" if reasons else "")
            return jsonify({"success": False, "message": message}), 400

        existing = Application.query.filter_by(
            student_id=student.id,
            job_post_id=job_id
        ).first()

        if existing:
            return jsonify({"success": True, "message": "You already applied for this job.", "applied": True})

        application = Application(
            student_id=student.id,
            job_post_id=job_id,
            status="APPLIED"
        )

        db.session.add(application)
        db.session.commit()
        cache.clear()

        return jsonify({"success": True, "message": "You have applied successfully for this job.", "applied": True})
    
    @app.route("/student/job/<int:job_id>")
    @login_required
    def student_view_job(job_id):
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        student = get_current_student()
        if not student:
            return "Student profile not found", 404

        job = JobPost.query.filter_by(
            id=job_id,
            status="APPROVED",
            college_id=student.college_id
        ).first_or_404()

        has_applied = Application.query.filter_by(
            student_id=student.id,
            job_post_id=job_id
        ).first() is not None

        eligibility_info = {
            "eligible": job.is_eligible_for(student),
            "reasons": job.get_eligibility_reasons(student),
        }

        return render_template(
            "student_job_details.html",
            job=job,
            back_url=url_for("student_dashboard"),
            has_applied=has_applied,
            eligibility_info=eligibility_info
        )

    @app.route("/student/applications")
    @login_required
    def student_applications():
        if current_user.role != "STUDENT":
            return "Unauthorized", 403

        student = get_current_student()
        if not student:
            return "Student profile not found", 404

        applications = Application.query.filter_by(
            student_id=student.id
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
        Application.query.filter(
            Application.job_post_id == job.id
        ).update({
            Application.interview_date: None,
            Application.interview_mode: None,
            Application.interview_notes: None
        })

        # Close the job posting
        job.status = "CLOSED"

        db.session.commit()
        cache.clear()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Student selected and drive closed", "status": "SELECTED", "job_closed": True})

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
        Application.query.filter(
            Application.job_post_id == job_id
        ).update({
            Application.interview_date: None,
            Application.interview_mode: None,
            Application.interview_notes: None
        })
        db.session.commit()
        cache.clear()

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
