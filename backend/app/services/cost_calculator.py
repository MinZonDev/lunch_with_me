"""
Cost calculator for splitting lunch bills.

Logic:
1. Filter members who are eating (is_eating=True)
2. Separate into regular and chay groups
3. For each group:
   a. Sum up all extra item costs
   b. Shared pool = total_bill - total_extras
   c. Per person share = shared_pool / num_eaters (rounded)
   d. Each person pays = share + their extra cost
"""

import math


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
        total_extras = sum(getattr(i, "extra_item_cost", 0) or 0 for i in regular_eaters)
        shared_pool = total_bill - total_extras
        per_person = math.ceil(shared_pool / len(regular_eaters)) if regular_eaters else 0
        result["shared_cost_per_person"] = per_person
        for item in regular_eaters:
            total = per_person + (getattr(item, "extra_item_cost", 0) or 0)
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": total})

    if chay_eaters and total_bill_chay > 0:
        total_extras_chay = sum(getattr(i, "extra_item_cost", 0) or 0 for i in chay_eaters)
        shared_pool_chay = total_bill_chay - total_extras_chay
        per_person_chay = math.ceil(shared_pool_chay / len(chay_eaters)) if chay_eaters else 0
        result["shared_cost_per_person_chay"] = per_person_chay
        for item in chay_eaters:
            total = per_person_chay + (getattr(item, "extra_item_cost", 0) or 0)
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": total})

    for item in items:
        if not item.is_eating:
            result["item_costs"].append({"item_id": item.id, "member_id": item.member_id, "total_cost": 0})

    return result
