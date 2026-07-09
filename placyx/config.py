import os

BASE_DIR = os.path.abspath(os.path.dirname("./instance"))

class Config:
    SECRET_KEY = "placyx-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "placyx.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True

    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    # Allow overriding timezone via env var. Default remains UTC.
    CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")
    CELERY_ENABLE_UTC = True

    CACHE_TYPE = os.environ.get("CACHE_TYPE", "RedisCache")
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/2")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 120))

    # Ensure schedule values are integers (can be overridden with env vars)
    DAILY_REMINDER_HOUR = int(os.environ.get("DAILY_REMINDER_HOUR", 23))
    DAILY_REMINDER_MINUTE = int(os.environ.get("DAILY_REMINDER_MINUTE", 45))
    MONTHLY_REPORT_DAY = int(os.environ.get("MONTHLY_REPORT_DAY", 7))
    MONTHLY_REPORT_HOUR = int(os.environ.get("MONTHLY_REPORT_HOUR", 23))
    MONTHLY_REPORT_MINUTE = int(os.environ.get("MONTHLY_REPORT_MINUTE", 45))
    EXPORT_FOLDER = os.environ.get("EXPORT_FOLDER", os.path.join(BASE_DIR, "exports"))
    # SMTP settings (defaults target SMTP2GO Europe)
    SMTP_HOST = os.environ.get("SMTP_HOST", "mail-eu.smtp2go.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 2525))
    SMTP_USER = os.environ.get("SMTP_USER", "ds.study.iitm.ac.in")
    SMTP_PASS = os.environ.get("SMTP_PASS", "Mgvanshika1909@")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@placyx.com")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
    GCHAT_WEBHOOK_URL = os.environ.get("GCHAT_WEBHOOK_URL", "")