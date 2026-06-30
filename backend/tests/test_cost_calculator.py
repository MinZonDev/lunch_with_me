"""
Unit tests for cost_calculator.py

Key invariants tested:
- sum(payments) == total_bill always (no rounding drift)
- Extras are allocated to correct individuals
- Zero-bill and no-eater edge cases
- shared_cost_per_person reflects base share (before extras)
"""
import pytest
from types import SimpleNamespace
from app.services.cost_calculator import _split_bill, calculate_costs


# ──────────────────────────────────────────────────────────────
# _split_bill
# ──────────────────────────────────────────────────────────────

class TestSplitBill:
    def _users(self, extras):
        return [{"extra_item_cost": e} for e in extras]

    def test_equal_split_no_extras(self):
        payments = _split_bill(90, self._users([0, 0, 0]))
        assert payments == [30, 30, 30]
        assert sum(payments) == 90

    def test_sum_equals_total_when_indivisible(self):
        """100 / 3 người — không chia hết, nhưng tổng phải bằng 100."""
        payments = _split_bill(100, self._users([0, 0, 0]))
        assert sum(payments) == 100
        # Người đầu được +1 từ remainder
        assert payments[0] == 34
        assert payments[1] == 33
        assert payments[2] == 33

    def test_sum_equals_total_larger_remainder(self):
        """101 / 3 — remainder=2, hai người đầu được 34, người cuối 33."""
        payments = _split_bill(101, self._users([0, 0, 0]))
        assert sum(payments) == 101
        assert payments == [34, 34, 33]

    def test_extras_allocated_individually(self):
        """Total=105, extras=[0,10,5]: shared_base=90 /3=30 each + own extra."""
        payments = _split_bill(105, self._users([0, 10, 5]))
        assert payments == [30, 40, 35]
        assert sum(payments) == 105

    def test_extras_with_remainder(self):
        """Total=100, extras=[5, 0, 0]: shared_base=95, 95//3=31 r=2."""
        payments = _split_bill(100, self._users([5, 0, 0]))
        # shared_base=95, base=31, remainder=2
        # person0: 31+1+5=37, person1: 31+1+0=32, person2: 31+0+0=31
        assert sum(payments) == 100
        assert payments[0] == 37  # extra + remainder
        assert payments[1] == 32
        assert payments[2] == 31

    def test_single_person_gets_all(self):
        payments = _split_bill(150, self._users([0]))
        assert payments == [150]

    def test_single_person_with_extra(self):
        payments = _split_bill(150, self._users([20]))
        assert payments == [150]
        assert sum(payments) == 150

    def test_two_people_odd_bill(self):
        payments = _split_bill(99, self._users([0, 0]))
        assert sum(payments) == 99
        assert payments == [50, 49]

    def test_zero_total_bill(self):
        payments = _split_bill(0, self._users([0, 0, 0]))
        assert payments == [0, 0, 0]
        assert sum(payments) == 0

    def test_extra_cost_missing_key_defaults_zero(self):
        users = [{}, {}, {"extra_item_cost": None}]
        payments = _split_bill(90, users)
        assert payments == [30, 30, 30]
        assert sum(payments) == 90

    def test_large_group(self):
        n = 10
        payments = _split_bill(1000, self._users([0] * n))
        assert payments == [100] * n
        assert sum(payments) == 1000

    def test_large_group_indivisible(self):
        """1001 / 10 = 100 r1 → đúng một người được 101."""
        payments = _split_bill(1001, self._users([0] * 10))
        assert sum(payments) == 1001
        assert payments.count(101) == 1
        assert payments.count(100) == 9


# ──────────────────────────────────────────────────────────────
# calculate_costs
# ──────────────────────────────────────────────────────────────

def _make_order(total_bill):
    return SimpleNamespace(total_bill=total_bill)


def _make_item(id, member_id, is_eating, extra=0):
    return SimpleNamespace(
        id=id,
        member_id=member_id,
        is_eating=is_eating,
        extra_item_cost=extra,
    )


class TestCalculateCosts:
    def test_no_eaters_returns_zeros(self):
        order = _make_order(200)
        items = [_make_item(1, 1, False), _make_item(2, 2, False)]
        result = calculate_costs(order, items)

        assert result["shared_cost_per_person"] == 0
        assert all(c["total_cost"] == 0 for c in result["item_costs"])

    def test_zero_bill_no_charge(self):
        order = _make_order(0)
        items = [_make_item(1, 1, True), _make_item(2, 2, True)]
        result = calculate_costs(order, items)

        assert result["shared_cost_per_person"] == 0
        assert all(c["total_cost"] == 0 for c in result["item_costs"])

    def test_even_split_three_people(self):
        order = _make_order(90)
        items = [_make_item(i, i, True) for i in range(1, 4)]
        result = calculate_costs(order, items)

        assert result["shared_cost_per_person"] == 30
        costs = {c["member_id"]: c["total_cost"] for c in result["item_costs"]}
        assert all(v == 30 for v in costs.values())
        assert sum(costs.values()) == 90

    def test_indivisible_bill_sum_correct(self):
        """100k / 3 người: tổng phải bằng 100."""
        order = _make_order(100)
        items = [_make_item(i, i, True) for i in range(1, 4)]
        result = calculate_costs(order, items)

        costs = [c["total_cost"] for c in result["item_costs"] if c["member_id"] in {1, 2, 3}]
        assert sum(costs) == 100
        # base_share hiển thị = 33 (floor)
        assert result["shared_cost_per_person"] == 33

    def test_extras_deducted_from_shared(self):
        """
        Total=105, 3 người, người id=1 có extra=10, người id=2 extra=5.
        shared_base=90, base=30/người.
        id=1: 30+10=40, id=2: 30+5=35, id=3: 30+0=30
        """
        order = _make_order(105)
        items = [
            _make_item(1, 1, True, extra=10),
            _make_item(2, 2, True, extra=5),
            _make_item(3, 3, True, extra=0),
        ]
        result = calculate_costs(order, items)

        costs = {c["member_id"]: c["total_cost"] for c in result["item_costs"]}
        assert costs[1] == 40
        assert costs[2] == 35
        assert costs[3] == 30
        assert sum(costs.values()) == 105

    def test_non_eaters_get_zero(self):
        order = _make_order(100)
        items = [
            _make_item(1, 1, True),
            _make_item(2, 2, False),
            _make_item(3, 3, True),
        ]
        result = calculate_costs(order, items)

        costs = {c["member_id"]: c["total_cost"] for c in result["item_costs"]}
        assert costs[2] == 0
        assert costs[1] + costs[3] == 100

    def test_all_item_costs_present(self):
        """Tất cả items (kể cả không ăn) đều có trong item_costs."""
        order = _make_order(90)
        items = [
            _make_item(1, 1, True),
            _make_item(2, 2, False),
            _make_item(3, 3, True),
        ]
        result = calculate_costs(order, items)

        item_ids = {c["item_id"] for c in result["item_costs"]}
        assert item_ids == {1, 2, 3}

    def test_sum_always_equals_total_bill(self):
        """Tổng tiền của những người ăn phải luôn bằng total_bill."""
        order = _make_order(253)
        items = [_make_item(i, i, True) for i in range(1, 8)]  # 7 người
        result = calculate_costs(order, items)

        eating_costs = sum(
            c["total_cost"] for c in result["item_costs"]
            if any(it.id == c["item_id"] and it.is_eating for it in items)
        )
        assert eating_costs == 253

    def test_shared_cost_per_person_is_floor_of_base(self):
        """shared_cost_per_person = (total - extras) // n (không phải round)."""
        order = _make_order(100)
        items = [_make_item(i, i, True) for i in range(1, 4)]  # 3 người
        result = calculate_costs(order, items)
        # (100-0)//3 = 33
        assert result["shared_cost_per_person"] == 33

    def test_single_eater_pays_all(self):
        order = _make_order(150)
        items = [
            _make_item(1, 1, True),
            _make_item(2, 2, False),
        ]
        result = calculate_costs(order, items)

        costs = {c["member_id"]: c["total_cost"] for c in result["item_costs"]}
        assert costs[1] == 150
        assert costs[2] == 0

    def test_extra_exceeds_bill_does_not_crash(self):
        """Edge case: extra_cost > total_bill (negative shared_base)."""
        order = _make_order(50)
        items = [
            _make_item(1, 1, True, extra=60),
            _make_item(2, 2, True, extra=0),
        ]
        # shared_base = 50 - 60 = -10, base = -10//2 = -5
        result = calculate_costs(order, items)
        # Tổng vẫn phải bằng 50
        eating_costs = sum(c["total_cost"] for c in result["item_costs"])
        assert eating_costs == 50
