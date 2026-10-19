"""Blacklist: members in debt whom admin has blocked from ordering.

A member is blocked only while they are on the list AND their balance is
negative. As soon as the balance gets back to >= 0 the entry is dropped, so
paying off the debt unlocks ordering without any admin action.

Docs live in the `blacklist` collection, keyed by member_id.
"""

from app.services.ledger import compute_balances

COLLECTION = "blacklist"


def _balance(db, member_id: int) -> int:
    b = compute_balances(db, member_id).get(member_id)
    return b["balance"] if b else 0


def debt_status(db, member_id: int | None) -> dict:
    """{blocked, debt} for one member; drops a stale entry once the debt is paid."""
    if not member_id:
        return {"blocked": False, "debt": 0}
    ref = db.collection(COLLECTION).document(str(member_id))
    if not ref.get().exists:
        return {"blocked": False, "debt": 0}
    balance = _balance(db, member_id)
    if balance >= 0:
        ref.delete()
        return {"blocked": False, "debt": 0}
    return {"blocked": True, "debt": -balance}


def is_blocked(db, member_id: int | None) -> bool:
    return debt_status(db, member_id)["blocked"]


def prune(db) -> None:
    """Drop every entry whose member no longer owes money."""
    entries = list(db.collection(COLLECTION).stream())
    if not entries:
        return
    balances = compute_balances(db)
    for snap in entries:
        mid = snap.to_dict()["member_id"]
        if (balances.get(mid) or {}).get("balance", 0) >= 0:
            snap.reference.delete()
