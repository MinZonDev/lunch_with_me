"""Withdrawal requests: create, cancel, reject, complete, and their effect on balance."""
import pytest

from tests.conftest import auth_headers, seed_deposit, seed_member, seed_user

BANK = {"bank_code": "VCB", "bank_name": "Vietcombank", "account_number": "0123456789", "account_name": "tran binh"}


@pytest.fixture()
def emails(monkeypatch):
    import app.services.email_service as email_service
    calls = []
    for name in ("send_withdrawal_request", "send_withdrawal_result"):
        monkeypatch.setattr(email_service, name, lambda *a, _n=name, **k: calls.append((_n, a)))
    return calls


@pytest.fixture()
def funded(db, user):
    seed_deposit(db, 1, 2, 100)
    return user


def _request(client, user, amount, **overrides):
    return client.post("/api/withdrawals", headers=user["headers"], json={**BANK, "amount": amount, **overrides})


def _balance(client, user):
    return client.get(f"/api/deposits/member/{user['member_id']}", headers=user["headers"]).json()


class TestCreate:
    def test_partial_request_is_pending_and_emails_admin(self, client, admin, funded, emails):
        res = _request(client, funded, 40)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["status"] == "pending" and body["amount"] == 40
        assert body["account_name"] == "TRAN BINH"
        assert emails[0][0] == "send_withdrawal_request"
        assert emails[0][1][0] == ["admin@test.local"]
        # pending doesn't touch the balance yet
        assert _balance(client, funded)["balance"] == 100

    def test_full_balance_allowed(self, client, funded, emails):
        assert _request(client, funded, 100).status_code == 201

    def test_more_than_balance_rejected(self, client, funded, emails):
        res = _request(client, funded, 101)
        assert res.status_code == 400 and "vượt quá số dư" in res.json()["detail"]

    def test_zero_or_negative_balance_rejected(self, client, user, emails):
        assert _request(client, user, 1).status_code == 400

    def test_only_one_pending(self, client, funded, emails):
        _request(client, funded, 10)
        res = _request(client, funded, 10)
        assert res.status_code == 400 and "chờ duyệt" in res.json()["detail"]

    def test_account_without_member_rejected(self, client, db, emails):
        seed_user(db, 9, "lonely", member_id=None)
        res = client.post("/api/withdrawals", headers=auth_headers(9), json={**BANK, "amount": 1})
        assert res.status_code == 400

    @pytest.mark.parametrize("field,value", [("amount", 0), ("account_number", "12"), ("account_number", "12 34"),
                                             ("account_name", ""), ("bank_code", "")])
    def test_validation(self, client, funded, field, value):
        payload = {**BANK, "amount": 10, field: value}
        assert client.post("/api/withdrawals", headers=funded["headers"], json=payload).status_code == 422


class TestProcess:
    def _pending(self, client, user, amount=40):
        return _request(client, user, amount).json()["id"]

    def test_complete_deducts_balance_and_notifies(self, client, admin, funded, emails):
        wid = self._pending(client, funded)
        res = client.post(f"/api/withdrawals/{wid}/complete", headers=admin["headers"])
        assert res.status_code == 200 and res.json()["status"] == "done"
        assert res.json()["processed_at"] is not None
        b = _balance(client, funded)
        assert b["balance"] == 60 and b["total_withdrawn"] == 40
        assert ("send_withdrawal_result", ("Trần Bình", "binh@test.local", 40, True, None)) in emails
        # shows up in history with running balance
        txn = b["transactions"][0]
        assert txn["type"] == "withdrawal" and txn["running_balance"] == 60

    def test_complete_rechecks_balance(self, client, db, admin, funded, emails):
        wid = self._pending(client, funded, 90)
        seed_deposit(db, 2, 2, 20, dtype="charge")  # balance drops to 80
        res = client.post(f"/api/withdrawals/{wid}/complete", headers=admin["headers"])
        assert res.status_code == 400
        assert _balance(client, funded)["balance"] == 80

    def test_reject_with_reason_keeps_balance(self, client, admin, funded, emails):
        wid = self._pending(client, funded)
        res = client.post(f"/api/withdrawals/{wid}/reject", headers=admin["headers"], json={"reason": "Sai STK"})
        assert res.json()["status"] == "rejected" and res.json()["reject_reason"] == "Sai STK"
        assert _balance(client, funded)["balance"] == 100
        # a new request is allowed again
        assert _request(client, funded, 10).status_code == 201

    def test_user_cancels_own_pending(self, client, funded, emails):
        wid = self._pending(client, funded)
        res = client.post(f"/api/withdrawals/{wid}/cancel", headers=funded["headers"])
        assert res.json()["status"] == "cancelled"

    def test_cannot_cancel_others(self, client, db, funded, emails):
        wid = self._pending(client, funded)
        seed_member(db, 3, "Chi")
        seed_user(db, 3, "chi", member_id=3)
        assert client.post(f"/api/withdrawals/{wid}/cancel", headers=auth_headers(3)).status_code == 403

    def test_cannot_process_twice(self, client, admin, funded, emails):
        wid = self._pending(client, funded)
        client.post(f"/api/withdrawals/{wid}/complete", headers=admin["headers"])
        assert client.post(f"/api/withdrawals/{wid}/complete", headers=admin["headers"]).status_code == 400
        assert client.post(f"/api/withdrawals/{wid}/reject", headers=admin["headers"], json={}).status_code == 400
        assert client.post(f"/api/withdrawals/{wid}/cancel", headers=funded["headers"]).status_code == 400

    def test_only_admin_processes(self, client, funded, emails):
        wid = self._pending(client, funded)
        assert client.post(f"/api/withdrawals/{wid}/complete", headers=funded["headers"]).status_code == 403
        assert client.post(f"/api/withdrawals/{wid}/reject", headers=funded["headers"], json={}).status_code == 403

    def test_deposit_approve_endpoint_refuses_withdrawals(self, client, admin, funded, emails):
        wid = self._pending(client, funded)
        assert client.post(f"/api/deposits/{wid}/approve", headers=admin["headers"]).status_code == 400

    def test_unknown_or_non_withdrawal_404(self, client, admin, funded):
        assert client.post("/api/withdrawals/999/complete", headers=admin["headers"]).status_code == 404
        # deposit id 1 exists but is not a withdrawal
        assert client.post("/api/withdrawals/1/complete", headers=admin["headers"]).status_code == 404


class TestList:
    def test_user_sees_own_admin_sees_all_with_filter(self, client, db, admin, funded, emails):
        seed_member(db, 3, "Chi")
        seed_user(db, 3, "chi", member_id=3)
        seed_deposit(db, 5, 3, 50)
        own = _request(client, funded, 10).json()["id"]
        other_headers = {"headers": auth_headers(3), "member_id": 3}
        other = _request(client, other_headers, 10).json()["id"]
        client.post(f"/api/withdrawals/{other}/complete", headers=admin["headers"])

        mine = client.get("/api/withdrawals", headers=funded["headers"]).json()
        assert [w["id"] for w in mine] == [own]
        everyone = client.get("/api/withdrawals", headers=admin["headers"]).json()
        assert {w["id"] for w in everyone} == {own, other}
        pending = client.get("/api/withdrawals", headers=admin["headers"], params={"status": "pending"}).json()
        assert [w["id"] for w in pending] == [own]
