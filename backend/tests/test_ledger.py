"""Unit tests for the shared balance formula in services/ledger.py."""
from app.services.ledger import compute_balances
from tests.conftest import seed_deposit, seed_member


def _seed_item(db, item_id, order_id, member_id, cost, is_eating=True):
    db.collection("order_items").document(str(item_id)).set({
        "id": item_id, "daily_order_id": order_id, "member_id": member_id,
        "is_eating": is_eating, "total_cost": cost, "order_date": "2026-07-01",
    })


def _seed_order(db, order_id, status):
    db.collection("daily_orders").document(f"2026-07-{order_id:02d}").set({
        "id": order_id, "order_date": f"2026-07-{order_id:02d}", "status": status,
    })


def test_balance_formula(db):
    seed_member(db, 1, "An")
    seed_deposit(db, 1, 1, 200)
    seed_deposit(db, 2, 1, 999, status="pending")          # pending: ignored
    seed_deposit(db, 3, 1, 15, dtype="charge")              # charge: subtracts
    _seed_order(db, 1, "finalized")
    _seed_order(db, 2, "open")
    _seed_item(db, 1, 1, 1, 35)
    _seed_item(db, 2, 2, 1, 50)                             # open order: ignored
    _seed_item(db, 3, 1, 1, 99, is_eating=False)            # not eating: ignored

    b = compute_balances(db)[1]
    assert b == {"deposited": 200, "charged": 15, "spent": 35, "balance": 150}
    assert compute_balances(db, 1)[1] == b


def test_single_member_only_reads_that_member(db):
    seed_deposit(db, 1, 1, 100)
    seed_deposit(db, 2, 2, 70)
    assert set(compute_balances(db, 2)) == {2}
