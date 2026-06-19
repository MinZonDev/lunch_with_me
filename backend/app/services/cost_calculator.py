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

from app.models import OrderItem, DailyOrder
import math


def calculate_costs(daily_order: DailyOrder, items: list[OrderItem]) -> dict:
    """
    Calculate how to split the bill for a daily order.

    Returns:
        dict with:
        - shared_cost_per_person: phần chia đều (regular)
        - shared_cost_per_person_chay: phần chia đều (chay)
        - item_costs: list of {item_id, member_id, total_cost}
    """
    # Separate regular and chay eaters
    regular_eaters = [item for item in items if item.is_eating and not item.is_chay]
    chay_eaters = [item for item in items if item.is_eating and item.is_chay]

    result = {
        "shared_cost_per_person": 0,
        "shared_cost_per_person_chay": 0,
        "item_costs": [],
    }

    # Calculate regular meal costs
    if regular_eaters and daily_order.total_bill > 0:
        total_extras = sum(item.extra_item_cost or 0 for item in regular_eaters)
        shared_pool = daily_order.total_bill - total_extras
        per_person = math.ceil(shared_pool / len(regular_eaters)) if len(regular_eaters) > 0 else 0
        result["shared_cost_per_person"] = per_person

        for item in regular_eaters:
            total = per_person + (item.extra_item_cost or 0)
            result["item_costs"].append({
                "item_id": item.id,
                "member_id": item.member_id,
                "total_cost": total,
            })

    # Calculate chay meal costs
    if chay_eaters and daily_order.total_bill_chay > 0:
        total_extras_chay = sum(item.extra_item_cost or 0 for item in chay_eaters)
        shared_pool_chay = daily_order.total_bill_chay - total_extras_chay
        per_person_chay = math.ceil(shared_pool_chay / len(chay_eaters)) if len(chay_eaters) > 0 else 0
        result["shared_cost_per_person_chay"] = per_person_chay

        for item in chay_eaters:
            total = per_person_chay + (item.extra_item_cost or 0)
            result["item_costs"].append({
                "item_id": item.id,
                "member_id": item.member_id,
                "total_cost": total,
            })

    # Non-eaters get 0 cost
    non_eaters = [item for item in items if not item.is_eating]
    for item in non_eaters:
        result["item_costs"].append({
            "item_id": item.id,
            "member_id": item.member_id,
            "total_cost": 0,
        })

    return result
