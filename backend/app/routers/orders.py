from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.core.auth import get_current_user, get_current_admin
from app.core.config import settings
from app.database import get_db, _next_id, _to_ns, _doc_ns
from app.schemas import (
    DailyOrderCreate, DailyOrderUpdate, DailyOrderFinalize,
    DailyOrderResponse, DailyOrderListResponse, OrderItemInOrder,
)
from app.services.cost_calculator import calculate_costs

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _make_deadline(order_date: date, deadline_time: str | None) -> datetime:
    """Convert 'HH:MM' VN time on order_date to UTC timezone-aware datetime."""
    time_str = deadline_time or settings.order_deadline_default
    h, m = map(int, time_str.split(":"))
    vn_dt = datetime(order_date.year, order_date.month, order_date.day, h, m, tzinfo=VN_TZ)
    return vn_dt.astimezone(timezone.utc)


def _minutes_remaining(deadline) -> int | None:
    if deadline is None:
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(timezone.utc)
    return int(delta.total_seconds() // 60)


def _load_items_with_names(db, order_id: int) -> list[SimpleNamespace]:
    """Load order items for an order_id, enriching each with member_name."""
    members_cache: dict[int, str] = {}
    items = []
    for snap in db.collection("order_items").where("daily_order_id", "==", order_id).stream():
        d = snap.to_dict()
        mid = d["member_id"]
        if mid not in members_cache:
            m_doc = db.collection("members").document(str(mid)).get()
            members_cache[mid] = m_doc.to_dict().get("name", "?") if m_doc.exists else "?"
        d["member_name"] = members_cache[mid]
        items.append(SimpleNamespace(**d))
    return items


def _build_order_response(order, items) -> DailyOrderResponse:
    order_date = order.order_date
    if isinstance(order_date, str):
        order_date = date.fromisoformat(order_date)

    item_responses = []
    eater_count = 0
    chay_eater_count = 0
    for item in items:
        item_responses.append(OrderItemInOrder(
            id=item.id,
            member_id=item.member_id,
            member_name=item.member_name,
            dish_name=getattr(item, "dish_name", None),
            dish_name_chay=getattr(item, "dish_name_chay", None),
            note=getattr(item, "note", None),
            is_eating=item.is_eating,
            is_chay=item.is_chay,
            extra_item_description=getattr(item, "extra_item_description", None),
            extra_item_cost=getattr(item, "extra_item_cost", 0) or 0,
            total_cost=getattr(item, "total_cost", 0) or 0,
        ))
        if item.is_eating:
            if item.is_chay:
                chay_eater_count += 1
            else:
                eater_count += 1

    return DailyOrderResponse(
        id=order.id,
        order_date=order_date,
        status=order.status,
        menu_link=getattr(order, "menu_link", None),
        menu_link_chay=getattr(order, "menu_link_chay", None),
        order_deadline=getattr(order, "order_deadline", None),
        minutes_remaining=_minutes_remaining(getattr(order, "order_deadline", None)),
        total_bill=getattr(order, "total_bill", 0) or 0,
        total_bill_chay=getattr(order, "total_bill_chay", 0) or 0,
        shared_cost_per_person=getattr(order, "shared_cost_per_person", 0) or 0,
        shared_cost_per_person_chay=getattr(order, "shared_cost_per_person_chay", 0) or 0,
        note=getattr(order, "note", None),
        created_by=getattr(order, "created_by", None),
        created_at=order.created_at,
        items=item_responses,
        eater_count=eater_count,
        chay_eater_count=chay_eater_count,
    )


def _get_order_by_id(db, order_id: int):
    """Find daily_order by numeric id field."""
    results = list(db.collection("daily_orders").where("id", "==", order_id).limit(1).stream())
    if not results:
        return None, None
    doc = results[0]
    return doc.reference, _to_ns(doc.to_dict())


@router.get("", response_model=list[DailyOrderListResponse])
def list_orders(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=30, le=100),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    stream = db.collection("daily_orders").stream()
    orders = [_to_ns(s.to_dict()) for s in stream]

    # Filter by date range
    if start_date:
        orders = [o for o in orders if date.fromisoformat(str(o.order_date)) >= start_date]
    if end_date:
        orders = [o for o in orders if date.fromisoformat(str(o.order_date)) <= end_date]

    orders.sort(key=lambda o: str(o.order_date), reverse=True)
    orders = orders[:limit]

    result = []
    for order in orders:
        order_date = order.order_date if isinstance(order.order_date, date) else date.fromisoformat(str(order.order_date))
        items_snap = list(db.collection("order_items").where("daily_order_id", "==", order.id).stream())
        eater_count = sum(1 for s in items_snap if not s.to_dict().get("is_chay") and s.to_dict().get("is_eating"))
        chay_eater_count = sum(1 for s in items_snap if s.to_dict().get("is_chay") and s.to_dict().get("is_eating"))
        result.append(DailyOrderListResponse(
            id=order.id,
            order_date=order_date,
            status=order.status,
            total_bill=getattr(order, "total_bill", 0) or 0,
            total_bill_chay=getattr(order, "total_bill_chay", 0) or 0,
            eater_count=eater_count,
            chay_eater_count=chay_eater_count,
            note=getattr(order, "note", None),
            created_at=order.created_at,
        ))
    return result


@router.get("/today", response_model=DailyOrderResponse | None)
def get_today_order(db=Depends(get_db), _=Depends(get_current_user)):
    today = datetime.now(VN_TZ).date()
    doc = db.collection("daily_orders").document(str(today)).get()
    if not doc.exists:
        return None
    order = _to_ns(doc.to_dict())
    items = _load_items_with_names(db, order.id)
    return _build_order_response(order, items)


@router.get("/{order_id}", response_model=DailyOrderResponse)
def get_order(order_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    _, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.post("", response_model=DailyOrderResponse, status_code=201)
def create_order(data: DailyOrderCreate, db=Depends(get_db), _=Depends(get_current_admin)):
    doc_id = str(data.order_date)
    if db.collection("daily_orders").document(doc_id).get().exists:
        raise HTTPException(status_code=400, detail="Order for this date already exists")

    order_id = _next_id(db, "daily_orders")
    now = datetime.now(timezone.utc)
    order_data = {
        "id": order_id,
        "order_date": doc_id,
        "status": "open",
        "menu_link": data.menu_link,
        "menu_link_chay": data.menu_link_chay,
        "order_deadline": _make_deadline(data.order_date, data.deadline_time),
        "total_bill": 0,
        "total_bill_chay": 0,
        "shared_cost_per_person": 0,
        "shared_cost_per_person_chay": 0,
        "note": data.note,
        "created_by": data.created_by,
        "created_at": now,
    }
    db.collection("daily_orders").document(doc_id).set(order_data)

    # Auto-create order items for all active members
    active_members = list(db.collection("members").where("is_active", "==", True).stream())
    batch = db.batch()
    for m_snap in active_members:
        m = m_snap.to_dict()
        item_id = _next_id(db, "order_items")
        ref = db.collection("order_items").document(str(item_id))
        batch.set(ref, {
            "id": item_id,
            "daily_order_id": order_id,
            "order_date": doc_id,
            "member_id": m["id"],
            "dish_name": None,
            "dish_name_chay": None,
            "note": None,
            "is_eating": False,
            "is_chay": False,
            "extra_item_description": None,
            "extra_item_cost": 0,
            "total_cost": 0,
            "created_at": now,
        })
    batch.commit()

    order = _to_ns(order_data)
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.put("/{order_id}", response_model=DailyOrderResponse)
def update_order(order_id: int, data: DailyOrderUpdate, db=Depends(get_db), _=Depends(get_current_admin)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = {}
    if data.menu_link is not None:
        updates["menu_link"] = data.menu_link
    if data.menu_link_chay is not None:
        updates["menu_link_chay"] = data.menu_link_chay
    if data.total_bill is not None:
        updates["total_bill"] = data.total_bill
    if data.total_bill_chay is not None:
        updates["total_bill_chay"] = data.total_bill_chay
    if data.note is not None:
        updates["note"] = data.note
    if data.status is not None:
        updates["status"] = data.status

    if updates:
        ref.update(updates)

    order = _to_ns({**ref.get().to_dict()})
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.post("/{order_id}/lock", response_model=DailyOrderResponse)
def lock_order(order_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is already finalized")
    ref.update({"status": "locked"})
    items = _load_items_with_names(db, order_id)
    return _build_order_response(_to_ns(ref.get().to_dict()), items)


@router.post("/{order_id}/reopen", response_model=DailyOrderResponse)
def reopen_order(order_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    ref.update({"status": "open"})
    items = _load_items_with_names(db, order_id)
    return _build_order_response(_to_ns(ref.get().to_dict()), items)


@router.post("/{order_id}/finalize", response_model=DailyOrderResponse)
def finalize_order(order_id: int, data: DailyOrderFinalize, db=Depends(get_db), _=Depends(get_current_admin)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.total_bill = data.total_bill
    order.total_bill_chay = data.total_bill_chay

    items = _load_items_with_names(db, order_id)
    cost_result = calculate_costs(order, items)

    # Update order
    ref.update({
        "total_bill": data.total_bill,
        "total_bill_chay": data.total_bill_chay,
        "status": "finalized",
        "shared_cost_per_person": cost_result["shared_cost_per_person"],
        "shared_cost_per_person_chay": cost_result["shared_cost_per_person_chay"],
    })

    # Update item costs in batch
    cost_map = {c["item_id"]: c["total_cost"] for c in cost_result["item_costs"]}
    if cost_map:
        batch = db.batch()
        for item in items:
            item_ref = db.collection("order_items").document(str(item.id))
            batch.update(item_ref, {"total_cost": cost_map.get(item.id, 0)})
        batch.commit()

    order = _to_ns(ref.get().to_dict())
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)
