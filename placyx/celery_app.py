import os
from celery import Celery
from celery.schedules import crontab, schedule
from config import Config


def make_celery():
    celery = Celery(
        __name__,
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
        include=["tasks"],
    )

    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone=Config.CELERY_TIMEZONE,
        enable_utc=Config.CELERY_ENABLE_UTC,
    )

    # Support a temporary demo schedule (every 5 minutes) when enabled via env var.
    demo_enabled = os.environ.get("DEMO_SCHEDULE_ENABLED", "true").lower() in ("1", "true", "yes")
    if demo_enabled:
        print("[DEMOSCHED] Demo schedule enabled: running reminder every 1 minutes")
        reminder_sched = schedule(60)  # every 60 seconds (1 minute)
    else:
        reminder_sched = crontab(hour=Config.DAILY_REMINDER_HOUR, minute=Config.DAILY_REMINDER_MINUTE)

    # monthly report stays on its cron schedule by default
    monthly_sched = crontab(
        day_of_month=Config.MONTHLY_REPORT_DAY,
        hour=Config.MONTHLY_REPORT_HOUR,
        minute=Config.MONTHLY_REPORT_MINUTE,
    )

    celery.conf.beat_schedule = {
        "daily-reminder-drive-notifications": {
            "task": "tasks.remind_students_for_closing_drives",
            "schedule": reminder_sched,
        },
        "monthly-admin-report": {
            "task": "tasks.send_admin_monthly_report",
            "schedule": monthly_sched,
        },
    }

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            from app import create_app

            app = create_app()
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery()
