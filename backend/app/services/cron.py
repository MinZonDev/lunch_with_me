"""Time-based jobs, driven by a once-a-minute tick.

On Cloud Run (scale to zero, CPU only during requests) an in-process scheduler
can't be trusted, so Cloud Scheduler calls POST /api/internal/cron/tick every
minute and the work happens inside that request. Locally/on a VPS, APScheduler
calls the same run_tick() every minute, so there is one source of truth for
when each job runs.

Every job except pickup runs at most once per period: the period is claimed
in a Firestore transaction (_cron/{job}) before running, so retries, late
ticks and several instances can't double-send emails. A tick that arrives
after the due time still runs the job (catch-up) as long as it's the same
period.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from firebase_admin import firestore as fb_firestore

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
logger = logging.getLogger("lwm.cron")

_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def claim(db, job: str, period: str) -> bool:
    """Atomically mark `job` as done for `period`. False if it already ran."""
    ref = db.collection("_cron").document(job)

    @fb_firestore.transactional
    def _claim(transaction, doc_ref):
        snap = doc_ref.get(transaction=transaction)
        if snap.exists and snap.to_dict().get("period") == period:
            return False
        transaction.set(doc_ref, {"period": period, "ran_at": datetime.now(timezone.utc)})
        return True

    return _claim(db.transaction(), ref)


def _at_or_after(now_vn: datetime, hhmm: str) -> bool:
    h, m = map(int, hhmm.split(":"))
    return (now_vn.hour, now_vn.minute) >= (h, m)


def _debt_reminder_due(db, now_vn: datetime) -> str | None:
    """Period key if the admin-configured debt reminder is due now, else None."""
    doc = db.document("_settings/debt_reminder").get()
    if not doc.exists:
        return None
    cfg = doc.to_dict()
    if not cfg.get("enabled") or not _at_or_after(now_vn, cfg.get("time") or "09:00"):
        return None
    schedule = cfg.get("schedule", "weekly")
    if schedule != "daily":
        if _DAYS[now_vn.weekday()] != cfg.get("day_of_week", "mon"):
            return None
        # Same weeks as the old APScheduler trigger week="*/2": odd ISO weeks
        if schedule == "biweekly" and now_vn.isocalendar().week % 2 == 0:
            return None
    return now_vn.date().isoformat()


def _jobs():
    # Looked up at call time so tests can monkeypatch the job functions
    from app.services import scheduler
    return scheduler


def run_tick(db, now: datetime | None = None) -> list[str]:
    """Run whatever is due at `now`. Returns the names of jobs that ran."""
    from app.services.pickup import run_due

    now = now or datetime.now(timezone.utc)
    now_vn = now.astimezone(VN_TZ)
    jobs = _jobs()
    ran = []

    def guarded(name, fn):
        try:
            fn()
            ran.append(name)
        except Exception:  # one failing job must not block the others
            logger.exception("Cron job %s failed", name)

    if 6 <= now_vn.hour <= 22:
        try:
            if run_due(db, now):
                ran.append("pickup")
        except Exception:
            logger.exception("Cron job pickup failed")

    today = now_vn.date().isoformat()
    if _at_or_after(now_vn, "12:05") and claim(db, "auto_lock", today):
        guarded("auto_lock", jobs._job_auto_lock_past_deadline)

    if now_vn.day == 1 and _at_or_after(now_vn, "08:00") and claim(db, "monthly_statement", today[:7]):
        guarded("monthly_statement", jobs._job_monthly_statement)

    period = _debt_reminder_due(db, now_vn)
    if period and claim(db, "debt_reminder", period):
        guarded("debt_reminder", jobs._job_debt_reminder)

    if ran:
        logger.info("Cron tick %s ran: %s", now_vn.strftime("%Y-%m-%d %H:%M"), ", ".join(ran))
    return ran
