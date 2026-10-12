"""Shared read helpers for balances and lookups.

Balance = approved deposits + order payments - charges - finalized meal costs
          - completed withdrawals.
Every place that shows or acts on a balance goes through compute_balances so
the formula lives in one spot.

Reads are kept cheap by projecting only the fields we sum (select) and by
batch-fetching documents (get_all) instead of one get() per id.
"""

from collections import defaultdict


def classify_txn(txn: dict) -> tuple[str, int]:
    """Classify a deposits-collection row into (bucket, amount) for the balance.

    Buckets in CREDIT_BUCKETS add to the balance, the rest subtract.
    """
    ttype = txn.get("type", "deposit")
    amount = txn.get("amount", 0) or 0
    if ttype == "deposit":
        return ("deposited", amount) if txn.get("status") == "approved" else ("ignored", 0)
    if ttype == "order_payment":
        # Member paid the restaurant out of pocket for an order: counts as money in
        return "deposited", amount
    if ttype == "charge":
        return "charged", amount
    if ttype == "withdrawal":
        # Only money actually transferred out counts; pending/rejected/cancelled don't
        return ("withdrawn", amount) if txn.get("status") == "done" else ("ignored", 0)
    return "ignored", 0


CREDIT_BUCKETS = {"deposited"}


def signed_delta(txn: dict) -> int:
    """How much a deposits-collection row moves the balance (+ credit / - debit)."""
    bucket, amount = classify_txn(txn)
    if bucket == "ignored":
        return 0
    return amount if bucket in CREDIT_BUCKETS else -amount


def member_names(db, member_ids) -> dict[int, str]:
    """Batch-load {member_id: name} for the given ids in one round trip."""
    ids = {int(m) for m in member_ids if m is not None}
    if not ids:
        return {}
    refs = [db.collection("members").document(str(m)) for m in ids]
    result = {m: "?" for m in ids}
    for snap in db.get_all(refs, field_paths=["id", "name"]):
        if snap.exists:
            d = snap.to_dict()
            result[int(snap.id)] = d.get("name", "?")
    return result


def chunks(values, size=30):
    """Firestore 'in' filters accept at most 30 values."""
    values = list(values)
    for i in range(0, len(values), size):
        yield values[i:i + size]


def orders_by_ids(db, order_ids, finalized_only=False) -> dict[int, dict]:
    """Batch-load daily_orders by numeric id into {id: data}.

    Queries on the id field rather than doc id: imported orders are keyed by date.
    """
    result = {}
    for chunk in chunks({int(o) for o in order_ids}):
        for snap in db.collection("daily_orders").where("id", "in", chunk).stream():
            d = snap.to_dict()
            if not finalized_only or d.get("status") == "finalized":
                result[d["id"]] = d
    return result


def finalized_order_ids(db) -> set[int]:
    return {
        s.to_dict()["id"]
        for s in db.collection("daily_orders").where("status", "==", "finalized").select(["id"]).stream()
    }


def compute_balances(db, member_id: int | None = None) -> dict[int, dict]:
    """Return {member_id: {deposited, charged, spent, balance}}.

    With member_id, only that member's rows are read; otherwise everyone's.
    """
    deposits = db.collection("deposits")
    items = db.collection("order_items").where("is_eating", "==", True)
    if member_id is not None:
        deposits = deposits.where("member_id", "==", member_id)
        items = items.where("member_id", "==", member_id)

    totals: dict[int, dict] = defaultdict(lambda: {"deposited": 0, "charged": 0, "spent": 0, "withdrawn": 0})

    for snap in deposits.select(["member_id", "amount", "type", "status"]).stream():
        t = snap.to_dict()
        bucket, amount = classify_txn(t)
        if bucket != "ignored":
            totals[t["member_id"]][bucket] += amount

    finalized = finalized_order_ids(db)
    for snap in items.select(["member_id", "daily_order_id", "total_cost"]).stream():
        i = snap.to_dict()
        if i["daily_order_id"] in finalized:
            totals[i["member_id"]]["spent"] += i.get("total_cost", 0) or 0

    for t in totals.values():
        t["balance"] = t["deposited"] - t["charged"] - t["spent"] - t["withdrawn"]
    return totals


def empty_balance() -> dict:
    return {"deposited": 0, "charged": 0, "spent": 0, "withdrawn": 0, "balance": 0}
