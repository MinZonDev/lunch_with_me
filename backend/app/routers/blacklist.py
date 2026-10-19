"""Blacklist: admin blocks members in debt from ordering until they pay."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.core.auth import get_current_user, get_current_admin
from app.core.config import settings
from app.services import blacklist
from app.services.ledger import compute_balances, member_names

logger = logging.getLogger("lwm.blacklist")

router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])


class BlacklistAdd(BaseModel):
    member_id: int


@router.get("/me")
def my_status(db=Depends(get_db), current_user=Depends(get_current_user)):
    """{blocked, debt} của user hiện tại — frontend dùng để hiện popup nhắc nợ."""
    return blacklist.debt_status(db, getattr(current_user, "member_id", None))


@router.get("")
def list_blacklist(db=Depends(get_db), _=Depends(get_current_admin)):
    """Danh sách đang bị blacklist (đã tự gỡ những người hết nợ)."""
    blacklist.prune(db)
    rows = [s.to_dict() for s in db.collection(blacklist.COLLECTION).stream()]
    if not rows:
        return []
    balances = compute_balances(db)
    names = member_names(db, {r["member_id"] for r in rows})
    result = [{
        "member_id": r["member_id"],
        "name": names.get(r["member_id"], "?"),
        "balance": (balances.get(r["member_id"]) or {}).get("balance", 0),
        "added_at": r.get("added_at"),
    } for r in rows]
    result.sort(key=lambda r: r["balance"])  # nợ nhiều nhất lên đầu
    return result


@router.post("", status_code=201)
def add_to_blacklist(data: BlacklistAdd, db=Depends(get_db), current_user=Depends(get_current_admin)):
    """Thêm người đang nợ vào blacklist và gửi email yêu cầu thanh toán."""
    from app.services.email_service import send_blacklist_notice

    if not db.collection("members").document(str(data.member_id)).get().exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy thành viên")
    b = compute_balances(db, data.member_id).get(data.member_id)
    balance = b["balance"] if b else 0
    if balance >= 0:
        raise HTTPException(status_code=400, detail="Thành viên này không nợ tiền")

    ref = db.collection(blacklist.COLLECTION).document(str(data.member_id))
    if ref.get().exists:
        raise HTTPException(status_code=400, detail="Thành viên này đã ở trong blacklist")
    ref.set({
        "member_id": data.member_id,
        "added_by": current_user.id,
        "added_at": datetime.now(timezone.utc),
    })
    logger.info("Admin %s blacklisted member %d (balance %d)", current_user.id, data.member_id, balance)

    users = list(db.collection("users").where("member_id", "==", data.member_id).limit(1).stream())
    u = users[0].to_dict() if users else {}
    emailed = bool(u.get("email"))
    if emailed:
        send_blacklist_notice(u["full_name"], u["email"], balance, settings.frontend_url)
    return {"member_id": data.member_id, "balance": balance, "emailed": emailed}


@router.delete("/{member_id}", status_code=204)
def remove_from_blacklist(member_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection(blacklist.COLLECTION).document(str(member_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Thành viên không có trong blacklist")
    ref.delete()
    logger.info("Member %d removed from blacklist", member_id)
