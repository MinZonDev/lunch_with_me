"""Withdrawals: a member asks to take money out of their deposit balance.

Flow: user creates a request (pending) → admins get an email → admin transfers
the money (VietQR shown in the UI) and marks it done, which is when it starts
counting against the balance. Pending requests can be cancelled by the owner
or rejected by an admin. Rows live in the deposits collection
(type="withdrawal") so they show up in the member's transaction history, and
are never deleted on cancel/reject — only their status changes.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.auth import get_current_admin, get_current_user
from app.core.config import settings
from app.database import _next_id, get_db
from app.schemas import WithdrawalCreate, WithdrawalReject, WithdrawalResponse
from app.services.ledger import compute_balances, member_names

logger = logging.getLogger("lwm.withdrawals")

router = APIRouter(prefix="/api/withdrawals", tags=["withdrawals"])


def _response(d: dict, name: str) -> WithdrawalResponse:
    return WithdrawalResponse(
        id=d["id"],
        member_id=d["member_id"],
        member_name=name,
        amount=d["amount"],
        bank_code=d.get("bank_code", ""),
        bank_name=d.get("bank_name", ""),
        account_number=d.get("account_number", ""),
        account_name=d.get("account_name", ""),
        status=d["status"],
        reject_reason=d.get("reject_reason"),
        created_at=d["created_at"],
        processed_at=d.get("processed_at"),
    )


def _balance(db, member_id: int) -> int:
    b = compute_balances(db, member_id).get(member_id)
    return b["balance"] if b else 0


def _pending_for(db, member_id: int) -> list[dict]:
    return [s.to_dict() for s in db.collection("deposits")
            .where("member_id", "==", member_id)
            .where("type", "==", "withdrawal")
            .where("status", "==", "pending").stream()]


def _load(db, withdrawal_id: int):
    ref = db.collection("deposits").document(str(withdrawal_id))
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("type") != "withdrawal":
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền")
    return ref, doc.to_dict()


def _require_pending(d: dict) -> None:
    if d["status"] != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu này đã được xử lý")


def _user_for_member(db, member_id: int) -> dict | None:
    users = [s.to_dict() for s in db.collection("users")
             .where("member_id", "==", member_id).where("is_active", "==", True).limit(1).stream()]
    return users[0] if users else None


def _notify_admins(db, d: dict, member_name: str) -> None:
    from app.services.email_service import send_withdrawal_request

    admin_emails = [u["email"] for u in (s.to_dict() for s in db.collection("users")
                                         .where("role", "==", "admin").where("is_active", "==", True).stream())
                    if u.get("email")]
    send_withdrawal_request(admin_emails, member_name, d["amount"], d["bank_name"],
                            d["account_number"], d["account_name"], settings.frontend_url)


def _notify_member(db, d: dict, done: bool) -> None:
    from app.services.email_service import send_withdrawal_result

    user = _user_for_member(db, d["member_id"])
    if user and user.get("email"):
        send_withdrawal_result(user.get("full_name", ""), user["email"], d["amount"], done, d.get("reject_reason"))


@router.get("", response_model=list[WithdrawalResponse])
def list_withdrawals(
    status: str | None = Query(default=None, pattern="^(pending|done|rejected|cancelled)$"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Admin: everyone's requests. User: only their own."""
    q = db.collection("deposits").where("type", "==", "withdrawal")
    if current_user.role != "admin":
        mid = getattr(current_user, "member_id", None)
        if not mid:
            return []
        q = q.where("member_id", "==", mid)
    if status:
        q = q.where("status", "==", status)
    rows = sorted((s.to_dict() for s in q.stream()), key=lambda d: d["created_at"], reverse=True)
    names = member_names(db, {d["member_id"] for d in rows})
    return [_response(d, names.get(d["member_id"], "?")) for d in rows]


@router.post("", response_model=WithdrawalResponse, status_code=201)
def create_withdrawal(
    data: WithdrawalCreate,
    background: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    mid = getattr(current_user, "member_id", None)
    if not mid:
        raise HTTPException(status_code=400, detail="Tài khoản chưa liên kết thành viên nên không có số dư để rút")
    if _pending_for(db, mid):
        raise HTTPException(status_code=400, detail="Bạn đang có một yêu cầu rút tiền chờ duyệt")

    balance = _balance(db, mid)
    if balance <= 0:
        raise HTTPException(status_code=400, detail="Số dư không đủ để rút")
    if data.amount > balance:
        raise HTTPException(status_code=400, detail=f"Số tiền rút vượt quá số dư ({balance}k)")

    wid = _next_id(db, "deposits")
    d = {
        "id": wid,
        "member_id": mid,
        "amount": data.amount,
        "type": "withdrawal",
        "status": "pending",
        "bank_code": data.bank_code.strip(),
        "bank_name": data.bank_name.strip(),
        "account_number": data.account_number.strip(),
        "account_name": data.account_name.strip().upper(),
        "note": f"Rút tiền về {data.bank_name.strip()}",
        "requested_by": current_user.id,
        "created_at": datetime.now(timezone.utc),
    }
    db.collection("deposits").document(str(wid)).set(d)
    logger.info("Member %s requested withdrawal %s (%sk)", mid, wid, data.amount)

    name = member_names(db, [mid]).get(mid, "?")
    background.add_task(_notify_admins, db, d, name)
    return _response(d, name)


@router.post("/{withdrawal_id}/cancel", response_model=WithdrawalResponse)
def cancel_withdrawal(withdrawal_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    ref, d = _load(db, withdrawal_id)
    if d["member_id"] != getattr(current_user, "member_id", None):
        raise HTTPException(status_code=403, detail="Chỉ người tạo yêu cầu được huỷ")
    _require_pending(d)
    updates = {"status": "cancelled", "processed_at": datetime.now(timezone.utc)}
    ref.update(updates)
    d.update(updates)
    return _response(d, member_names(db, [d["member_id"]]).get(d["member_id"], "?"))


@router.post("/{withdrawal_id}/reject", response_model=WithdrawalResponse)
def reject_withdrawal(
    withdrawal_id: int,
    data: WithdrawalReject,
    background: BackgroundTasks,
    db=Depends(get_db),
    admin=Depends(get_current_admin),
):
    ref, d = _load(db, withdrawal_id)
    _require_pending(d)
    updates = {
        "status": "rejected",
        "reject_reason": (data.reason or "").strip() or None,
        "processed_at": datetime.now(timezone.utc),
        "processed_by": admin.id,
    }
    ref.update(updates)
    d.update(updates)
    background.add_task(_notify_member, db, d, False)
    return _response(d, member_names(db, [d["member_id"]]).get(d["member_id"], "?"))


@router.post("/{withdrawal_id}/complete", response_model=WithdrawalResponse)
def complete_withdrawal(
    withdrawal_id: int,
    background: BackgroundTasks,
    db=Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Admin confirms the transfer went through: the amount now leaves the balance."""
    ref, d = _load(db, withdrawal_id)
    _require_pending(d)
    # Balance may have dropped since the request (meals finalized, charges added)
    balance = _balance(db, d["member_id"])
    if d["amount"] > balance:
        raise HTTPException(
            status_code=400,
            detail=f"Số dư hiện tại ({balance}k) không đủ cho yêu cầu {d['amount']}k. Hãy từ chối để người dùng tạo lại.",
        )
    updates = {"status": "done", "processed_at": datetime.now(timezone.utc), "processed_by": admin.id}
    ref.update(updates)
    d.update(updates)
    logger.info("Admin %s completed withdrawal %s", admin.id, withdrawal_id)
    background.add_task(_notify_member, db, d, True)
    return _response(d, member_names(db, [d["member_id"]]).get(d["member_id"], "?"))
