from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from app.database import get_db, _next_id, _doc_ns
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserUpdate, UserResponse, ChangePasswordRequest
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
        email=u.email,
        date_of_birth=dob,
        role=u.role,
        is_active=u.is_active,
        member_id=getattr(u, "member_id", None),
        created_at=u.created_at,
    )


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
    if data.email is not None:
        conflict = list(db.collection("users").where("email", "==", data.email).limit(1).stream())
        if conflict and conflict[0].to_dict()["id"] != current_user.id:
            raise HTTPException(status_code=400, detail="Email đã được dùng")
        updates["email"] = data.email
    if data.date_of_birth is not None:
        updates["date_of_birth"] = str(data.date_of_birth)
    if data.member_id is not None:
        updates["member_id"] = data.member_id

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
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
    if data.email is not None:
        conflict = list(db.collection("users").where("email", "==", data.email).limit(1).stream())
        if conflict and conflict[0].to_dict()["id"] != user_id:
            raise HTTPException(status_code=400, detail="Email đã được dùng")
        updates["email"] = data.email
    if data.date_of_birth is not None:
        updates["date_of_birth"] = str(data.date_of_birth)
    if data.member_id is not None:
        updates["member_id"] = data.member_id

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
