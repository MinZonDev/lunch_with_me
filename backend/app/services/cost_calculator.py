"""
Cost calculator for splitting lunch bills.

Logic:
1. Filter members who are eating (is_eating=True)
2. Separate into regular and chay groups
3. For each group:
   a. totalExtra = sum of extra_item_cost from all eaters
   b. baseShare = (totalBill - totalExtra) / num_eaters
   c. amountToPay = baseShare + user.extra_item_cost
"""

from decimal import Decimal, ROUND_HALF_UP


def _split_bill(total_bill: float, users: list) -> list:
    """
    Split total_bill among users based on their extra costs.

    Each user dict must have an 'extra_item_cost' key (defaults to 0).
    Returns a list of amounts to pay, one per user, as integers.

    Example: total_bill=105, users with extraCost [0, 10, 5]
      totalExtra=15, baseShare=30 => payments [30, 40, 35]
    """
    total = Decimal(str(total_bill))
    extras = [Decimal(str(u.get("extra_item_cost", 0) or 0)) for u in users]
    total_extra = sum(extras)
    n = len(users)
    base_share = (total - total_extra) / n
    return [
        int((base_share + extra).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        for extra in extras
    ]


def calculate_costs(daily_order, items: list) -> dict:
    """
    Calculate how to split the bill for a daily order.
    Works with SimpleNamespace objects or any object with the expected attributes.
    """
    regular_eaters = [item for item in items if item.is_eating and not item.is_chay]
    chay_eaters = [item for item in items if item.is_eating and item.is_chay]

    result = {
        "shared_cost_per_person": 0,
        "shared_cost_per_person_chay": 0,
        "item_costs": [],
    }

    total_bill = getattr(daily_order, "total_bill", 0) or 0
    total_bill_chay = getattr(daily_order, "total_bill_chay", 0) or 0

    if regular_eaters and total_bill > 0:
        user_dicts = [{"extra_item_cost": getattr(i, "extra_item_cost", 0) or 0} for i in regular_eaters]
        total_extra = sum(d["extra_item_cost"] for d in user_dicts)
        base_share = int(
            (Decimal(str(total_bill)) - Decimal(str(total_extra)))
            .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            / len(regular_eaters)
        )
        result["shared_cost_per_person"] = base_share
        payments = _split_bill(total_bill, user_dicts)
        for item, amount in zip(regular_eaters, payments):
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": amount})

    if chay_eaters and total_bill_chay > 0:
        user_dicts_chay = [{"extra_item_cost": getattr(i, "extra_item_cost", 0) or 0} for i in chay_eaters]
        total_extra_chay = sum(d["extra_item_cost"] for d in user_dicts_chay)
        base_share_chay = int(
            (Decimal(str(total_bill_chay)) - Decimal(str(total_extra_chay)))
            .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            / len(chay_eaters)
        )
        result["shared_cost_per_person_chay"] = base_share_chay
        payments_chay = _split_bill(total_bill_chay, user_dicts_chay)
        for item, amount in zip(chay_eaters, payments_chay):
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": amount})

    for item in items:
        if not item.is_eating:
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": 0})

    return result
