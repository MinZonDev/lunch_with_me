import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db, _next_id
from app.schemas import DelegationCreate, DelegationResponse
from app.core.auth import get_current_user
from app.services.delegation import has_active_delegation

logger = logging.getLogger("lwm.delegations")

router = APIRouter(prefix="/api/delegations", tags=["delegations"])


def _member_name(db, member_id: int) -> str:
    doc = db.collection("members").document(str(member_id)).get()
    return doc.to_dict().get("name", "?") if doc.exists else "?"


def _delegation_response(d: dict) -> DelegationResponse:
    return DelegationResponse(
        id=d["id"],
        grantor_member_id=d["grantor_member_id"],
        grantor_name=d.get("grantor_name", "?"),
        delegate_member_id=d["delegate_member_id"],
        delegate_name=d.get("delegate_name", "?"),
        status=d["status"],
        created_at=d["created_at"],
    )


@router.get("", response_model=list[DelegationResponse])
def list_my_delegations(db=Depends(get_db), current_user=Depends(get_current_user)):
    """Trả về ủy quyền liên quan đến user hiện tại (cả 2 chiều)."""
    my_member_id = getattr(current_user, "member_id", None)
    if not my_member_id:
        return []

    seen_ids: set[int] = set()
    results = []

    for snap in db.collection("delegations").where("grantor_member_id", "==", my_member_id).stream():
        d = snap.to_dict()
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            results.append(_delegation_response(d))

    for snap in db.collection("delegations").where("delegate_member_id", "==", my_member_id).stream():
        d = snap.to_dict()
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            results.append(_delegation_response(d))

    logger.info("User %s listed delegations (%d)", current_user.id, len(results))
    return results


@router.post("", response_model=DelegationResponse, status_code=201)
def grant_delegation(data: DelegationCreate, db=Depends(get_db), current_user=Depends(get_current_user)):
    """Tôi ủy quyền cho người khác đặt giùm tôi."""
    my_member_id = getattr(current_user, "member_id", None)
    if not my_member_id:
        raise HTTPException(status_code=400, detail="Tài khoản chưa liên kết với thành viên")

    if data.delegate_member_id == my_member_id:
        raise HTTPException(status_code=400, detail="Không thể ủy quyền cho chính mình")

    delegate_doc = db.collection("members").document(str(data.delegate_member_id)).get()
    if not delegate_doc.exists:
        raise HTTPException(status_code=404, detail="Thành viên không tồn tại")

    # Check duplicate active delegation
    if has_active_delegation(db, my_member_id, data.delegate_member_id):
        raise HTTPException(status_code=409, detail="Ủy quyền đã tồn tại")

    grantor_name = _member_name(db, my_member_id)
    delegate_name = delegate_doc.to_dict().get("name", "?")

    doc_id = _next_id(db, "delegations")
    doc_data = {
        "id": doc_id,
        "grantor_member_id": my_member_id,
        "grantor_name": grantor_name,
        "delegate_member_id": data.delegate_member_id,
        "delegate_name": delegate_name,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
    }
    db.collection("delegations").document(str(doc_id)).set(doc_data)
    logger.info("Member %s granted delegation to member %s", my_member_id, data.delegate_member_id)
    return _delegation_response(doc_data)


@router.delete("/{delegation_id}", status_code=204)
def revoke_delegation(delegation_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    """Thu hồi ủy quyền (chỉ người ủy quyền mới được thu hồi)."""
    my_member_id = getattr(current_user, "member_id", None)

    results = list(
        db.collection("delegations").where("id", "==", delegation_id).limit(1).stream()
    )
    if not results:
        raise HTTPException(status_code=404, detail="Không tìm thấy ủy quyền")

    d = results[0].to_dict()
    if d["grantor_member_id"] != my_member_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ người ủy quyền mới được thu hồi")

    results[0].reference.update({"status": "revoked"})
    logger.info("Delegation %d revoked by user %s", delegation_id, current_user.id)
