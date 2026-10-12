"""Orderer role (người đặt cơm) and payer credit on finalize."""
import pytest

from tests.conftest import auth_headers, seed_member, seed_user


@pytest.fixture()
def orderer(db):
    seed_member(db, 5, "Đặt Cơm")
    seed_user(db, 5, "orderer", role="orderer", member_id=5)
    return {"user_id": 5, "member_id": 5, "headers": auth_headers(5, "orderer")}


def _order_with_eaters(client, headers, member_ids, order_date="2026-07-10"):
    order = client.post("/api/orders", headers=headers, json={"order_date": order_date, "name": "Cơm"}).json()
    for mid in member_ids:
        # Each member picks their own dish (users 2 and 5 are linked to members 2 and 5)
        res = client.post(f"/api/orders/{order['id']}/items", headers=auth_headers(mid),
                          json={"member_id": mid, "dish_name": "Gà"})
        assert res.status_code == 201, res.text
    return order["id"]


def _credits(db, order_id):
    return [s.to_dict() for s in db.collection("deposits").stream()
            if s.to_dict().get("daily_order_id") == order_id]


def _balance(client, headers, member_id):
    return client.get(f"/api/deposits/member/{member_id}", headers=headers).json()["balance"]


class TestOrdererPermissions:
    def test_orderer_creates_locks_finalizes(self, client, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2, 5])
        assert client.post(f"/api/orders/{oid}/lock", headers=orderer["headers"]).status_code == 200
        res = client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"], json={"total_bill": 60})
        assert res.status_code == 200 and res.json()["status"] == "finalized"

    def test_orderer_cannot_delete_or_reopen_finalized(self, client, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"], json={"total_bill": 30})
        assert client.delete(f"/api/orders/{oid}", headers=orderer["headers"]).status_code == 403
        assert client.post(f"/api/orders/{oid}/reopen", headers=orderer["headers"]).status_code == 403

    def test_orderer_cannot_manage_deposits(self, client, orderer, user):
        res = client.post("/api/deposits/charge", headers=orderer["headers"],
                          json={"member_id": 2, "amount": 10})
        assert res.status_code == 403

    def test_plain_user_cannot_create(self, client, user):
        res = client.post("/api/orders", headers=user["headers"], json={"order_date": "2026-07-10"})
        assert res.status_code == 403

    def test_admin_can_assign_orderer_role(self, client, admin, user):
        res = client.put("/api/auth/users/2", headers=admin["headers"], json={"role": "orderer"})
        assert res.status_code == 200 and res.json()["role"] == "orderer"


class TestPayerCredit:
    def test_credit_created_with_note_and_counts_in_balance(self, client, db, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2, 5])
        body = client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                           json={"total_bill": 60, "payer_member_id": 5}).json()
        assert body["payer_member_id"] == 5 and body["payer_amount"] == 60
        assert body["payer_name"] == "Đặt Cơm"

        [credit] = _credits(db, oid)
        assert credit["type"] == "order_payment" and credit["amount"] == 60
        assert credit["note"] == "Đặt cơm ngày 10-07-2026 (Cơm)"
        # paid 60 for the restaurant, ate 30
        assert _balance(client, orderer["headers"], 5) == 30

    def test_custom_amount(self, client, db, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5, "payer_amount": 75})
        assert _credits(db, oid)[0]["amount"] == 75

    def test_admin_payer_gets_no_credit(self, client, db, admin, user):
        oid = _order_with_eaters(client, admin["headers"], [2])
        body = client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"],
                           json={"total_bill": 30, "payer_member_id": None}).json()
        assert body["payer_member_id"] is None and body["payer_amount"] == 0
        assert _credits(db, oid) == []

    def test_refinalize_updates_single_credit(self, client, db, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5})
        # Bill corrected without re-sending payer: amount follows the bill
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"], json={"total_bill": 70})
        [credit] = _credits(db, oid)
        assert credit["amount"] == 70 and credit["member_id"] == 5

    def test_custom_amount_kept_when_bill_edited(self, client, db, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5, "payer_amount": 80})
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"], json={"total_bill": 70})
        assert _credits(db, oid)[0]["amount"] == 80

    def test_change_payer_moves_credit(self, client, db, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5})
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 2})
        [credit] = _credits(db, oid)
        assert credit["member_id"] == 2

    def test_reopen_removes_and_refinalize_restores(self, client, db, admin, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5})
        client.post(f"/api/orders/{oid}/reopen", headers=admin["headers"])
        assert _credits(db, oid) == []
        body = client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"],
                           json={"total_bill": 60}).json()
        assert body["payer_member_id"] == 5
        assert len(_credits(db, oid)) == 1

    def test_delete_order_removes_credit(self, client, db, admin, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                    json={"total_bill": 60, "payer_member_id": 5})
        client.delete(f"/api/orders/{oid}", headers=admin["headers"])
        assert _credits(db, oid) == []

    def test_unknown_payer_404(self, client, orderer, user):
        oid = _order_with_eaters(client, orderer["headers"], [2])
        res = client.post(f"/api/orders/{oid}/finalize", headers=orderer["headers"],
                          json={"total_bill": 60, "payer_member_id": 999})
        assert res.status_code == 404
