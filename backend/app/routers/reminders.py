"""Debt reminder: manual send + auto-schedule config."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.core.auth import get_current_admin
from app.core.config import settings

router = APIRouter(prefix="/api/reminders", tags=["reminders"])

_SETTINGS_DOC = "_settings/debt_reminder"


class ReminderSettings(BaseModel):
    enabled: bool = False
    schedule: str = "weekly"      # daily | weekly | biweekly
    day_of_week: str = "mon"      # mon tue wed thu fri sat sun (weekly/biweekly)
    time: str = "09:00"           # HH:MM VN time


class SendReminderRequest(BaseModel):
    member_id: Optional[int] = None   # None = gửi tất cả người nợ


def _compute_balances(db):
    """Return list of {member_id, name, email, balance} for all active users with member link."""
    all_txns = [s.to_dict() for s in db.collection("deposits").stream()]
    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    finalized_ids = {
        s.to_dict()["id"]
        for s in db.collection("daily_orders").where("status", "==", "finalized").stream()
    }
    users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]

    result = []
    for u in users:
        mid = u.get("member_id")
        if not mid:
            continue
        my_txns = [t for t in all_txns if t["member_id"] == mid]
        deposited = sum(t["amount"] for t in my_txns if t.get("type", "deposit") == "deposit" and t.get("status") == "approved")
        charged = sum(t["amount"] for t in my_txns if t.get("type") == "charge")
        spent = sum(i.get("total_cost", 0) or 0 for i in all_items if i["member_id"] == mid and i["daily_order_id"] in finalized_ids)
        result.append({
            "member_id": mid,
            "user_id": u["id"],
            "name": u.get("nickname") or u["full_name"],
            "full_name": u["full_name"],
            "email": u.get("email", ""),
            "balance": deposited - charged - spent,
        })
    return result


@router.get("/debtors")
def list_debtors(db=Depends(get_db), _=Depends(get_current_admin)):
    """Danh sách thành viên đang nợ (balance < 0)."""
    balances = _compute_balances(db)
    debtors = [b for b in balances if b["balance"] < 0]
    debtors.sort(key=lambda b: b["balance"])  # nợ nhiều nhất lên đầu
    return debtors


@router.post("/send")
def send_reminder(data: SendReminderRequest, db=Depends(get_db), _=Depends(get_current_admin)):
    """Gửi nhắc nợ — 1 người hoặc hàng loạt (người nợ)."""
    from app.services.email_service import send_debt_reminder

    balances = _compute_balances(db)

    if data.member_id is not None:
        targets = [b for b in balances if b["member_id"] == data.member_id]
        if not targets:
            raise HTTPException(status_code=404, detail="Không tìm thấy thành viên")
    else:
        targets = [b for b in balances if b["balance"] < 0]

    sent, skipped = 0, 0
    for t in targets:
        if not t["email"]:
            skipped += 1
            continue
        send_debt_reminder(t["full_name"], t["email"], t["balance"], settings.frontend_url)
        sent += 1

    return {"sent": sent, "skipped_no_email": skipped}


@router.get("/settings", response_model=ReminderSettings)
def get_settings(db=Depends(get_db), _=Depends(get_current_admin)):
    doc = db.document(_SETTINGS_DOC).get()
    if not doc.exists:
        return ReminderSettings()
    return ReminderSettings(**doc.to_dict())


@router.put("/settings", response_model=ReminderSettings)
def update_settings(data: ReminderSettings, db=Depends(get_db), _=Depends(get_current_admin)):
    db.document(_SETTINGS_DOC).set(data.model_dump())
    # Reschedule the APScheduler job immediately
    from app.services.scheduler import reschedule_debt_reminder
    reschedule_debt_reminder(data)
    return data
