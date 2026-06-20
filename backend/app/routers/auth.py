from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from app.database import get_db, _next_id, _doc_ns
from app.schemas import (
    LoginRequest, TokenResponse, UserCreate, UserUpdate, UserResponse,
    ChangePasswordRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.core.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_admin,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(u) -> UserResponse:
    dob = getattr(u, "date_of_birth", None)
    if isinstance(dob, str):
        from datetime import date
        try:
            dob = date.fromisoformat(dob)
        except ValueError:
            dob = None
    return UserResponse(
        id=u.id,
        username=u.username,
        full_name=u.full_name,
        nickname=getattr(u, "nickname", None),
        email=u.email,
        date_of_birth=dob,
        avatar_url=getattr(u, "avatar_url", None),
        role=u.role,
        is_active=u.is_active,
        member_id=getattr(u, "member_id", None),
        created_at=u.created_at,
    )


def _auto_create_member(db, full_name: str) -> int:
    """Create a member entry for a new user and return the member_id."""
    member_id = _next_id(db, "members")
    db.collection("members").document(str(member_id)).set({
        "id": member_id,
        "name": full_name,
        "is_active": True,
        "is_admin": False,
        "created_at": datetime.now(timezone.utc),
    })
    return member_id


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db=Depends(get_db)):
    """Public self-registration. Auto-creates a linked member entry."""
    if list(db.collection("users").where("username", "==", data.username).limit(1).stream()):
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    if list(db.collection("users").where("email", "==", data.email).limit(1).stream()):
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    member_id = _auto_create_member(db, data.full_name)

    user_id = _next_id(db, "users")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": user_id,
        "username": data.username,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "email": data.email,
        "date_of_birth": str(data.date_of_birth) if data.date_of_birth else None,
        "role": "user",
        "is_active": True,
        "member_id": member_id,
        "created_at": now,
    }
    db.collection("users").document(str(user_id)).set(doc_data)

    token = create_access_token({"sub": str(user_id), "role": "user"})
    from app.database import _doc_ns
    user = _doc_ns(db.collection("users").document(str(user_id)).get())
    return TokenResponse(access_token=token, user=_user_response(user))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db=Depends(get_db)):
    results = list(db.collection("users").where("username", "==", data.username).where("is_active", "==", True).limit(1).stream())
    if not results:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai username hoặc mật khẩu")
    user = _doc_ns(results[0])
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai username hoặc mật khẩu")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user=_user_response(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return _user_response(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(data: UserUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
        # Sync member name
        mid = getattr(current_user, "member_id", None)
        if mid:
            db.collection("members").document(str(mid)).update({"name": data.full_name})
    if data.nickname is not None:
        updates["nickname"] = data.nickname
    if data.email is not None:
        conflict = list(db.collection("users").where("email", "==", data.email).limit(1).stream())
        if conflict and conflict[0].to_dict()["id"] != current_user.id:
            raise HTTPException(status_code=400, detail="Email đã được dùng")
        updates["email"] = data.email
    if data.date_of_birth is not None:
        updates["date_of_birth"] = str(data.date_of_birth)
    if data.avatar_url is not None:
        updates["avatar_url"] = data.avatar_url or None

    if updates:
        db.collection("users").document(str(current_user.id)).update(updates)

    doc = db.collection("users").document(str(current_user.id)).get()
    return _user_response(_doc_ns(doc))


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    db.collection("users").document(str(current_user.id)).update({"password_hash": hash_password(data.new_password)})
    return {"message": "Đổi mật khẩu thành công"}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db=Depends(get_db)):
    import secrets
    from datetime import timedelta
    from app.services.email_service import send_reset_password

    results = list(db.collection("users").where("email", "==", data.email).where("is_active", "==", True).limit(1).stream())
    # Always return 200 to avoid email enumeration
    if not results:
        return {"message": "Nếu email tồn tại, link đặt lại mật khẩu sẽ được gửi."}

    user = results[0].to_dict()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    db.collection("password_reset_tokens").document(token).set({
        "token": token,
        "user_id": user["id"],
        "expires_at": expires_at,
        "used": False,
    })

    from app.core.config import settings
    frontend_url = getattr(settings, "frontend_url", "http://localhost:3000")
    reset_url = f"{frontend_url}/reset-password?token={token}"
    send_reset_password(user["full_name"], user["email"], reset_url)

    return {"message": "Nếu email tồn tại, link đặt lại mật khẩu sẽ được gửi."}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db=Depends(get_db)):
    ref = db.collection("password_reset_tokens").document(data.token)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=400, detail="Token không hợp lệ hoặc đã hết hạn")

    token_data = doc.to_dict()
    if token_data.get("used"):
        raise HTTPException(status_code=400, detail="Token đã được sử dụng")

    expires_at = token_data["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Token đã hết hạn (1 giờ)")

    user_id = token_data["user_id"]
    db.collection("users").document(str(user_id)).update({"password_hash": hash_password(data.new_password)})
    ref.update({"used": True})
    return {"message": "Đặt lại mật khẩu thành công. Hãy đăng nhập lại."}


# ---- Admin: manage all users ----

@router.get("/users", response_model=list[UserResponse])
def list_users(db=Depends(get_db), _=Depends(get_current_admin)):
    users = [_doc_ns(s) for s in db.collection("users").stream()]
    users.sort(key=lambda u: u.full_name)
    return [_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db=Depends(get_db), _=Depends(get_current_admin)):
    if list(db.collection("users").where("username", "==", data.username).limit(1).stream()):
        raise HTTPException(status_code=400, detail="Username đã tồn tại")
    if list(db.collection("users").where("email", "==", data.email).limit(1).stream()):
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    user_id = _next_id(db, "users")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": user_id,
        "username": data.username,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "email": data.email,
        "date_of_birth": str(data.date_of_birth) if data.date_of_birth else None,
        "role": data.role,
        "is_active": True,
        "member_id": data.member_id,
        "created_at": now,
    }
    db.collection("users").document(str(user_id)).set(doc_data)
    doc = db.collection("users").document(str(user_id)).get()
    return _user_response(_doc_ns(doc))


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, data: UserUpdate, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("users").document(str(user_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
        mid = doc.to_dict().get("member_id")
        if mid:
            db.collection("members").document(str(mid)).update({"name": data.full_name})
    if data.nickname is not None:
        updates["nickname"] = data.nickname
    if data.email is not None:
        conflict = list(db.collection("users").where("email", "==", data.email).limit(1).stream())
        if conflict and conflict[0].to_dict()["id"] != user_id:
            raise HTTPException(status_code=400, detail="Email đã được dùng")
        updates["email"] = data.email
    if data.date_of_birth is not None:
        updates["date_of_birth"] = str(data.date_of_birth)
    if data.member_id is not None:
        updates["member_id"] = data.member_id
    if data.role is not None:
        updates["role"] = data.role

    if updates:
        ref.update(updates)
    return _user_response(_doc_ns(ref.get()))


@router.delete("/users/{user_id}", status_code=204)
def deactivate_user(user_id: int, db=Depends(get_db), current_admin=Depends(get_current_admin)):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Không thể deactivate chính mình")
    ref = db.collection("users").document(str(user_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    ref.update({"is_active": False})
