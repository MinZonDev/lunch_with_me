"""Pick who collects the food (người lấy cơm) for an order and email the eaters.

Runs automatically once the order deadline passes (scheduler, every minute)
and on demand when an admin/orderer re-rolls. The draw is weighted by recent
history so the duty rotates: whoever collected on the previous order day sits
out (when there are enough other eaters), and each pickup in the last
HISTORY_DAYS cuts a member's chance to 1/(1+n)^2.
"""

import logging
import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from firebase_admin import firestore as fb_firestore

logger = logging.getLogger("lwm.pickup")

HISTORY_DAYS = 14


def _eater_ids(db, order_id: int) -> list[int]:
    return sorted({
        s.to_dict()["member_id"] for s in db.collection("order_items")
        .where("daily_order_id", "==", order_id)
        .where("is_eating", "==", True).select(["member_id"]).stream()
    })


def _recent_pickups(db, order_date: str) -> tuple[Counter, set[int]]:
    """Pickup counts per member over the last HISTORY_DAYS before order_date,
    plus who collected on the most recent earlier day that had a pickup."""
    start = (date.fromisoformat(str(order_date)) - timedelta(days=HISTORY_DAYS)).isoformat()
    by_date: dict[str, set[int]] = {}
    for s in (db.collection("daily_orders")
              .where("order_date", ">=", start).where("order_date", "<", str(order_date))
              .select(["order_date", "pickup_member_ids"]).stream()):
        o = s.to_dict()
        if o.get("pickup_member_ids"):
            by_date.setdefault(str(o["order_date"]), set()).update(o["pickup_member_ids"])
    counts = Counter(m for ids in by_date.values() for m in ids)
    last = by_date[max(by_date)] if by_date else set()
    return counts, last


def _weighted_sample(eaters: list[int], count: int, counts: Counter, last: set[int], rng) -> list[int]:
    pool = [m for m in eaters if m not in last]
    if len(pool) < count:
        pool = list(eaters)
    chosen = []
    for _ in range(count):
        weights = [1 / (1 + counts[m]) ** 2 for m in pool]
        m = rng.choices(pool, weights=weights)[0]
        chosen.append(m)
        pool.remove(m)
    return chosen


def pick(db, order_ref, *, reroll: bool = False, rng: random.Random | None = None) -> dict | None:
    """Choose pickers and store them on the order.

    Without reroll this is a no-op if pickers were already chosen, and the
    claim happens in a transaction so concurrent scheduler runs (several
    Cloud Run instances) can't both pick and both send emails.
    Returns the updated order dict, or None if nothing was picked.
    """
    order = order_ref.get().to_dict()
    eaters = _eater_ids(db, order["id"])
    if not eaters:
        return None
    count = min(max(order.get("pickup_count", 1) or 1, 1), len(eaters))
    counts, last = _recent_pickups(db, order["order_date"])
    chosen = sorted(_weighted_sample(eaters, count, counts, last, rng or random))
    names_snap = db.get_all([db.collection("members").document(str(m)) for m in chosen])
    names = {int(s.id): s.to_dict().get("name", "?") for s in names_snap if s.exists}
    fields = {
        "pickup_member_ids": chosen,
        "pickup_names": [names.get(m, "?") for m in chosen],
        "pickup_picked_at": datetime.now(timezone.utc),
    }

    @fb_firestore.transactional
    def _claim(transaction, ref):
        current = ref.get(transaction=transaction).to_dict()
        if current.get('pickup_method') == 'collective':
            return False
        if current.get("pickup_member_ids") and not reroll:
            return False
        transaction.update(ref, fields)
        return True

    if not _claim(db.transaction(), order_ref):
        return None
    logger.info("Order %s pickup: %s", order["id"], fields["pickup_names"])
    return {**order, **fields}


def notify(db, order: dict) -> int:
    """Email everyone who ordered who is collecting the food today."""
    from app.core.config import settings
    from app.services.email_service import send_pickup_announcement

    eaters = set(_eater_ids(db, order["id"]))
    users = [u for u in (s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream())
             if u.get("member_id") in eaters and u.get("email")]
    picked = set(order.get("pickup_member_ids") or [])
    order_date = datetime.strptime(str(order["order_date"]), "%Y-%m-%d").strftime("%d/%m/%Y")
    for u in users:
        send_pickup_announcement(
            email=u["email"],
            full_name=u.get("full_name", ""),
            order_date=order_date,
            order_name=order.get("name"),
            picker_names=order.get("pickup_names") or [],
            is_picker=u["member_id"] in picked,
            frontend_url=settings.frontend_url,
        )
    return len(users)


def run_due(db, now: datetime | None = None) -> int:
    """Pick for today's orders whose deadline has passed and that have no pickers yet."""
    from zoneinfo import ZoneInfo

    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    done = 0
    for snap in db.collection("daily_orders").where("order_date", "==", today).stream():
        o = snap.to_dict()
        deadline = o.get("order_deadline")
        if o.get('pickup_method') == 'collective' or o.get("pickup_member_ids") or not deadline:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline > now:
            continue
        picked = pick(db, snap.reference)
        if picked:
            notify(db, picked)
            done += 1
    return done
