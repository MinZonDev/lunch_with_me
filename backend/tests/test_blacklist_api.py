"""API tests for /api/blacklist: add/remove, ordering lock, auto-unblock on payment."""
from tests.conftest import auth_headers, seed_deposit, seed_member, seed_user
from tests.test_orders_api import _create_order, _item_of


def _blacklist(client, admin, member_id=2):
    return client.post("/api/blacklist", headers=admin["headers"], json={"member_id": member_id})


def _in_debt(db, member_id=2, amount=80):
    seed_deposit(db, 50 + member_id, member_id, amount, dtype="charge")


class TestManageBlacklist:
    def test_add_debtor_sends_email(self, client, db, admin, user, sent_emails):
        _in_debt(db)
        res = _blacklist(client, admin)
        assert res.status_code == 201
        assert res.json() == {"member_id": 2, "balance": -80, "emailed": True}
        name, args, _ = sent_emails[-1]
        assert name == "send_blacklist_notice"
        assert args[:3] == ("Trần Bình", "binh@test.local", -80)

    def test_cannot_add_member_without_debt(self, client, db, admin, user):
        seed_deposit(db, 1, 2, 100)
        assert _blacklist(client, admin).status_code == 400

    def test_cannot_add_twice(self, client, db, admin, user):
        _in_debt(db)
        _blacklist(client, admin)
        assert _blacklist(client, admin).status_code == 400

    def test_requires_admin(self, client, db, user):
        _in_debt(db)
        assert _blacklist(client, user).status_code == 403
        assert client.get("/api/blacklist", headers=user["headers"]).status_code == 403

    def test_list_and_manual_remove(self, client, db, admin, user):
        _in_debt(db)
        _blacklist(client, admin)
        rows = client.get("/api/blacklist", headers=admin["headers"]).json()
        assert [(r["member_id"], r["name"], r["balance"]) for r in rows] == [(2, "Bình", -80)]

        assert client.delete("/api/blacklist/2", headers=admin["headers"]).status_code == 204
        assert client.get("/api/blacklist", headers=admin["headers"]).json() == []
        assert client.get("/api/blacklist/me", headers=user["headers"]).json() == {"blocked": False, "debt": 0}


class TestOrderingLock:
    def test_status_reports_current_debt(self, client, db, admin, user):
        _in_debt(db)
        _blacklist(client, admin)
        seed_deposit(db, 1, 2, 30)  # partial payment
        assert client.get("/api/blacklist/me", headers=user["headers"]).json() == {"blocked": True, "debt": 50}

    def test_blocked_member_cannot_add_change_or_cancel(self, client, db, admin, user):
        order = _create_order(client, admin)
        oid = order["id"]
        client.post(f"/api/orders/{oid}/items", headers=user["headers"],
                    json={"member_id": 2, "dish_name": "Gà chiên"})
        _in_debt(db)
        _blacklist(client, admin)
        item = _item_of(client.get(f"/api/orders/{oid}", headers=user["headers"]).json(), 2)

        assert client.post(f"/api/orders/{oid}/items", headers=user["headers"],
                           json={"member_id": 2, "dish_name": "Bò xào"}).status_code == 403
        assert client.put(f"/api/orders/{oid}/items/{item['id']}", headers=user["headers"],
                          json={"dish_name": "Bò xào"}).status_code == 403
        assert client.delete(f"/api/orders/{oid}/items/{item['id']}", headers=user["headers"]).status_code == 403
        # Dish chosen before blacklisting is kept
        item = _item_of(client.get(f"/api/orders/{oid}", headers=user["headers"]).json(), 2)
        assert item["dish_name"] == "Gà chiên" and item["is_eating"] is True

    def test_delegate_cannot_order_for_blocked_member(self, client, db, admin, user):
        seed_member(db, 3, "Chi")
        seed_user(db, 3, "chi", member_id=3)
        db.collection("delegations").document("1").set({
            "id": 1, "grantor_member_id": 2, "delegate_member_id": 3, "status": "active",
        })
        order = _create_order(client, admin)
        _in_debt(db)
        _blacklist(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=auth_headers(3),
                          json={"member_id": 2, "dish_name": "Bò xào"})
        assert res.status_code == 403

    def test_blocked_member_can_still_order_for_grantor(self, client, db, admin, user):
        seed_member(db, 3, "Chi")
        db.collection("delegations").document("1").set({
            "id": 1, "grantor_member_id": 3, "delegate_member_id": 2, "status": "active",
        })
        order = _create_order(client, admin)
        _in_debt(db)
        _blacklist(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                          json={"member_id": 3, "dish_name": "Bò xào"})
        assert res.status_code == 201

    def test_admin_can_order_for_blocked_member(self, client, db, admin, user):
        order = _create_order(client, admin)
        _in_debt(db)
        _blacklist(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=admin["headers"],
                          json={"member_id": 2, "dish_name": "Cá kho"})
        assert res.status_code == 201


class TestAutoUnblock:
    def test_approved_deposit_that_clears_debt_unblocks(self, client, db, admin, user):
        order = _create_order(client, admin)
        _in_debt(db)
        _blacklist(client, admin)
        seed_deposit(db, 1, 2, 80, status="pending")
        assert client.post("/api/deposits/1/approve", headers=admin["headers"]).status_code == 200

        assert db.collection("blacklist").document("2").get().exists is False
        res = client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                          json={"member_id": 2, "dish_name": "Gà chiên"})
        assert res.status_code == 201

    def test_partial_payment_keeps_block(self, client, db, admin, user):
        _in_debt(db)
        _blacklist(client, admin)
        seed_deposit(db, 1, 2, 30, status="pending")
        client.post("/api/deposits/1/approve", headers=admin["headers"])
        assert client.get("/api/blacklist/me", headers=user["headers"]).json()["blocked"] is True
