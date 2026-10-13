"""Random món: settings on create, dish list sources (Be / restaurant / order), permissions."""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import app.routers.be_menu as be_menu
from tests.conftest import auth_headers, seed_member, seed_user

DISHES = [{"name": "Cơm gà xối mỡ", "price": 35}, {"name": "  Canh chua  ", "price": 15.5}]


def _restaurant(db, rid, name, **extra):
    db.collection("restaurants").document(str(rid)).set({
        "id": rid, "name": name, "is_active": True, "created_at": datetime.now(timezone.utc), **extra})


def _create(client, headers, **payload):
    res = client.post("/api/orders", headers=headers, json={"order_date": "2026-07-10", **payload})
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture()
def be_ok(monkeypatch):
    calls = []

    def fake(r):
        calls.append(r["be_restaurant_id"])
        return {"restaurant_name": r["name"], "items": [
            {"name": "Bún bò", "price": 45000, "category": "Bún", "image": "https://img/x.jpg"},
            {"name": "Cơm tấm", "price": 40500, "category": "Cơm", "image": ""},
        ]}
    monkeypatch.setattr(be_menu, "fetch_be_menu", fake)
    return calls


class TestCreate:
    def test_dishes_saved_on_restaurant_for_reuse(self, client, db, admin, user):
        _restaurant(db, 3, "Cơm Chay")
        order = _create(client, admin["headers"], restaurant_id=3, allow_random=True, dishes=DISHES)
        assert order["allow_random"] is True
        saved = db.collection("restaurants").document("3").get().to_dict()["dishes"]
        assert saved == [{"name": "Cơm gà xối mỡ", "price": 35.0}, {"name": "Canh chua", "price": 15.5}]
        # next menu at the same restaurant reuses the list without re-entering it
        nxt = _create(client, admin["headers"], restaurant_id=3, allow_random=True)
        body = client.get(f"/api/orders/{nxt['id']}/dishes", headers=user["headers"]).json()
        assert body["source"] == "restaurant" and [d["name"] for d in body["items"]] == ["Cơm gà xối mỡ", "Canh chua"]
        # and the restaurant listing exposes it for prefill
        listed = client.get("/api/restaurants", headers=user["headers"]).json()
        assert listed[0]["dishes"][0]["name"] == "Cơm gà xối mỡ"

    def test_dishes_on_order_without_restaurant(self, client, db, admin, user):
        order = _create(client, admin["headers"], allow_random=True, dishes=DISHES[:1])
        body = client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"]).json()
        assert body == {"source": "order", "items": [
            {"name": "Cơm gà xối mỡ", "price": 35.0, "category": None, "image": None}]}

    def test_random_off_by_default(self, client, admin, user):
        order = _create(client, admin["headers"])
        assert order["allow_random"] is False
        res = client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"])
        assert res.status_code == 400

    @pytest.mark.parametrize("bad", [[{"name": "   ", "price": 10}], [{"name": "X", "price": -1}],
                                     [{"name": "X" * 101, "price": 1}]])
    def test_validation(self, client, admin, bad):
        res = client.post("/api/orders", headers=admin["headers"],
                          json={"order_date": "2026-07-10", "allow_random": True, "dishes": bad})
        assert res.status_code == 422


class TestSources:
    def test_be_menu_preferred_and_price_in_k(self, client, db, admin, user, be_ok):
        _restaurant(db, 2, "Cam Ranh", be_restaurant_id="51148", dishes=DISHES)
        order = _create(client, admin["headers"], restaurant_id=2, allow_random=True)
        body = client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"]).json()
        assert body["source"] == "be"
        assert body["items"][0] == {"name": "Bún bò", "price": 45.0, "category": "Bún", "image": "https://img/x.jpg"}
        assert body["items"][1]["price"] == 40.5 and body["items"][1]["image"] is None

    def test_falls_back_to_manual_list_when_be_down(self, client, db, admin, user, monkeypatch):
        def down(r):
            raise HTTPException(status_code=502, detail="Không thể lấy menu từ Be")
        monkeypatch.setattr(be_menu, "fetch_be_menu", down)
        _restaurant(db, 2, "Cam Ranh", be_restaurant_id="51148", dishes=DISHES)
        order = _create(client, admin["headers"], restaurant_id=2, allow_random=True)
        body = client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"]).json()
        assert body["source"] == "restaurant"

    def test_be_down_and_no_list_502(self, client, db, admin, user, monkeypatch):
        def down(r):
            raise HTTPException(status_code=502, detail="Không thể lấy menu từ Be")
        monkeypatch.setattr(be_menu, "fetch_be_menu", down)
        _restaurant(db, 2, "Cam Ranh", be_restaurant_id="51148")
        order = _create(client, admin["headers"], restaurant_id=2, allow_random=True)
        assert client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"]).status_code == 502

    def test_no_list_yet(self, client, db, admin, user):
        _restaurant(db, 6, "Bicago")
        order = _create(client, admin["headers"], restaurant_id=6, allow_random=True)
        body = client.get(f"/api/orders/{order['id']}/dishes", headers=user["headers"]).json()
        assert body == {"source": "none", "items": []}


class TestSettings:
    def test_orderer_toggles_and_edits_list(self, client, db, admin, user):
        seed_member(db, 5, "Đặt Cơm")
        seed_user(db, 5, "orderer", role="orderer", member_id=5)
        orderer = auth_headers(5, "orderer")
        _restaurant(db, 6, "Bicago")
        order = _create(client, orderer, restaurant_id=6)
        res = client.put(f"/api/orders/{order['id']}/random", headers=orderer,
                         json={"allow_random": True, "dishes": [{"name": "Burger", "price": 59}]})
        assert res.status_code == 200 and res.json()["allow_random"] is True
        assert db.collection("restaurants").document("6").get().to_dict()["dishes"] == [{"name": "Burger", "price": 59.0}]
        # toggling off keeps the list
        client.put(f"/api/orders/{order['id']}/random", headers=orderer, json={"allow_random": False})
        assert db.collection("restaurants").document("6").get().to_dict()["dishes"]

    def test_plain_user_cannot_change(self, client, admin, user):
        order = _create(client, admin["headers"])
        res = client.put(f"/api/orders/{order['id']}/random", headers=user["headers"], json={"allow_random": True})
        assert res.status_code == 403
