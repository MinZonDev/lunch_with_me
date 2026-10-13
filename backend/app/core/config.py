import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production-very-secret-key")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

    # App
    app_name: str = "Lunch With Me"
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # SMTP (Gmail)
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")

    # Firebase Storage bucket for menu images, e.g. "my-project.appspot.com"
    storage_bucket: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # Microsoft Teams group notification
    teams_webhook_url: str = os.getenv("TEAMS_WEBHOOK_URL", "")

    # Bank transfer info
    bank_id: str = os.getenv("BANK_ID", "VIKKI")
    bank_account: str = os.getenv("BANK_ACCOUNT", "880011988")
    bank_account_name: str = os.getenv("BANK_ACCOUNT_NAME", "PHAM MINH TRONG")

    # Business rules
    low_balance_threshold: int = int(os.getenv("LOW_BALANCE_THRESHOLD", "50"))
    order_deadline_default: str = os.getenv("ORDER_DEADLINE_DEFAULT", "11:00")

    # Background jobs (reminders, auto-lock, pickup random). Turn off when a local
    # backend points at the production project so it doesn't email real users.
    enable_scheduler: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() not in ("0", "false", "no")
    # Shared secret for POST /api/internal/cron/tick (Cloud Scheduler). Empty = endpoint disabled.
    cron_secret: str = os.getenv("CRON_SECRET", "")


settings = Settings()
