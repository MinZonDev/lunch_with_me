"""API tests for /api/deposits: requests, approval, charges, balance math."""
from datetime import datetime, timezone

from tests.conftest import seed_deposit, seed_member


def _seed_finalized_spending(db, order_id, member_id, total_cost, status="finalized"):
    """A finalized daily_order + an eating item for member_id costing total_cost."""
    db.collection("daily_orders").document(str(order_id)).set({
        "id": order_id, "order_date": "2026-07-01", "status": status,
        "total_bill": total_cost, "created_at": datetime.now(timezone.utc),
    })
    db.collection("order_items").document(str(900 + order_id)).set({
        "id": 900 + order_id, "daily_order_id": order_id, "member_id": member_id,
        "dish_name": "Cơm gà", "is_eating": True, "extra_item_cost": 0,
        "total_cost": total_cost, "created_at": datetime.now(timezone.utc),
    })


class TestCreateDeposit:
    def test_user_request_is_pending(self, client, user):
        res = client.post("/api/deposits", headers=user["headers"],
                          json={"amount": 500, "note": "Nạp tháng 7"})
        assert res.status_code == 201
        assert res.json()["status"] == "pending"

    def test_admin_deposit_for_member_is_auto_approved(self, client, admin, user):
        res = client.post("/api/deposits", headers=admin["headers"],
                          json={"amount": 300, "member_id": 2})
        assert res.status_code == 201
        body = res.json()
        assert body["status"] == "approved" and body["member_id"] == 2

    def test_unknown_member_404(self, client, admin):
        res = client.post("/api/deposits", headers=admin["headers"],
                          json={"amount": 300, "member_id": 999})
        assert res.status_code == 404


class TestApproveDeposit:
    def test_admin_approves_pending(self, client, db, admin, user):
        seed_deposit(db, 1, 2, 500, status="pending")
        res = client.post("/api/deposits/1/approve", headers=admin["headers"])
        assert res.status_code == 200
        assert db.collection("deposits").document("1").get().to_dict()["status"] == "approved"

    def test_double_approve_refused(self, client, db, admin, user):
        seed_deposit(db, 1, 2, 500, status="approved")
        assert client.post("/api/deposits/1/approve", headers=admin["headers"]).status_code == 400

    def test_approve_requires_admin(self, client, db, user):
        seed_deposit(db, 1, 2, 500, status="pending")
        assert client.post("/api/deposits/1/approve", headers=user["headers"]).status_code == 403


class TestCharge:
    def test_requires_admin(self, client, user):
        res = client.post("/api/deposits/charge", headers=user["headers"],
                          json={"member_id": 2, "amount": 30})
        assert res.status_code == 403

    def test_admin_creates_approved_charge(self, client, admin, user):
        res = client.post("/api/deposits/charge", headers=admin["headers"],
                          json={"member_id": 2, "amount": 30, "note": "Ship ngoài"})
        assert res.status_code == 201
        body = res.json()
        assert body["type"] == "charge" and body["status"] == "approved"


class TestBalanceSummary:
    def test_balance_math(self, client, db, admin, user):
        """deposited(approved)=500, pending ignored, charge=50, finalized spent=97,
        open-order spending ignored → balance = 500 - 50 - 97 = 353."""
        seed_deposit(db, 1, 2, 500, status="approved")
        seed_deposit(db, 2, 2, 200, status="pending")
        seed_deposit(db, 3, 2, 50, dtype="charge")
        _seed_finalized_spending(db, 10, 2, 97)
        _seed_finalized_spending(db, 11, 2, 999, status="open")  # not finalized → ignored

        res = client.get("/api/deposits/summary", headers=admin["headers"])
        assert res.status_code == 200
        row = next(m for m in res.json() if m["id"] == 2)
        assert row["total_deposited"] == 500
        assert row["total_charged"] == 50
        assert row["total_spent"] == 97
        assert row["balance"] == 353

    def test_user_sees_only_own_balance(self, client, db, admin, user):
        res = client.get("/api/deposits/summary", headers=user["headers"])
        assert res.status_code == 200
        assert [m["id"] for m in res.json()] == [2]

    def test_admin_sees_all_members(self, client, db, admin, user):
        res = client.get("/api/deposits/summary", headers=admin["headers"])
        assert {m["id"] for m in res.json()} == {1, 2}


class TestMemberDetail:
    def test_user_cannot_view_other_member(self, client, admin, user):
        assert client.get("/api/deposits/member/1", headers=user["headers"]).status_code == 403

    def test_own_detail_with_running_balance(self, client, db, user):
        seed_deposit(db, 1, 2, 500, status="approved",
                     created_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        seed_deposit(db, 2, 2, 50, dtype="charge",
                     created_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        res = client.get("/api/deposits/member/2", headers=user["headers"])
        assert res.status_code == 200
        body = res.json()
        assert body["balance"] == 450
        # Newest first; running balance accumulated oldest → newest
        assert [t["running_balance"] for t in body["transactions"]] == [450, 500]


class TestManageDeposits:
    def test_list_shows_own_only_for_user(self, client, db, admin, user):
        seed_deposit(db, 1, 1, 100)
        seed_deposit(db, 2, 2, 200)
        mine = client.get("/api/deposits", headers=user["headers"]).json()
        assert [d["id"] for d in mine] == [2]
        everyone = client.get("/api/deposits", headers=admin["headers"]).json()
        assert {d["id"] for d in everyone} == {1, 2}

    def test_admin_edits_amount_and_note(self, client, db, admin, user):
        seed_deposit(db, 1, 2, 500)
        res = client.put("/api/deposits/1", headers=admin["headers"],
                         json={"amount": 550, "note": "Sửa lại"})
        assert res.status_code == 200
        stored = db.collection("deposits").document("1").get().to_dict()
        assert stored["amount"] == 550 and stored["note"] == "Sửa lại"

    def test_delete_requires_admin(self, client, db, user):
        seed_deposit(db, 1, 2, 500)
        assert client.delete("/api/deposits/1", headers=user["headers"]).status_code == 403

    def test_admin_deletes_deposit(self, client, db, admin, user):
        seed_deposit(db, 1, 2, 500)
        assert client.delete("/api/deposits/1", headers=admin["headers"]).status_code == 204
        assert not db.collection("deposits").document("1").get().exists
