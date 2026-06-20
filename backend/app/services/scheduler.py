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

    all_orders = [s.to_dict() for s in db.collection("daily_orders").where("status", "==", "finalized").stream()]
    month_order_ids = {o["id"] for o in all_orders if start_str <= o["order_date"] <= end_str}

    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    all_deposits = [s.to_dict() for s in db.collection("deposits").stream()]
    all_finalized_ids = {o["id"] for o in all_orders}

    users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]
    for user in users:
        if not user.get("email") or not user.get("member_id"):
            continue
        mid = user["member_id"]

        month_items = [i for i in all_items if i["member_id"] == mid and i["daily_order_id"] in month_order_ids]
        days = len(month_items)
        spent = sum(i.get("total_cost", 0) or 0 for i in month_items)

        total_dep = sum(d["amount"] for d in all_deposits if d["member_id"] == mid)
        total_spent_all = sum(i.get("total_cost", 0) or 0 for i in all_items if i["member_id"] == mid and i["daily_order_id"] in all_finalized_ids)
        balance = total_dep - total_spent_all

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

    user = users[0]
    finalized_ids = {s.to_dict()["id"] for s in db.collection("daily_orders").where("status", "==", "finalized").stream()}
    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]

    total_dep = sum(s.to_dict()["amount"] for s in db.collection("deposits").where("member_id", "==", member_id).stream())
    total_spent = sum(i.get("total_cost", 0) or 0 for i in all_items if i["member_id"] == member_id and i["daily_order_id"] in finalized_ids)
    balance = total_dep - total_spent

    if 0 <= balance <= settings.low_balance_threshold:
        send_low_balance_alert(user["full_name"], user["email"], balance)


def start_scheduler():
    _scheduler.add_job(_job_deadline_reminder, "interval", minutes=5, id="deadline_reminder")
    _scheduler.add_job(_job_auto_lock_past_deadline, CronTrigger(hour=12, minute=5, timezone=VN_TZ), id="auto_lock")
    _scheduler.add_job(_job_monthly_statement, CronTrigger(day=1, hour=8, timezone=VN_TZ), id="monthly_statement")
    _scheduler.start()
    print("[Scheduler] Started")


def stop_scheduler():
    _scheduler.shutdown(wait=False)
