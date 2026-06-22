from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from app.database import get_db, _next_id, _to_ns, _doc_ns
from app.schemas import MemberCreate, MemberUpdate, MemberResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/members", tags=["members"])


def _build_member_username_map(db) -> dict:
    """Return {member_id: username} from users collection."""
    result = {}
    for snap in db.collection("users").stream():
        u = snap.to_dict()
        mid = u.get("member_id")
        uname = u.get("username")
        if mid and uname:
            result[mid] = uname
    return result


def _member_response(ns, username: str | None = None) -> MemberResponse:
    return MemberResponse(
        id=ns.id,
        name=ns.name,
        is_active=ns.is_active,
        is_admin=getattr(ns, "is_admin", False),
        username=username,
        created_at=ns.created_at,
    )


@router.get("/public", response_model=list[MemberResponse])
def list_members_public(db=Depends(get_db)):
    """Public endpoint: list active members for registration form (no auth required)."""
    members = [_to_ns(s.to_dict()) for s in db.collection("members").where("is_active", "==", True).stream()]
    members.sort(key=lambda m: m.name)
    return [_member_response(m) for m in members]


@router.get("", response_model=list[MemberResponse])
def list_members(active_only: bool = True, db=Depends(get_db), _=Depends(get_current_user)):
    col = db.collection("members")
    if active_only:
        stream = col.where("is_active", "==", True).stream()
    else:
        stream = col.stream()
    members = [_to_ns(s.to_dict()) for s in stream]
    members.sort(key=lambda m: m.name)
    umap = _build_member_username_map(db)
    return [_member_response(m, umap.get(m.id)) for m in members]


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(member_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    doc = db.collection("members").document(str(member_id)).get()
    m = _doc_ns(doc)
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    umap = _build_member_username_map(db)
    return _member_response(m, umap.get(member_id))


@router.post("", response_model=MemberResponse, status_code=201)
def create_member(data: MemberCreate, db=Depends(get_db), _=Depends(get_current_admin)):
    existing = list(db.collection("members").where("name", "==", data.name).limit(1).stream())
    if existing:
        raise HTTPException(status_code=400, detail="Member with this name already exists")

    new_id = _next_id(db, "members")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": new_id,
        "name": data.name,
        "is_active": True,
        "is_admin": data.is_admin,
        "created_at": now,
    }
    db.collection("members").document(str(new_id)).set(doc_data)
    return _member_response(_to_ns(doc_data))


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(member_id: int, data: MemberUpdate, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("members").document(str(member_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Member not found")

    updates = {}
    if data.name is not None:
        conflict = list(db.collection("members").where("name", "==", data.name).limit(1).stream())
        if conflict and conflict[0].to_dict()["id"] != member_id:
            raise HTTPException(status_code=400, detail="Name already taken")
        updates["name"] = data.name
    if data.is_active is not None:
        updates["is_active"] = data.is_active
    if data.is_admin is not None:
        updates["is_admin"] = data.is_admin

    if updates:
        ref.update(updates)

    return _member_response(_to_ns({**doc.to_dict(), **updates}))


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("members").document(str(member_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Member not found")
    ref.update({"is_active": False})
