from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import calendar

from app.database import get_db, _next_id, _to_ns
from app.schemas import DepositCreate, ChargeCreate, DepositResponse, MemberBalanceResponse, DepositHistoryResponse, MemberDailyCost, SpendingItemResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


def _member_name(db, member_id: int) -> str:
    doc = db.collection("members").document(str(member_id)).get()
    return doc.to_dict().get("name", "?") if doc.exists else "?"


def _deposit_response(d: dict, member_names: dict) -> DepositResponse:
    return DepositResponse(
        id=d["id"],
        member_id=d["member_id"],
        member_name=member_names.get(d["member_id"], "?"),
        amount=d["amount"],
        note=d.get("note"),
        status=d.get("status", "approved"),
        type=d.get("type", "deposit"),
        created_at=d["created_at"],
    )


@router.get("/summary", response_model=list[MemberBalanceResponse])
def get_deposit_summary(db=Depends(get_db), current_user=Depends(get_current_user)):
    is_admin = getattr(current_user, "role", "user") == "admin"

    if is_admin:
        members = sorted(
            [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()],
            key=lambda m: m["name"],
        )
        # Build member_id → user info map for admin view
        all_users = [s.to_dict() for s in db.collection("users").where("is_active", "==", True).stream()]
        user_map = {u["member_id"]: u for u in all_users if u.get("member_id")}
    else:
        # Only show the current user's member
        mid = getattr(current_user, "member_id", None)
        if not mid:
            return []
        doc = db.collection("members").document(str(mid)).get()
        members = [doc.to_dict()] if doc.exists else []
        user_map = {}

    all_txns = [s.to_dict() for s in db.collection("deposits").stream()]
    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    finalized_ids = {
        s.to_dict()["id"]
        for s in db.collection("daily_orders").where("status", "==", "finalized").stream()
    }

    result = []
    for m in members:
        mid = m["id"]
        my_txns = [t for t in all_txns if t["member_id"] == mid]
        total_deposited = sum(t["amount"] for t in my_txns if t.get("type", "deposit") == "deposit" and t.get("status") == "approved")
        total_charged = sum(t["amount"] for t in my_txns if t.get("type") == "charge")
        total_spent = sum(
            i["total_cost"] for i in all_items
            if i["member_id"] == mid and i["daily_order_id"] in finalized_ids
        )
        u = user_map.get(mid)
        result.append(MemberBalanceResponse(
            id=mid,
            name=m["name"],
            username=u.get("username") if u else None,
            email=u.get("email") if u else None,
            total_deposited=total_deposited,
            total_charged=total_charged,
            total_spent=total_spent,
            balance=total_deposited - total_charged - total_spent,
        ))
    return result


@router.get("", response_model=list[DepositResponse])
def list_deposits(db=Depends(get_db), current_user=Depends(get_current_user)):
    is_admin = getattr(current_user, "role", "user") == "admin"
    col = db.collection("deposits")

    if is_admin:
        stream = col.stream()
    else:
        mid = getattr(current_user, "member_id", None)
        if not mid:
            return []
        stream = col.where("member_id", "==", mid).stream()

    deposits = [s.to_dict() for s in stream]
    deposits.sort(key=lambda d: d["created_at"], reverse=True)

    member_names: dict[int, str] = {}
    for d in deposits:
        mid = d["member_id"]
        if mid not in member_names:
            member_names[mid] = _member_name(db, mid)

    return [_deposit_response(d, member_names) for d in deposits]


@router.post("", response_model=DepositResponse, status_code=201)
def create_deposit(data: DepositCreate, db=Depends(get_db), current_user=Depends(get_current_user)):
    is_admin = getattr(current_user, "role", "user") == "admin"

    if is_admin and data.member_id:
        # Admin tạo deposit cho người khác → tự động approved
        target_member_id = data.member_id
        status = "approved"
    else:
        # User tạo yêu cầu cho chính mình → pending
        target_member_id = getattr(current_user, "member_id", None)
        if not target_member_id:
            raise HTTPException(status_code=400, detail="Tài khoản chưa được liên kết với thành viên")
        status = "approved" if is_admin else "pending"

    m_doc = db.collection("members").document(str(target_member_id)).get()
    if not m_doc.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    member_name = m_doc.to_dict().get("name", "?")

    dep_id = _next_id(db, "deposits")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": dep_id,
        "member_id": target_member_id,
        "amount": data.amount,
        "note": data.note,
        "status": status,
        "type": "deposit",
        "requested_by": current_user.id,
        "created_at": now,
    }
    db.collection("deposits").document(str(dep_id)).set(doc_data)

    return DepositResponse(
        id=dep_id,
        member_id=target_member_id,
        member_name=member_name,
        amount=data.amount,
        note=data.note,
        status=status,
        created_at=now,
    )


@router.post("/charge", response_model=DepositResponse, status_code=201)
def add_charge(data: ChargeCreate, db=Depends(get_db), _=Depends(get_current_admin)):
    """Admin thêm khoản chi ngoài — trừ trực tiếp vào deposit của thành viên."""
    m_doc = db.collection("members").document(str(data.member_id)).get()
    if not m_doc.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    member_name = m_doc.to_dict().get("name", "?")

    dep_id = _next_id(db, "deposits")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": dep_id,
        "member_id": data.member_id,
        "amount": data.amount,
        "note": data.note,
        "status": "approved",
        "type": "charge",
        "created_at": now,
    }
    db.collection("deposits").document(str(dep_id)).set(doc_data)
    return DepositResponse(
        id=dep_id, member_id=data.member_id, member_name=member_name,
        amount=data.amount, note=data.note, status="approved", type="charge", created_at=now,
    )


@router.post("/{deposit_id}/approve", response_model=DepositResponse)
def approve_deposit(deposit_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("deposits").document(str(deposit_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deposit not found")
    d = doc.to_dict()
    if d.get("status") == "approved":
        raise HTTPException(status_code=400, detail="Deposit đã được duyệt")
    ref.update({"status": "approved"})
    d["status"] = "approved"
    return _deposit_response(d, {d["member_id"]: _member_name(db, d["member_id"])})


@router.delete("/{deposit_id}", status_code=204)
def delete_deposit(deposit_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("deposits").document(str(deposit_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Deposit not found")
    ref.delete()


@router.get("/spending", response_model=list[SpendingItemResponse])
def get_spending(db=Depends(get_db), current_user=Depends(get_current_user)):
    """Lịch sử chi tiêu ăn (finalized order items) của user hiện tại."""
    from datetime import date as date_type
    mid = getattr(current_user, "member_id", None)
    if not mid:
        return []

    finalized_map = {
        s.to_dict()["id"]: s.to_dict()
        for s in db.collection("daily_orders").where("status", "==", "finalized").stream()
    }

    items = [
        s.to_dict() for s in
        db.collection("order_items")
        .where("member_id", "==", mid)
        .where("is_eating", "==", True)
        .stream()
    ]

    result = []
    for item in items:
        order = finalized_map.get(item["daily_order_id"])
        if not order:
            continue
        dish = item.get("dish_name") or item.get("dish_name_chay") or "—"
        order_date_raw = order["order_date"]
        order_date = date_type.fromisoformat(str(order_date_raw))
        result.append(SpendingItemResponse(
            daily_order_id=item["daily_order_id"],
            order_date=order_date,
            order_name=order.get("name"),
            dish_name=dish,
            is_chay=item.get("is_chay", False),
            total_cost=item.get("total_cost", 0) or 0,
            created_at=item.get("created_at") or order.get("created_at"),
        ))

    result.sort(key=lambda r: r.order_date, reverse=True)
    return result


@router.get("/history", response_model=DepositHistoryResponse)
def get_deposit_history(month: int, year: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    from datetime import date
    is_admin = getattr(current_user, "role", "user") == "admin"

    _, last_day = calendar.monthrange(year, month)
    start = str(date(year, month, 1))
    end = str(date(year, month, last_day))

    all_orders = [
        s.to_dict() for s in
        db.collection("daily_orders").where("status", "==", "finalized").stream()
    ]
    month_orders = [o for o in all_orders if start <= o["order_date"] <= end]
    month_orders.sort(key=lambda o: o["order_date"])
    order_ids = {o["id"] for o in month_orders}
    dates = [o["order_date"] for o in month_orders]

    if is_admin:
        active_members = sorted(
            [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()],
            key=lambda m: m["name"],
        )
    else:
        mid = getattr(current_user, "member_id", None)
        if not mid:
            return DepositHistoryResponse(month=month, year=year, dates=[], members=[])
        doc = db.collection("members").document(str(mid)).get()
        active_members = [doc.to_dict()] if doc.exists else []

    if not order_ids:
        return DepositHistoryResponse(
            month=month, year=year, dates=[],
            members=[MemberDailyCost(member_id=m["id"], member_name=m["name"], daily_costs={}, total_spent=0) for m in active_members],
        )

    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    items = [i for i in all_items if i["daily_order_id"] in order_ids]
    order_date_map = {o["id"]: o["order_date"] for o in month_orders}

    matrix: dict[int, dict] = {}
    for item in items:
        mid = item["member_id"]
        d = order_date_map.get(item["daily_order_id"])
        if d:
            matrix.setdefault(mid, {})[d] = item.get("total_cost", 0) or 0

    result_members = []
    for m in active_members:
        daily = matrix.get(m["id"], {})
        result_members.append(MemberDailyCost(
            member_id=m["id"],
            member_name=m["name"],
            daily_costs=daily,
            total_spent=sum(daily.values()),
        ))

    return DepositHistoryResponse(month=month, year=year, dates=dates, members=result_members)
