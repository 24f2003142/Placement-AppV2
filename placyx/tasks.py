import os
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from celery_app import celery
from config import Config
from models import db, User, Admin, Student, JobPost, Application, ExportJob


def send_email(to_email: str, subject: str, body: str, html: str = None):
    """Send an email via SMTP using settings from `Config`.

    Returns True if send appears successful, False otherwise.
    """
    host = Config.SMTP_HOST
    port = Config.SMTP_PORT
    user = Config.SMTP_USER
    pwd = Config.SMTP_PASS
    from_addr = Config.SMTP_FROM
    use_tls = Config.SMTP_USE_TLS
    use_ssl = Config.SMTP_USE_SSL

    print(f"[EMAIL] ATTEMPT to={to_email}, subject={subject}, html={'yes' if html else 'no'}")

    if not user or not pwd:
        print("[EMAIL] WARNING: SMTP credentials (SMTP_USER/SMTP_PASS) are not set. Skipping real send.")
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_email
    if html:
        msg.set_content(body)
        msg.add_alternative(html, subtype='html')
    else:
        msg.set_content(body)

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        server.login(user, pwd)
        server.send_message(msg)
        server.quit()
        print(f"[EMAIL] SENT to={to_email}")
        return True
    except Exception as exc:
        print(f"[EMAIL] FAILED to send to={to_email}: {exc}")
        return False


def send_chat_notification(webhook_url: str, text: str):
    try:
        response = requests.post(webhook_url, json={"text": text}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"Failed to send chat notification: {exc}")
        return False


@celery.task(name="tasks.remind_students_for_closing_drives")
def remind_students_for_closing_drives():
    tomorrow = datetime.utcnow().date() + timedelta(days=1)

    closing_drives = JobPost.query.filter(
        JobPost.application_deadline == tomorrow,
        JobPost.status == "APPROVED"
    ).all()

    if not closing_drives:
        return "No closing drives tomorrow"

    results = []

    for drive in closing_drives:
        applied_student_ids = {app.student_id for app in Application.query.filter_by(job_post_id=drive.id).all()}
        students = Student.query.filter(
            Student.is_placed == False,
            ~Student.id.in_(applied_student_ids)
        ).all()

        for student in students:
            subject = f"Reminder: {drive.title} closes tomorrow"
            body = (
                f"Hi {student.name},\n\n"
                f"The placement drive '{drive.title}' from {drive.company.name} closes tomorrow ({drive.application_deadline}).\n"
                "If you haven't already applied, please visit the portal and submit your application today.\n\n"
                "Best regards,\nPlacyx Placement Team"
            )
            # Prefer per-student `notification_email` if set, else use registered user email
            recipient = None
            if getattr(student, 'notification_email', None):
                recipient = student.notification_email
            elif getattr(student, 'user', None) and getattr(student.user, 'email', None):
                recipient = student.user.email

            if recipient:
                email_sent = send_email(recipient, subject, body)
                print(f"[EMAIL] reminder to {recipient} - status: {'sent' if email_sent else 'NOT SENT'}")
            else:
                print(f"[EMAIL] reminder skipped because no email exists for student_id={student.id}")

            if Config.GCHAT_WEBHOOK_URL:
                notification_text = (
                    f"Reminder: {drive.title} closes tomorrow. "
                    f"Student: {student.name}, email: {student.user.email}"
                )
                send_chat_notification(Config.GCHAT_WEBHOOK_URL, notification_text)

            results.append({
                "student_id": student.id,
                "email": student.user.email,
                "job_post_id": drive.id,
                "job_title": drive.title,
            })

    return {"notified": len(results), "details": results}


@celery.task(name="tasks.send_admin_monthly_report")
def send_admin_monthly_report():
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_month - timedelta(seconds=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    drives = JobPost.query.filter(
        JobPost.created_at >= last_month_start,
        JobPost.created_at <= last_month_end
    ).all()
    total_drives = len(drives)
    applications = Application.query.join(JobPost).filter(
        Application.applied_on >= last_month_start,
        Application.applied_on <= last_month_end
    ).all()
    total_applications = len(applications)
    selected_count = sum(1 for app in applications if app.status == "SELECTED")
    interview_scheduled_count = sum(1 for app in applications if app.status == "INTERVIEW_SCHEDULED")

    # Prefer Admin.notification_email if configured; fall back to the admin user's registered email
    admin_user = User.query.filter_by(role="ADMIN").first()
    admin = Admin.query.first()
    if not admin_user:
        return {"error": "No admin user found"}

    admin_email = None
    if admin and getattr(admin, 'notification_email', None):
        admin_email = admin.notification_email
    elif getattr(admin_user, 'email', None):
        admin_email = admin_user.email

    if not admin_email:
        return {"error": "Admin has no email configured"}

    html_summary = f"""
        <h2>Monthly Placement Report</h2>
        <p><strong>Reporting period:</strong> {last_month_start.date()} to {last_month_end.date()}</p>
        <ul>
          <li><strong>Drives created:</strong> {total_drives}</li>
          <li><strong>Applications submitted:</strong> {total_applications}</li>
          <li><strong>Interviews scheduled:</strong> {interview_scheduled_count}</li>
          <li><strong>Students selected:</strong> {selected_count}</li>
        </ul>
        <table border='1' cellpadding='6' cellspacing='0'>
          <thead>
            <tr>
              <th>Drive</th>
              <th>Company</th>
              <th>Deadline</th>
              <th>Applications</th>
              <th>Selected</th>
            </tr>
          </thead>
          <tbody>
    """

    for drive in drives:
        drive_apps = [app for app in applications if app.job_post_id == drive.id]
        selected_for_drive = sum(1 for app in drive_apps if app.status == "SELECTED")
        html_summary += f"""
            <tr>
              <td>{drive.title}</td>
              <td>{drive.company.name}</td>
              <td>{drive.application_deadline}</td>
              <td>{len(drive_apps)}</td>
              <td>{selected_for_drive}</td>
            </tr>
        """

    html_summary += """
          </tbody>
        </table>
    """

    subject = f"Monthly Placement Report for {last_month_start.strftime('%B %Y')}"
    email_sent = send_email(admin_email, subject, html_summary, html=html_summary)
    print(f"[EMAIL] monthly report to {admin_email} - status: {'sent' if email_sent else 'NOT SENT'}")

    return {
        "report_sent": True,
        "admin_email": admin_email,
        "drives": total_drives,
        "applications": total_applications,
        "interview_scheduled": interview_scheduled_count,
        "selected": selected_count
    }


@celery.task(name="tasks.generate_student_csv_export")
def generate_student_csv_export(student_id: int, export_job_id: int):
    from csv import writer
    os.makedirs(Config.EXPORT_FOLDER, exist_ok=True)
    job = ExportJob.query.get(export_job_id)
    student = Student.query.get(student_id)
    if not job or not student:
        return {"error": "Missing export job or student."}

    job.status = "IN_PROGRESS"
    db.session.commit()

    try:
        filename = f"student_export_{student.id}_{int(datetime.utcnow().timestamp())}.csv"
        filepath = os.path.join(Config.EXPORT_FOLDER, filename)

        applications = Application.query.filter_by(student_id=student.id).all()
        with open(filepath, "w", newline='', encoding='utf-8') as csvfile:
            csv_writer = writer(csvfile)
            csv_writer.writerow([
                "Application ID",
                "Job Title",
                "Company",
                "Status",
                "Applied On",
                "Interview Date",
                "Interview Mode",
                "Interview Notes"
            ])
            for app in applications:
                csv_writer.writerow([
                    app.id,
                    app.job_post.title,
                    app.job_post.company.name,
                    app.status,
                    app.applied_on.strftime('%Y-%m-%d %H:%M:%S'),
                    app.interview_date.strftime('%Y-%m-%d %H:%M:%S') if app.interview_date else "",
                    app.interview_mode or "",
                    app.interview_notes or ""
                ])

        job.status = "COMPLETED"
        job.file_path = filepath
        job.completed_at = datetime.utcnow()
        db.session.commit()

        if student.user.email and student.receive_notifications:
            email_sent = send_email(
                student.user.email,
                "Your CSV export is ready",
                f"Your export is ready. Download it from: {filepath}",
            )
            print(f"[EMAIL] CSV export notification to {student.user.email} - status: {'sent' if email_sent else 'NOT SENT'}")

        return {"status": "completed", "file_path": filepath}
    except Exception as exc:
        job.status = "FAILED"
        job.error_message = str(exc)
        db.session.commit()
        return {"status": "failed", "error": str(exc)}
