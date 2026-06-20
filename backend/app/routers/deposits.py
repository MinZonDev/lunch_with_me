from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import calendar

from app.database import get_db, _next_id, _to_ns
from app.schemas import DepositCreate, DepositResponse, MemberBalanceResponse, DepositHistoryResponse, MemberDailyCost
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


@router.get("/summary", response_model=list[MemberBalanceResponse])
def get_deposit_summary(db=Depends(get_db), _=Depends(get_current_user)):
    members = sorted(
        [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()],
        key=lambda m: m["name"],
    )

    all_deposits = [s.to_dict() for s in db.collection("deposits").stream()]
    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]

    # Get finalized order IDs
    finalized_ids = {
        s.to_dict()["id"]
        for s in db.collection("daily_orders").where("status", "==", "finalized").stream()
    }

    result = []
    for m in members:
        mid = m["id"]
        total_deposited = sum(d["amount"] for d in all_deposits if d["member_id"] == mid)
        total_spent = sum(
            i["total_cost"] for i in all_items
            if i["member_id"] == mid and i["daily_order_id"] in finalized_ids
        )
        result.append(MemberBalanceResponse(
            id=mid,
            name=m["name"],
            total_deposited=total_deposited,
            total_spent=total_spent,
            balance=total_deposited - total_spent,
        ))
    return result


@router.get("", response_model=list[DepositResponse])
def list_deposits(member_id: int | None = None, db=Depends(get_db), _=Depends(get_current_user)):
    col = db.collection("deposits")
    if member_id:
        stream = col.where("member_id", "==", member_id).stream()
    else:
        stream = col.stream()

    deposits = [s.to_dict() for s in stream]
    deposits.sort(key=lambda d: d["created_at"], reverse=True)

    # Build member name cache
    member_names: dict[int, str] = {}
    for d in deposits:
        mid = d["member_id"]
        if mid not in member_names:
            m_doc = db.collection("members").document(str(mid)).get()
            member_names[mid] = m_doc.to_dict().get("name", "?") if m_doc.exists else "?"

    return [
        DepositResponse(
            id=d["id"],
            member_id=d["member_id"],
            member_name=member_names[d["member_id"]],
            amount=d["amount"],
            note=d.get("note"),
            created_at=d["created_at"],
        )
        for d in deposits
    ]


@router.post("", response_model=DepositResponse, status_code=201)
def create_deposit(data: DepositCreate, db=Depends(get_db), _=Depends(get_current_admin)):
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
        "created_at": now,
    }
    db.collection("deposits").document(str(dep_id)).set(doc_data)

    return DepositResponse(
        id=dep_id,
        member_id=data.member_id,
        member_name=member_name,
        amount=data.amount,
        note=data.note,
        created_at=now,
    )


@router.get("/history", response_model=DepositHistoryResponse)
def get_deposit_history(month: int, year: int, db=Depends(get_db), _=Depends(get_current_user)):
    from datetime import date

    _, last_day = calendar.monthrange(year, month)
    start = str(date(year, month, 1))
    end = str(date(year, month, last_day))

    # Finalized orders in month
    all_orders = [
        s.to_dict() for s in
        db.collection("daily_orders").where("status", "==", "finalized").stream()
    ]
    month_orders = [o for o in all_orders if start <= o["order_date"] <= end]
    month_orders.sort(key=lambda o: o["order_date"])
    order_ids = {o["id"] for o in month_orders}
    dates = [o["order_date"] for o in month_orders]

    if not order_ids:
        active_members = sorted(
            [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()],
            key=lambda m: m["name"],
        )
        return DepositHistoryResponse(
            month=month, year=year, dates=[],
            members=[MemberDailyCost(member_id=m["id"], member_name=m["name"], daily_costs={}, total_spent=0) for m in active_members],
        )

    # Load eating items for those orders
    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    items = [i for i in all_items if i["daily_order_id"] in order_ids]

    # Build order_id → date map
    order_date_map = {o["id"]: o["order_date"] for o in month_orders}

    # Build matrix: member_id → {date_str → cost}
    matrix: dict[int, dict] = {}
    for item in items:
        mid = item["member_id"]
        d = order_date_map.get(item["daily_order_id"])
        if d:
            matrix.setdefault(mid, {})[d] = item.get("total_cost", 0) or 0

    active_members = sorted(
        [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()],
        key=lambda m: m["name"],
    )
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


@router.delete("/{deposit_id}", status_code=204)
def delete_deposit(deposit_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("deposits").document(str(deposit_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Deposit not found")
    ref.delete()
