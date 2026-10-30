"""Pick who collects the food (người lấy cơm) for an order and email the eaters.

Runs automatically once the order deadline passes (scheduler, every minute)
and on demand when an admin/orderer re-rolls. Everyone who ordered has the
same chance.
"""

import logging
import random
from datetime import datetime, timezone

from firebase_admin import firestore as fb_firestore

logger = logging.getLogger("lwm.pickup")


def _eater_ids(db, order_id: int) -> list[int]:
    return sorted({
        s.to_dict()["member_id"] for s in db.collection("order_items")
        .where("daily_order_id", "==", order_id)
        .where("is_eating", "==", True).select(["member_id"]).stream()
    })


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
    chosen = sorted((rng or random).sample(eaters, count))
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
