"""Restaurant menu images: upload/delete via Storage (mocked) and exposure on orders."""
from datetime import datetime, timezone

import pytest

from app.services import storage


@pytest.fixture()
def fake_storage(monkeypatch):
    uploaded, deleted = [], []

    def upload(restaurant_id, data, content_type):
        path = f"menu-images/{restaurant_id}/{len(uploaded)}.{storage.ALLOWED_TYPES[content_type]}"
        uploaded.append((path, data))
        return {"path": path, "url": f"https://cdn.test/{path}"}

    monkeypatch.setattr(storage, "upload_menu_image", upload)
    monkeypatch.setattr(storage, "delete_object", deleted.append)
    return {"uploaded": uploaded, "deleted": deleted}


@pytest.fixture()
def restaurant(db):
    db.collection("restaurants").document("7").set({
        "id": 7, "name": "Cơm Tấm", "link": None, "is_active": True,
        "created_at": datetime.now(timezone.utc),
    })
    return 7


def _png(name="menu.png", size=10):
    return ("files", (name, b"\x89PNG" + b"0" * size, "image/png"))


def _upload(client, headers, rid, *files):
    return client.post(f"/api/restaurants/{rid}/menu-images", headers=headers, files=list(files))


class TestUpload:
    def test_upload_multiple(self, client, admin, restaurant, fake_storage):
        res = _upload(client, admin["headers"], restaurant, _png("a.png"), _png("b.png"))
        assert res.status_code == 200, res.text
        images = res.json()["menu_images"]
        assert [i["path"] for i in images] == ["menu-images/7/0.png", "menu-images/7/1.png"]
        # appended, not replaced
        res = _upload(client, admin["headers"], restaurant, _png("c.png"))
        assert len(res.json()["menu_images"]) == 3

    def test_rejects_non_image_without_uploading_any(self, client, admin, restaurant, fake_storage):
        res = _upload(client, admin["headers"], restaurant, _png(),
                      ("files", ("menu.pdf", b"%PDF", "application/pdf")))
        assert res.status_code == 400
        assert fake_storage["uploaded"] == []

    def test_rejects_oversized(self, client, admin, restaurant, fake_storage):
        res = _upload(client, admin["headers"], restaurant, _png(size=storage.MAX_BYTES))
        assert res.status_code == 400 and "5MB" in res.json()["detail"]

    def test_limit_per_restaurant(self, client, db, admin, restaurant, fake_storage):
        db.collection("restaurants").document("7").update(
            {"menu_images": [{"path": f"p{i}", "url": "u"} for i in range(20)]})
        assert _upload(client, admin["headers"], restaurant, _png()).status_code == 400

    def test_admin_only(self, client, user, restaurant, fake_storage):
        assert _upload(client, user["headers"], restaurant, _png()).status_code == 403

    def test_storage_not_configured_503(self, client, admin, restaurant, monkeypatch):
        monkeypatch.setattr(storage.settings, "storage_bucket", "")
        assert _upload(client, admin["headers"], restaurant, _png()).status_code == 503

    def test_unknown_restaurant_404(self, client, admin, fake_storage):
        assert _upload(client, admin["headers"], 999, _png()).status_code == 404


class TestDelete:
    def test_delete_removes_reference_and_file(self, client, admin, restaurant, fake_storage):
        _upload(client, admin["headers"], restaurant, _png(), _png())
        res = client.delete(f"/api/restaurants/{restaurant}/menu-images", headers=admin["headers"],
                            params={"path": "menu-images/7/0.png"})
        assert [i["path"] for i in res.json()["menu_images"]] == ["menu-images/7/1.png"]
        assert fake_storage["deleted"] == ["menu-images/7/0.png"]

    def test_delete_unknown_path_404(self, client, admin, restaurant, fake_storage):
        res = client.delete(f"/api/restaurants/{restaurant}/menu-images", headers=admin["headers"],
                            params={"path": "nope"})
        assert res.status_code == 404


def test_orders_expose_restaurant_menu_images(client, admin, user, restaurant, fake_storage):
    _upload(client, admin["headers"], restaurant, _png())
    order = client.post("/api/orders", headers=admin["headers"],
                        json={"order_date": "2026-07-10", "restaurant_id": restaurant}).json()
    body = client.get(f"/api/orders/{order['id']}", headers=user["headers"]).json()
    assert body["menu_images"] == [{"path": "menu-images/7/0.png", "url": "https://cdn.test/menu-images/7/0.png"}]
    listed = client.get("/api/restaurants", headers=user["headers"]).json()
    assert listed[0]["menu_images"][0]["path"] == "menu-images/7/0.png"
