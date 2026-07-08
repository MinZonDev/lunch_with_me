"""
Cost calculator for splitting lunch bills.

Logic:
1. Filter members who are eating (is_eating=True)
2. totalExtra = sum of extra_item_cost from all eaters
3. shared_base = total_bill - totalExtra
4. base_per_person = ceil(shared_base / n)  (round up)
5. Each person pays the same base + own extra_item_cost
   Everyone pays equally; sum(payments) may exceed total_bill
   by up to (n - 1) due to rounding up.
"""
import math


def _split_bill(total_bill: int, users: list) -> list:
    """
    Split total_bill among users based on their extra costs.

    Each user dict must have an 'extra_item_cost' key (defaults to 0).
    Returns a list of amounts to pay, one per user, as integers.
    The shared portion is rounded UP so everyone pays the same base.

    Example: total_bill=100, 3 users with extraCost [0, 0, 0]
      shared_base=100, base=ceil(100/3)=34 => payments [34, 34, 34]

    Example: total_bill=105, users with extraCost [0, 10, 5]
      shared_base=90, base=30 => payments [30, 40, 35]
    """
    extras = [int(u.get("extra_item_cost", 0) or 0) for u in users]
    total_extra = sum(extras)
    n = len(users)
    shared_base = total_bill - total_extra
    base = math.ceil(shared_base / n)
    return [base + extra for extra in extras]


def calculate_costs(daily_order, items: list) -> dict:
    """
    Calculate how to split the bill for a daily order.
    Works with SimpleNamespace objects or any object with the expected attributes.
    """
    eaters = [item for item in items if item.is_eating]

    result = {
        "shared_cost_per_person": 0,
        "item_costs": [],
    }

    total_bill = getattr(daily_order, "total_bill", 0) or 0

    if eaters and total_bill > 0:
        user_dicts = [{"extra_item_cost": getattr(i, "extra_item_cost", 0) or 0} for i in eaters]
        total_extra = sum(d["extra_item_cost"] for d in user_dicts)
        shared_base = total_bill - total_extra
        result["shared_cost_per_person"] = math.ceil(shared_base / len(eaters))
        payments = _split_bill(total_bill, user_dicts)
        for item, amount in zip(eaters, payments):
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": amount})

    for item in items:
        if not item.is_eating:
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": 0})

    return result
