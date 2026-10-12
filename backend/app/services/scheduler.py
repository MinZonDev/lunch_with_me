"""APScheduler background jobs."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_scheduler = BackgroundScheduler(timezone=VN_TZ)


def _job_deadline_reminder():
    from app.database import init_db, get_db
    from app.services.email_service import send_order_reminder
    from app.core.config import settings

    init_db()
    db = get_db()
    now_utc = datetime.now(timezone.utc)
    window_start = now_utc + timedelta(minutes=1)
    window_end = now_utc + timedelta(minutes=31)

    open_orders = [s.to_dict() for s in db.collection("daily_orders").where("status", "==", "open").stream()]
    for order in open_orders:
        deadline = order.get("order_deadline")
        if not deadline:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if not (window_start <= deadline <= window_end):
            continue

        # Find members who haven't ordered
        items = [s.to_dict() for s in db.collection("order_items").where("daily_order_id", "==", order["id"]).stream()]
        pending_member_ids = {i["member_id"] for i in items if not i.get("is_eating")}

        # Find users linked to pending members
        users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]
        users = [u for u in users if u.get("member_id") in pending_member_ids and u.get("email")]

        deadline_vn = deadline.astimezone(VN_TZ)
        deadline_str = deadline_vn.strftime("%H:%M")
        order_date_str = datetime.strptime(order["order_date"], "%Y-%m-%d").strftime("%d/%m/%Y")

        for user in users:
            send_order_reminder(
                order_date=order_date_str,
                deadline_str=deadline_str,
                member_name=user["full_name"],
                email=user["email"],
                frontend_url=settings.frontend_url,
            )


def _job_auto_lock_past_deadline():
    from app.database import init_db, get_db

    init_db()
    db = get_db()
    now_utc = datetime.now(timezone.utc)

    open_orders = [s for s in db.collection("daily_orders").where("status", "==", "open").stream()]
    batch = db.batch()
    locked = 0
    for snap in open_orders:
        deadline = snap.to_dict().get("order_deadline")
        if not deadline:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= now_utc:
            batch.update(snap.reference, {"status": "locked"})
            locked += 1
    if locked:
        batch.commit()
        print(f"[Scheduler] Auto-locked {locked} expired orders")


def _job_monthly_statement():
    from app.database import init_db, get_db
    from app.services.email_service import send_monthly_statement
    import calendar
    from datetime import date

    init_db()
    db = get_db()
    now_vn = datetime.now(VN_TZ)
    if now_vn.month == 1:
        month, year = 12, now_vn.year - 1
    else:
        month, year = now_vn.month - 1, now_vn.year

    _, last_day = calendar.monthrange(year, month)
    start_str = str(date(year, month, 1))
    end_str = str(date(year, month, last_day))

    from app.services.ledger import compute_balances, finalized_order_ids

    finalized_ids = finalized_order_ids(db)
    month_items = [
        d for d in (s.to_dict() for s in db.collection("order_items")
                    .where("order_date", ">=", start_str).where("order_date", "<=", end_str).stream())
        if d.get("is_eating") and d["daily_order_id"] in finalized_ids
    ]
    balances = compute_balances(db)

    users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]
    for user in users:
        if not user.get("email") or not user.get("member_id"):
            continue
        mid = user["member_id"]

        mine = [i for i in month_items if i["member_id"] == mid]
        days = len(mine)
        spent = sum(i.get("total_cost", 0) or 0 for i in mine)
        balance = balances[mid]["balance"] if mid in balances else 0

        send_monthly_statement(month, year, user["full_name"], user["email"], days, spent, balance)


def check_low_balance(member_id: int):
    from app.database import init_db, get_db
    from app.services.email_service import send_low_balance_alert
    from app.core.config import settings

    init_db()
    db = get_db()

    users = [s.to_dict() for s in db.collection("users").where("member_id", "==", member_id).where("is_active", "==", True).limit(1).stream()]
    if not users or not users[0].get("email"):
        return

    from app.services.ledger import compute_balances

    user = users[0]
    b = compute_balances(db, member_id).get(member_id)
    balance = b["balance"] if b else 0

    if 0 <= balance <= settings.low_balance_threshold:
        send_low_balance_alert(user["full_name"], user["email"], balance)


def _job_debt_reminder():
    from app.database import init_db, get_db
    from app.services.email_service import send_debt_reminder
    from app.services.teams_service import send_debt_reminder_summary
    from app.core.config import settings as cfg

    init_db()
    db = get_db()

    # Check if enabled
    doc = db.document("_settings/debt_reminder").get()
    if not doc.exists or not doc.to_dict().get("enabled"):
        return
    webhook_url = doc.to_dict().get("teams_webhook_url", "")

    from app.services.ledger import compute_balances

    # Compute balances for all active users
    balances = compute_balances(db)
    users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]

    sent = 0
    debtors = []
    for u in users:
        mid = u.get("member_id")
        if not mid:
            continue
        balance = balances[mid]["balance"] if mid in balances else 0
        if balance < 0:
            debtors.append({"name": u.get("nickname") or u["full_name"], "balance": balance, "email": u.get("email", "")})
            if u.get("email"):
                send_debt_reminder(u["full_name"], u["email"], balance, cfg.frontend_url)
                sent += 1

    send_debt_reminder_summary(debtors, cfg.frontend_url, webhook_url)

    print(f"[Scheduler] Debt reminder sent to {sent} members")


_DAY_MAP = {"mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu", "fri": "fri", "sat": "sat", "sun": "sun"}


def reschedule_debt_reminder(cfg):
    """Kept for callers; the tick reads the debt reminder settings every minute."""


def _job_tick():
    from app.database import init_db, get_db
    from app.services.cron import run_tick

    init_db()
    run_tick(get_db())


def start_scheduler():
    """In-process mode (local / VPS): same once-a-minute tick Cloud Scheduler drives on Cloud Run."""
    _scheduler.add_job(_job_tick, CronTrigger(minute="*", timezone=VN_TZ),
                       id="tick", max_instances=1, coalesce=True)
    _scheduler.start()
    print("[Scheduler] Started")


def stop_scheduler():
    _scheduler.shutdown(wait=False)
