"""Random người lấy cơm: auto at deadline, re-roll, emails."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.services import pickup
from tests.conftest import auth_headers, seed_member, seed_user

NOW = datetime(2026, 7, 10, 5, 0, tzinfo=timezone.utc)  # 12:00 VN


@pytest.fixture()
def emails(monkeypatch):
    import app.services.email_service as email_service
    calls = []
    monkeypatch.setattr(email_service, "send_pickup_announcement", lambda **k: calls.append(k))
    return calls


@pytest.fixture()
def team(db, admin):
    for mid, name, username in ((2, "Bình", "binh"), (3, "Chi", "chi"), (4, "Dũng", "dung")):
        seed_member(db, mid, name)
        seed_user(db, mid, username, member_id=mid, full_name=name)
    return [2, 3, 4]


def _order(client, admin, member_ids, pickup_count=1, deadline="11:30"):
    order = client.post("/api/orders", headers=admin["headers"], json={
        "order_date": "2026-07-10", "deadline_time": deadline, "pickup_count": pickup_count,
    }).json()
    for mid in member_ids:
        client.post(f"/api/orders/{order['id']}/items", headers=auth_headers(mid),
                    json={"member_id": mid, "dish_name": "Gà"})
    return order["id"]


def _get(client, admin, oid):
    return client.get(f"/api/orders/{oid}", headers=admin["headers"]).json()


class TestAutoPick:
    def test_picks_after_deadline_and_emails_eaters_only(self, client, db, admin, team, emails):
        oid = _order(client, admin, [2, 3])  # member 4 didn't order
        assert pickup.run_due(db, NOW) == 1

        body = _get(client, admin, oid)
        assert len(body["pickup_member_ids"]) == 1
        assert body["pickup_member_ids"][0] in (2, 3)
        assert body["pickup_names"][0] in ("Bình", "Chi")
        assert body["pickup_picked_at"] is not None

        assert sorted(e["email"] for e in emails) == ["binh@test.local", "chi@test.local"]
        assert sum(e["is_picker"] for e in emails) == 1
        assert all(e["order_date"] == "10/07/2026" for e in emails)

    def test_not_before_deadline(self, client, db, admin, team, emails):
        oid = _order(client, admin, [2, 3], deadline="13:00")
        assert pickup.run_due(db, NOW) == 0
        assert _get(client, admin, oid)["pickup_member_ids"] == []

    def test_runs_once(self, client, db, admin, team, emails):
        _order(client, admin, [2, 3])
        pickup.run_due(db, NOW)
        assert pickup.run_due(db, NOW + timedelta(minutes=1)) == 0
        assert len(emails) == 2

    def test_no_eaters_no_pick(self, client, db, admin, team, emails):
        oid = _order(client, admin, [])
        assert pickup.run_due(db, NOW) == 0
        assert _get(client, admin, oid)["pickup_member_ids"] == []

    def test_count_capped_by_eaters(self, client, db, admin, team, emails):
        oid = _order(client, admin, [2, 3], pickup_count=5)
        pickup.run_due(db, NOW)
        assert sorted(_get(client, admin, oid)["pickup_member_ids"]) == [2, 3]

    def test_multiple_pickers_distinct(self, client, db, admin, team, emails):
        oid = _order(client, admin, [2, 3, 4], pickup_count=2)
        pickup.run_due(db, NOW)
        ids = _get(client, admin, oid)["pickup_member_ids"]
        assert len(ids) == 2 and len(set(ids)) == 2

    def test_other_days_ignored(self, client, db, admin, team, emails):
        _order(client, admin, [2])
        assert pickup.run_due(db, NOW + timedelta(days=1)) == 0

    def test_previous_day_picker_sits_out(self, client, db, admin, team):
        db.collection("daily_orders").document("900").set(
            {"id": 900, "order_date": "2026-07-09", "pickup_member_ids": [2]})
        oid = _order(client, admin, [2, 3, 4])
        ref = db.collection("daily_orders").document(str(oid))
        rng = random.Random(1)
        for _ in range(200):
            assert pickup.pick(db, ref, reroll=True, rng=rng)["pickup_member_ids"][0] != 2

    def test_previous_picker_allowed_when_no_one_else(self, client, db, admin, team):
        db.collection("daily_orders").document("900").set(
            {"id": 900, "order_date": "2026-07-09", "pickup_member_ids": [2]})
        oid = _order(client, admin, [2, 3], pickup_count=2)
        ref = db.collection("daily_orders").document(str(oid))
        assert pickup.pick(db, ref, reroll=True)["pickup_member_ids"] == [2, 3]

    def test_frequent_pickers_less_likely(self, client, db, admin, team):
        # Bình collected twice recently (not yesterday), Chi once, Dũng never.
        for doc_id, day, ids in (("901", "2026-07-03", [2]), ("902", "2026-07-06", [2]),
                                 ("903", "2026-07-07", [3]), ("904", "2026-07-08", [4]),
                                 ("905", "2026-07-09", [4]), ("906", "2026-06-01", [3, 3])):
            db.collection("daily_orders").document(doc_id).set(
                {"id": int(doc_id), "order_date": day, "pickup_member_ids": ids})
        # Dũng picked yesterday -> excluded; weights Bình 1/9, Chi 1/4 (06-01 is outside window).
        oid = _order(client, admin, [2, 3, 4])
        ref = db.collection("daily_orders").document(str(oid))
        rng = random.Random(7)
        counts = {2: 0, 3: 0, 4: 0}
        for _ in range(1300):
            counts[pickup.pick(db, ref, reroll=True, rng=rng)["pickup_member_ids"][0]] += 1
        assert counts[4] == 0
        assert 300 < counts[2] < 500 and 800 < counts[3] < 1000, counts

    def test_uniform_distribution(self, client, db, admin, team):
        oid = _order(client, admin, [2, 3, 4])
        ref = db.collection("daily_orders").document(str(oid))
        rng = random.Random(42)
        counts = {2: 0, 3: 0, 4: 0}
        for _ in range(900):
            counts[pickup.pick(db, ref, reroll=True, rng=rng)["pickup_member_ids"][0]] += 1
        assert all(250 < c < 350 for c in counts.values()), counts


class TestReroll:
    def test_manager_rerolls_with_new_count(self, client, db, admin, team, emails):
        oid = _order(client, admin, [2, 3, 4])
        res = client.post(f"/api/orders/{oid}/pickup", headers=admin["headers"], params={"count": 2})
        assert res.status_code == 200
        assert len(res.json()["pickup_member_ids"]) == 2 and res.json()["pickup_count"] == 2
        assert len(emails) == 3

    def test_plain_user_cannot_reroll(self, client, admin, team, emails):
        oid = _order(client, admin, [2])
        assert client.post(f"/api/orders/{oid}/pickup", headers=auth_headers(2)).status_code == 403

    def test_reroll_without_eaters_400(self, client, admin, team, emails):
        oid = _order(client, admin, [])
        assert client.post(f"/api/orders/{oid}/pickup", headers=admin["headers"]).status_code == 400
