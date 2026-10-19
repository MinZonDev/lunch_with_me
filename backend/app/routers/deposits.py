from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone
import calendar

from app.database import get_db, _next_id, _to_ns
from app.schemas import DepositCreate, ChargeCreate, DepositUpdate, DepositResponse, MemberBalanceResponse, DepositHistoryResponse, MemberDailyCost, SpendingItemResponse, MemberDetailResponse, MemberTransactionItem
from app.core.auth import get_current_user, get_current_admin
from app.services import blacklist
from app.services.ledger import compute_balances, empty_balance, member_names, orders_by_ids, signed_delta

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

    balances = compute_balances(db, None if is_admin else members[0]["id"]) if members else {}

    result = []
    for m in members:
        mid = m["id"]
        b = balances.get(mid) or empty_balance()
        u = user_map.get(mid)
        result.append(MemberBalanceResponse(
            id=mid,
            name=m["name"],
            username=u.get("username") if u else None,
            email=u.get("email") if u else None,
            total_deposited=b["deposited"],
            total_charged=b["charged"],
            total_spent=b["spent"],
            total_withdrawn=b["withdrawn"],
            balance=b["balance"],
        ))
    return result


@router.get("", response_model=list[DepositResponse])
def list_deposits(
    status: str | None = Query(default=None, description="Lọc theo trạng thái, VD: pending"),
    type: str | None = Query(default=None, description="deposit | charge | order_payment | withdrawal"),
    limit: int | None = Query(default=None, ge=1, le=500),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    is_admin = getattr(current_user, "role", "user") == "admin"
    col = db.collection("deposits")
    if status:
        col = col.where("status", "==", status)

    if is_admin:
        stream = col.stream()
    else:
        mid = getattr(current_user, "member_id", None)
        if not mid:
            return []
        stream = col.where("member_id", "==", mid).stream()

    deposits = [s.to_dict() for s in stream]
    if type:
        deposits = [d for d in deposits if d.get("type", "deposit") == type]
    deposits.sort(key=lambda d: d["created_at"], reverse=True)
    if limit:
        deposits = deposits[:limit]

    names = member_names(db, {d["member_id"] for d in deposits})
    return [_deposit_response(d, names) for d in deposits]


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
    if d.get("type", "deposit") != "deposit":
        raise HTTPException(status_code=400, detail="Chỉ duyệt được yêu cầu nạp tiền")
    if d.get("status") == "approved":
        raise HTTPException(status_code=400, detail="Deposit đã được duyệt")
    ref.update({"status": "approved"})
    d["status"] = "approved"
    blacklist.debt_status(db, d["member_id"])  # unblocks the member if this paid off the debt
    return _deposit_response(d, {d["member_id"]: _member_name(db, d["member_id"])})


@router.put("/{deposit_id}", response_model=DepositResponse)
def update_deposit(deposit_id: int, data: DepositUpdate, db=Depends(get_db), _=Depends(get_current_admin)):
    """Admin sửa số tiền / ghi chú của một giao dịch nạp hoặc khoản chi."""
    ref = db.collection("deposits").document(str(deposit_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deposit not found")

    updates = {}
    if data.amount is not None:
        updates["amount"] = data.amount
    if data.note is not None:
        updates["note"] = data.note.strip() or None
    if updates:
        ref.update(updates)

    d = {**doc.to_dict(), **updates}
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

    items = [
        s.to_dict() for s in
        db.collection("order_items")
        .where("member_id", "==", mid)
        .where("is_eating", "==", True)
        .stream()
    ]
    finalized_map = orders_by_ids(db, {i["daily_order_id"] for i in items}, finalized_only=True)

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
            total_cost=item.get("total_cost", 0) or 0,
            created_at=item.get("created_at") or order.get("created_at"),
        ))

    result.sort(key=lambda r: r.order_date, reverse=True)
    return result


@router.get("/member/{member_id}", response_model=MemberDetailResponse)
def get_member_detail(member_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    """Chi tiết giao dịch của một thành viên: nạp tiền, khoản chi, tiền ăn."""
    from datetime import date as date_type
    is_admin = getattr(current_user, "role", "user") == "admin"
    my_member_id = getattr(current_user, "member_id", None)

    # Non-admin can only view their own
    if not is_admin and my_member_id != member_id:
        raise HTTPException(status_code=403, detail="Không có quyền xem thông tin này")

    m_doc = db.collection("members").document(str(member_id)).get()
    if not m_doc.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    member_name = m_doc.to_dict().get("name", "?")

    # All deposit/charge transactions for this member
    dep_docs = [s.to_dict() for s in db.collection("deposits").where("member_id", "==", member_id).stream()]
    dep_docs.sort(key=lambda d: d["created_at"])

    # All spending (finalized order items)
    spending_items = [
        s.to_dict() for s in
        db.collection("order_items")
        .where("member_id", "==", member_id)
        .where("is_eating", "==", True)
        .stream()
    ]
    finalized_map = orders_by_ids(db, {i["daily_order_id"] for i in spending_items}, finalized_only=True)

    b = compute_balances(db, member_id).get(member_id) or empty_balance()

    # Build unified transaction list; deltas[i] is how txns[i] moves the balance
    txns: list[MemberTransactionItem] = []
    deltas: list[int] = []

    for d in dep_docs:
        txn_type = d.get("type", "deposit")
        txns.append(MemberTransactionItem(
            type=txn_type,
            date=d["created_at"],
            amount=d["amount"],
            description=d.get("note"),
            status=d.get("status", "approved"),
        ))
        deltas.append(signed_delta(d))

    for item in spending_items:
        order = finalized_map.get(item["daily_order_id"])
        if not order:
            continue
        dish = item.get("dish_name") or item.get("dish_name_chay") or "—"
        order_date_raw = order["order_date"]
        order_date = date_type.fromisoformat(str(order_date_raw))
        order_name = order.get("name")
        desc = dish
        if order_name:
            desc = f"{dish} ({order_name})"
        txns.append(MemberTransactionItem(
            type="spending",
            date=item.get("created_at") or order.get("created_at"),
            amount=item.get("total_cost", 0) or 0,
            description=desc,
            order_date=order_date,
            daily_order_id=item["daily_order_id"],
        ))
        deltas.append(-(item.get("total_cost", 0) or 0))

    # Compute running balance from oldest to newest, then show newest first
    ordered = sorted(zip(txns, deltas), key=lambda p: p[0].date)
    running = 0
    for t, delta in ordered:
        running += delta
        t.running_balance = running
    txns = [t for t, _ in reversed(ordered)]

    return MemberDetailResponse(
        member_id=member_id,
        member_name=member_name,
        total_deposited=b["deposited"],
        total_charged=b["charged"],
        total_spent=b["spent"],
        total_withdrawn=b["withdrawn"],
        balance=b["balance"],
        transactions=txns,
    )


@router.get("/history", response_model=DepositHistoryResponse)
def get_deposit_history(month: int, year: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    from datetime import date
    is_admin = getattr(current_user, "role", "user") == "admin"

    _, last_day = calendar.monthrange(year, month)
    start = str(date(year, month, 1))
    end = str(date(year, month, last_day))

    month_orders = [
        s.to_dict() for s in
        db.collection("daily_orders")
        .where("order_date", ">=", start).where("order_date", "<=", end).stream()
    ]
    month_orders = [o for o in month_orders if o.get("status") == "finalized"]
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

    month_items = (
        db.collection("order_items")
        .where("order_date", ">=", start).where("order_date", "<=", end)
        .select(["member_id", "daily_order_id", "is_eating", "total_cost"])
        .stream()
    )
    items = [d for d in (s.to_dict() for s in month_items)
             if d.get("is_eating") and d["daily_order_id"] in order_ids]
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
