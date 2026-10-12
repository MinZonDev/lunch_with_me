"""API tests for /api/orders and /api/orders/{id}/items: lifecycle, permissions, bill split."""
from datetime import datetime, timezone

from tests.conftest import seed_member


def _create_order(client, admin, **overrides):
    payload = {"order_date": "2026-07-10", "name": "Cơm trưa", **overrides}
    res = client.post("/api/orders", json=payload, headers=admin["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def _item_of(order_body, member_id):
    return next(i for i in order_body["items"] if i["member_id"] == member_id)


class TestCreateOrder:
    def test_requires_admin(self, client, user):
        res = client.post("/api/orders", json={"order_date": "2026-07-10"}, headers=user["headers"])
        assert res.status_code == 403

    def test_autocreates_items_for_active_members_only(self, client, db, admin, user):
        seed_member(db, 3, "Chi")
        seed_member(db, 4, "Nghỉ Việc", is_active=False)
        order = _create_order(client, admin)
        assert {i["member_id"] for i in order["items"]} == {1, 2, 3}
        assert all(i["is_eating"] is False for i in order["items"])
        assert order["status"] == "open"
        assert order["eater_count"] == 0

    def test_deadline_converted_from_vn_time(self, client, admin):
        order = _create_order(client, admin, deadline_time="11:30")
        # 11:30 VN (UTC+7) → 04:30 UTC
        assert order["order_deadline"].startswith("2026-07-10T04:30")


class TestChooseDish:
    def test_member_picks_own_dish(self, client, admin, user):
        order = _create_order(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                          json={"member_id": 2, "dish_name": "Gà chiên mắm"})
        assert res.status_code == 201
        body = res.json()
        assert body["is_eating"] is True and body["dish_name"] == "Gà chiên mắm"

    def test_cannot_pick_for_other_member(self, client, admin, user):
        order = _create_order(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                          json={"member_id": 1, "dish_name": "Bò xào"})
        assert res.status_code == 403

    def test_delegation_allows_picking_for_grantor(self, client, db, admin, user):
        db.collection("delegations").document("1").set({
            "id": 1, "grantor_member_id": 1, "delegate_member_id": 2, "status": "active",
        })
        order = _create_order(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                          json={"member_id": 1, "dish_name": "Bò xào"})
        assert res.status_code == 201

    def test_admin_can_pick_for_anyone(self, client, admin, user):
        order = _create_order(client, admin)
        res = client.post(f"/api/orders/{order['id']}/items", headers=admin["headers"],
                          json={"member_id": 2, "dish_name": "Cá kho"})
        assert res.status_code == 201

    def test_cancel_item_resets_choice(self, client, admin, user):
        order = _create_order(client, admin)
        client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                    json={"member_id": 2, "dish_name": "Gà chiên"})
        item = _item_of(client.get(f"/api/orders/{order['id']}", headers=user["headers"]).json(), 2)
        res = client.delete(f"/api/orders/{order['id']}/items/{item['id']}", headers=user["headers"])
        assert res.status_code == 204
        item = _item_of(client.get(f"/api/orders/{order['id']}", headers=user["headers"]).json(), 2)
        assert item["is_eating"] is False and item["dish_name"] is None


class TestLockAndFinalize:
    def test_lock_then_reopen(self, client, admin):
        order = _create_order(client, admin)
        assert client.post(f"/api/orders/{order['id']}/lock",
                           headers=admin["headers"]).json()["status"] == "locked"
        assert client.post(f"/api/orders/{order['id']}/reopen",
                           headers=admin["headers"]).json()["status"] == "open"

    def test_finalize_requires_admin(self, client, admin, user):
        order = _create_order(client, admin)
        res = client.post(f"/api/orders/{order['id']}/finalize",
                          json={"total_bill": 100}, headers=user["headers"])
        assert res.status_code == 403

    def test_finalize_splits_bill_with_extras(self, client, db, admin, user):
        """bill=105, eaters=[m1 extra 0, m2 extra 10] → shared=95, base=ceil(95/2)=48."""
        seed_member(db, 3, "Chi")  # member 3 does not eat
        order = _create_order(client, admin)
        oid = order["id"]
        client.post(f"/api/orders/{oid}/items", headers=admin["headers"],
                    json={"member_id": 1, "dish_name": "Bò xào"})
        client.post(f"/api/orders/{oid}/items", headers=admin["headers"],
                    json={"member_id": 2, "dish_name": "Gà chiên"})
        item2 = _item_of(client.get(f"/api/orders/{oid}", headers=admin["headers"]).json(), 2)
        res = client.put(f"/api/orders/{oid}/items/{item2['id']}/extra", headers=admin["headers"],
                         json={"extra_item_description": "Trà đào", "extra_item_cost": 10})
        assert res.status_code == 200

        res = client.post(f"/api/orders/{oid}/finalize", json={"total_bill": 105},
                          headers=admin["headers"])
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "finalized"
        assert body["shared_cost_per_person"] == 48
        assert _item_of(body, 1)["total_cost"] == 48
        assert _item_of(body, 2)["total_cost"] == 58
        assert _item_of(body, 3)["total_cost"] == 0

    def test_lock_after_finalize_refused(self, client, admin):
        order = _create_order(client, admin)
        client.post(f"/api/orders/{order['id']}/finalize", json={"total_bill": 0},
                    headers=admin["headers"])
        res = client.post(f"/api/orders/{order['id']}/lock", headers=admin["headers"])
        assert res.status_code == 400

    def test_no_modification_after_finalize(self, client, admin, user):
        order = _create_order(client, admin)
        oid = order["id"]
        client.post(f"/api/orders/{oid}/items", headers=user["headers"],
                    json={"member_id": 2, "dish_name": "Gà chiên"})
        item = _item_of(client.get(f"/api/orders/{oid}", headers=user["headers"]).json(), 2)
        client.post(f"/api/orders/{oid}/finalize", json={"total_bill": 50}, headers=admin["headers"])

        assert client.post(f"/api/orders/{oid}/items", headers=user["headers"],
                           json={"member_id": 2, "dish_name": "Khác"}).status_code == 400
        assert client.put(f"/api/orders/{oid}/items/{item['id']}", headers=user["headers"],
                          json={"dish_name": "Khác"}).status_code == 400
        assert client.delete(f"/api/orders/{oid}/items/{item['id']}",
                             headers=user["headers"]).status_code == 400


class TestOrderCrud:
    def test_get_missing_order_404(self, client, user):
        assert client.get("/api/orders/999", headers=user["headers"]).status_code == 404

    def test_admin_updates_bill_and_name(self, client, admin):
        order = _create_order(client, admin)
        res = client.put(f"/api/orders/{order['id']}", headers=admin["headers"],
                         json={"total_bill": 250, "name": "Bún chả"})
        assert res.status_code == 200
        body = res.json()
        assert body["total_bill"] == 250 and body["name"] == "Bún chả"

    def test_delete_order_removes_items(self, client, db, admin, user):
        order = _create_order(client, admin)
        oid = order["id"]
        assert client.delete(f"/api/orders/{oid}", headers=admin["headers"]).status_code == 204
        assert client.get(f"/api/orders/{oid}", headers=admin["headers"]).status_code == 404
        leftovers = list(db.collection("order_items").where("daily_order_id", "==", oid).stream())
        assert leftovers == []

    def test_list_orders_reports_eater_count(self, client, admin, user):
        order = _create_order(client, admin)
        client.post(f"/api/orders/{order['id']}/items", headers=user["headers"],
                    json={"member_id": 2, "dish_name": "Gà chiên"})
        res = client.get("/api/orders", headers=user["headers"])
        assert res.status_code == 200
        listed = next(o for o in res.json() if o["id"] == order["id"])
        assert listed["eater_count"] == 1

    def test_update_links_replaces_list(self, client, admin):
        order = _create_order(client, admin)
        res = client.put(f"/api/orders/{order['id']}/links", headers=admin["headers"],
                         json={"links": [{"label": "Quán A", "url": "https://a.example"}]})
        assert res.status_code == 200
        assert res.json()["links"] == [{"label": "Quán A", "url": "https://a.example"}]


class TestExceptionItems:
    def _setup(self, client, db, admin, user):
        seed_member(db, 3, "Chi")
        order = _create_order(client, admin)
        oid = order["id"]
        for mid, dish in ((1, "Gà"), (2, "Bò"), (3, "Cơm trắng")):
            client.post(f"/api/orders/{oid}/items", headers=admin["headers"],
                        json={"member_id": mid, "dish_name": dish})
        body = client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()
        return oid, _item_of(body, 3)["id"]

    def test_exception_before_finalize(self, client, db, admin, user):
        oid, item_id = self._setup(client, db, admin, user)
        res = client.put(f"/api/orders/{oid}/items/{item_id}/exception", headers=admin["headers"],
                         json={"is_exception": True, "exception_amount": 3})
        assert res.status_code == 200
        assert res.json()["is_exception"] is True and res.json()["exception_amount"] == 3

        body = client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"],
                           json={"total_bill": 103}).json()
        assert {i["member_id"]: i["total_cost"] for i in body["items"]} == {1: 50, 2: 50, 3: 3}
        assert body["shared_cost_per_person"] == 50

    def test_exception_after_finalize_resplits(self, client, db, admin, user):
        oid, item_id = self._setup(client, db, admin, user)
        client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"], json={"total_bill": 90})
        client.put(f"/api/orders/{oid}/items/{item_id}/exception", headers=admin["headers"],
                   json={"is_exception": True, "exception_amount": 4})
        body = client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()
        assert {i["member_id"]: i["total_cost"] for i in body["items"]} == {1: 43, 2: 43, 3: 4}

        # Bỏ ngoại lệ → chia đều lại
        client.put(f"/api/orders/{oid}/items/{item_id}/exception", headers=admin["headers"],
                   json={"is_exception": False})
        body = client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()
        assert {i["member_id"]: i["total_cost"] for i in body["items"]} == {1: 30, 2: 30, 3: 30}
        assert _item_of(body, 3)["exception_amount"] == 0

    def test_exception_exceeding_bill_rejected_and_rolled_back(self, client, db, admin, user):
        oid, item_id = self._setup(client, db, admin, user)
        client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"], json={"total_bill": 90})
        res = client.put(f"/api/orders/{oid}/items/{item_id}/exception", headers=admin["headers"],
                         json={"is_exception": True, "exception_amount": 200})
        assert res.status_code == 400
        body = client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()
        assert _item_of(body, 3)["is_exception"] is False

    def test_exception_requires_admin(self, client, db, admin, user):
        oid, item_id = self._setup(client, db, admin, user)
        res = client.put(f"/api/orders/{oid}/items/{item_id}/exception", headers=user["headers"],
                         json={"is_exception": True, "exception_amount": 3})
        assert res.status_code == 403

    def test_extra_after_finalize_resplits_server_side(self, client, db, admin, user):
        oid, item_id = self._setup(client, db, admin, user)
        client.post(f"/api/orders/{oid}/finalize", headers=admin["headers"], json={"total_bill": 90})
        client.put(f"/api/orders/{oid}/items/{item_id}/extra", headers=admin["headers"],
                   json={"extra_item_description": "Trà", "extra_item_cost": 6})
        body = client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()
        assert {i["member_id"]: i["total_cost"] for i in body["items"]} == {1: 28, 2: 28, 3: 34}
