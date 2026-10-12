"""API tests for /api/auth: login, OTP registration, approval, password flows."""
from tests.conftest import TEST_PASSWORD, auth_headers, seed_member, seed_user


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


class TestLogin:
    def test_success_returns_token_and_user(self, client, user):
        res = _login(client, "binh", TEST_PASSWORD)
        assert res.status_code == 200
        body = res.json()
        assert body["access_token"]
        assert body["user"]["username"] == "binh"
        assert body["user"]["member_id"] == 2

    def test_wrong_password(self, client, user):
        assert _login(client, "binh", "sai-mat-khau").status_code == 401

    def test_unknown_username(self, client, db):
        assert _login(client, "khong-ton-tai", TEST_PASSWORD).status_code == 401

    def test_pending_account_blocked(self, client, db):
        seed_user(db, 5, "pending", is_active=False, approved=False)
        res = _login(client, "pending", TEST_PASSWORD)
        assert res.status_code == 403
        assert res.json()["detail"] == "PENDING_APPROVAL"

    def test_deactivated_account_blocked(self, client, db):
        seed_user(db, 6, "cu", is_active=False, approved=True)
        res = _login(client, "cu", TEST_PASSWORD)
        assert res.status_code == 403
        assert res.json()["detail"] == "INACTIVE_ACCOUNT"


class TestMe:
    def test_requires_token(self, client, db):
        assert client.get("/api/auth/me").status_code == 401

    def test_returns_current_user(self, client, user):
        res = client.get("/api/auth/me", headers=user["headers"])
        assert res.status_code == 200
        assert res.json()["full_name"] == "Trần Bình"

    def test_rejects_garbage_token(self, client, db):
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert res.status_code == 401


class TestSendOtp:
    def test_stores_code_and_sends_email(self, client, db, sent_emails):
        res = client.post("/api/auth/send-otp", json={"email": "new@test.local"})
        assert res.status_code == 200
        otp = db.collection("otp_tokens").document("new@test.local").get().to_dict()
        assert len(otp["code"]) == 6 and not otp["used"]
        assert [c[0] for c in sent_emails] == ["send_otp_email"]

    def test_rejects_registered_email(self, client, user):
        res = client.post("/api/auth/send-otp", json={"email": "binh@test.local"})
        assert res.status_code == 400

    def test_rate_limited_within_60s(self, client, db):
        assert client.post("/api/auth/send-otp", json={"email": "a@test.local"}).status_code == 200
        assert client.post("/api/auth/send-otp", json={"email": "a@test.local"}).status_code == 429


class TestRegister:
    def _send_otp(self, client, db, email):
        client.post("/api/auth/send-otp", json={"email": email})
        return db.collection("otp_tokens").document(email).get().to_dict()["code"]

    def test_full_flow_register_approve_login(self, client, db, admin):
        code = self._send_otp(client, db, "moi@test.local")
        res = client.post("/api/auth/register", json={
            "username": "nguoimoi", "password": "matkhau6",
            "full_name": "Người Mới", "email": "moi@test.local", "otp_code": code,
        })
        assert res.status_code == 201

        # Blocked until admin approves
        res = _login(client, "nguoimoi", "matkhau6")
        assert res.status_code == 403 and res.json()["detail"] == "PENDING_APPROVAL"

        new_user = next(s.to_dict() for s in db.collection("users").stream()
                        if s.to_dict()["username"] == "nguoimoi")
        # A member was auto-created and linked
        assert new_user["member_id"] is not None
        assert db.collection("members").document(str(new_user["member_id"])).get().exists

        res = client.post(f"/api/auth/users/{new_user['id']}/approve", headers=admin["headers"])
        assert res.status_code == 200

        assert _login(client, "nguoimoi", "matkhau6").status_code == 200

    def test_wrong_otp_rejected(self, client, db):
        code = self._send_otp(client, db, "moi2@test.local")
        wrong = "000000" if code != "000000" else "111111"
        res = client.post("/api/auth/register", json={
            "username": "moi2", "password": "matkhau6",
            "full_name": "Moi Hai", "email": "moi2@test.local", "otp_code": wrong,
        })
        assert res.status_code == 400
        assert not list(db.collection("users").where("username", "==", "moi2").stream())

    def test_otp_marked_used_after_register(self, client, db):
        code = self._send_otp(client, db, "moi3@test.local")
        res = client.post("/api/auth/register", json={
            "username": "moi3", "password": "matkhau6",
            "full_name": "Moi Ba", "email": "moi3@test.local", "otp_code": code,
        })
        assert res.status_code == 201
        assert db.collection("otp_tokens").document("moi3@test.local").get().to_dict()["used"] is True

    def test_used_otp_rejected(self, client, db):
        from datetime import datetime, timedelta, timezone
        db.collection("otp_tokens").document("moi4@test.local").set({
            "email": "moi4@test.local", "code": "123456", "used": True,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "created_at": datetime.now(timezone.utc),
        })
        res = client.post("/api/auth/register", json={
            "username": "moi4", "password": "matkhau6",
            "full_name": "Moi Bốn", "email": "moi4@test.local", "otp_code": "123456",
        })
        assert res.status_code == 400

    def test_duplicate_username_rejected(self, client, user):
        res = client.post("/api/auth/register", json={
            "username": "binh", "password": "matkhau6",
            "full_name": "Binh Gia", "email": "khac@test.local", "otp_code": "123456",
        })
        assert res.status_code == 400


class TestChangePassword:
    def test_wrong_current_password(self, client, user):
        res = client.post("/api/auth/change-password", headers=user["headers"],
                          json={"current_password": "sai", "new_password": "moimoi6"})
        assert res.status_code == 400

    def test_success_then_login_with_new(self, client, user):
        res = client.post("/api/auth/change-password", headers=user["headers"],
                          json={"current_password": TEST_PASSWORD, "new_password": "moimoi6"})
        assert res.status_code == 200
        assert _login(client, "binh", TEST_PASSWORD).status_code == 401
        assert _login(client, "binh", "moimoi6").status_code == 200


class TestPasswordReset:
    def test_unknown_email_still_200_no_token(self, client, db):
        res = client.post("/api/auth/forgot-password", json={"email": "ma@test.local"})
        assert res.status_code == 200  # anti email-enumeration
        assert not list(db.collection("password_reset_tokens").stream())

    def test_full_reset_flow_and_token_single_use(self, client, db, user, sent_emails):
        res = client.post("/api/auth/forgot-password", json={"email": "binh@test.local"})
        assert res.status_code == 200
        assert [c[0] for c in sent_emails] == ["send_reset_password"]

        token = next(iter(db.collection("password_reset_tokens").stream())).to_dict()["token"]
        res = client.post("/api/auth/reset-password",
                          json={"token": token, "new_password": "resetok6"})
        assert res.status_code == 200
        assert _login(client, "binh", "resetok6").status_code == 200

        # Token cannot be replayed
        res = client.post("/api/auth/reset-password",
                          json={"token": token, "new_password": "khac666"})
        assert res.status_code == 400

    def test_invalid_token_rejected(self, client, db):
        res = client.post("/api/auth/reset-password",
                          json={"token": "khong-ton-tai", "new_password": "moimoi6"})
        assert res.status_code == 400


class TestAdminUserManagement:
    def test_list_users_requires_admin(self, client, user):
        assert client.get("/api/auth/users", headers=user["headers"]).status_code == 403

    def test_admin_creates_active_user_with_member(self, client, db, admin):
        res = client.post("/api/auth/users", headers=admin["headers"], json={
            "username": "taymoi", "password": "matkhau6",
            "full_name": "Tây Mới", "email": "taymoi@test.local",
        })
        assert res.status_code == 201
        body = res.json()
        assert body["is_active"] is True
        assert db.collection("members").document(str(body["member_id"])).get().exists

    def test_admin_cannot_deactivate_self(self, client, admin):
        res = client.delete(f"/api/auth/users/{admin['user_id']}", headers=admin["headers"])
        assert res.status_code == 400

    def test_deactivate_then_reactivate(self, client, db, admin, user):
        assert client.delete("/api/auth/users/2", headers=admin["headers"]).status_code == 204
        assert _login(client, "binh", TEST_PASSWORD).status_code == 403
        assert client.post("/api/auth/users/2/reactivate", headers=admin["headers"]).status_code == 200
        assert _login(client, "binh", TEST_PASSWORD).status_code == 200

    def test_reject_pending_user_deletes_user_and_member(self, client, db, admin):
        seed_member(db, 9, "Chờ Duyệt")
        seed_user(db, 9, "choduyet", member_id=9, is_active=False, approved=False)
        res = client.post("/api/auth/users/9/reject", headers=admin["headers"])
        assert res.status_code == 204
        assert not db.collection("users").document("9").get().exists
        assert not db.collection("members").document("9").get().exists

    def test_reject_approved_user_refused(self, client, admin, user):
        res = client.post("/api/auth/users/2/reject", headers=admin["headers"])
        assert res.status_code == 400
