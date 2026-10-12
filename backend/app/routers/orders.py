from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud.firestore import Query as FsQuery
from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.core.auth import get_current_user, get_current_admin, get_order_manager
from app.core.config import settings
from app.database import get_db, _next_id, _next_ids, _to_ns, _doc_ns
from app.schemas import (
    DailyOrderCreate, DailyOrderUpdate, DailyOrderFinalize, DailyOrderLinksUpdate,
    DailyOrderResponse, DailyOrderListResponse, DailyOrderPage, DailyOrderStats,
    OrderItemInOrder, OrderLinkItem,
)
from app.services.cost_calculator import calculate_costs
from app.services.ledger import member_names, chunks

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
    docs = [s.to_dict() for s in db.collection("order_items").where("daily_order_id", "==", order_id).stream()]
    names = member_names(db, {d["member_id"] for d in docs})
    return [SimpleNamespace(**d, member_name=names.get(d["member_id"], "?")) for d in docs]


def _build_order_response(order, items) -> DailyOrderResponse:
    order_date = order.order_date
    if isinstance(order_date, str):
        order_date = date.fromisoformat(order_date)

    item_responses = []
    eater_count = 0
    for item in items:
        # Backward compat: old items may have dish_name_chay instead of dish_name
        dish = getattr(item, "dish_name", None) or getattr(item, "dish_name_chay", None)
        item_responses.append(OrderItemInOrder(
            id=item.id,
            member_id=item.member_id,
            member_name=item.member_name,
            dish_name=dish,
            note=getattr(item, "note", None),
            is_eating=item.is_eating,
            extra_item_description=getattr(item, "extra_item_description", None),
            extra_item_cost=getattr(item, "extra_item_cost", 0) or 0,
            is_exception=getattr(item, "is_exception", False) or False,
            exception_amount=getattr(item, "exception_amount", 0) or 0,
            total_cost=getattr(item, "total_cost", 0) or 0,
        ))
        if item.is_eating:
            eater_count += 1

    raw_links = getattr(order, "links", None) or []
    parsed_links = [OrderLinkItem(label=l["label"], url=l["url"]) for l in raw_links if isinstance(l, dict)]

    return DailyOrderResponse(
        id=order.id,
        order_date=order_date,
        name=getattr(order, "name", None),
        status=order.status,
        restaurant_id=getattr(order, "restaurant_id", None),
        restaurant_name=getattr(order, "restaurant_name", None),
        links=parsed_links,
        order_deadline=getattr(order, "order_deadline", None),
        minutes_remaining=_minutes_remaining(getattr(order, "order_deadline", None)),
        total_bill=getattr(order, "total_bill", 0) or 0,
        shared_cost_per_person=getattr(order, "shared_cost_per_person", 0) or 0,
        note=getattr(order, "note", None),
        created_by=getattr(order, "created_by", None),
        created_at=order.created_at,
        payer_member_id=getattr(order, "payer_member_id", None),
        payer_name=getattr(order, "payer_name", None),
        payer_amount=getattr(order, "payer_amount", 0) or 0,
        items=item_responses,
        eater_count=eater_count,
    )


def _get_order_by_id(db, order_id: int):
    """Find daily_order by numeric id field."""
    results = list(db.collection("daily_orders").where("id", "==", order_id).limit(1).stream())
    if not results:
        return None, None
    doc = results[0]
    return doc.reference, _to_ns(doc.to_dict())


def recalculate_costs(db, ref, order, extra_updates: dict | None = None) -> None:
    """Split order.total_bill among its items and persist the result.

    Shared by finalize and by edits made after finalizing (extras, exceptions).
    Raises 400 when the bill cannot be split (e.g. exceptions exceed the bill).
    """
    items = [SimpleNamespace(**s.to_dict()) for s in
             db.collection("order_items").where("daily_order_id", "==", order.id).stream()]
    try:
        cost_result = calculate_costs(order, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ref.update({
        "total_bill": order.total_bill,
        "shared_cost_per_person": cost_result["shared_cost_per_person"],
        **(extra_updates or {}),
    })

    cost_map = {c["item_id"]: c["total_cost"] for c in cost_result["item_costs"]}
    if items:
        batch = db.batch()
        for item in items:
            item_ref = db.collection("order_items").document(str(item.id))
            batch.update(item_ref, {"total_cost": cost_map.get(item.id, 0)})
        batch.commit()


def _eater_counts(db, order_ids: list[int]) -> dict[int, int]:
    counts = {oid: 0 for oid in order_ids}
    for chunk in chunks(order_ids):
        q = (db.collection("order_items")
             .where("daily_order_id", "in", chunk)
             .where("is_eating", "==", True)
             .select(["daily_order_id"]))
        for snap in q.stream():
            counts[snap.to_dict()["daily_order_id"]] += 1
    return counts


def _encode_cursor(order) -> str:
    return f"{order['order_date']}_{order['id']}"


def _decode_cursor(cursor: str) -> dict:
    try:
        order_date, oid = cursor.rsplit("_", 1)
        date.fromisoformat(order_date)
        return {"order_date": order_date, "id": int(oid)}
    except ValueError:
        raise HTTPException(status_code=400, detail="Cursor không hợp lệ")


def _payer_credit_snaps(db, order_id: int) -> list:
    return list(db.collection("deposits")
                .where("daily_order_id", "==", order_id)
                .where("type", "==", "order_payment").stream())


def sync_payer_credit(db, order: dict) -> None:
    """Keep the payer's 'Đặt cơm ngày dd-mm-yyyy' credit in line with the order.

    One credit per order: created/updated while the order is finalized with a
    member payer, removed otherwise (admin payer, reopened order).
    """
    existing = _payer_credit_snaps(db, order["id"])
    payer_id = order.get("payer_member_id")
    amount = order.get("payer_amount", 0) or 0

    if order.get("status") != "finalized" or payer_id is None or amount <= 0:
        for snap in existing:
            snap.reference.delete()
        return

    day = date.fromisoformat(str(order["order_date"])).strftime("%d-%m-%Y")
    note = f"Đặt cơm ngày {day}"
    if order.get("name"):
        note += f" ({order['name']})"
    fields = {"member_id": payer_id, "amount": amount, "note": note, "status": "approved"}
    if existing:
        existing[0].reference.update(fields)
        for extra in existing[1:]:
            extra.reference.delete()
        return

    dep_id = _next_id(db, "deposits")
    db.collection("deposits").document(str(dep_id)).set({
        "id": dep_id,
        **fields,
        "type": "order_payment",
        "daily_order_id": order["id"],
        "created_at": datetime.now(timezone.utc),
    })


@router.get("", response_model=DailyOrderPage)
def list_orders(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, description="next_cursor của trang trước"),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """Orders newest first, paginated by cursor (order_date + id)."""
    q = db.collection("daily_orders")
    if start_date:
        q = q.where("order_date", ">=", str(start_date))
    if end_date:
        q = q.where("order_date", "<=", str(end_date))
    q = q.order_by("order_date", direction=FsQuery.DESCENDING).order_by("id", direction=FsQuery.DESCENDING)
    if cursor:
        q = q.start_after(_decode_cursor(cursor))
    docs = [s.to_dict() for s in q.limit(limit + 1).stream()]

    has_more = len(docs) > limit
    docs = docs[:limit]
    counts = _eater_counts(db, [o["id"] for o in docs])

    items = [
        DailyOrderListResponse(
            id=o["id"],
            order_date=date.fromisoformat(str(o["order_date"])),
            name=o.get("name"),
            status=o["status"],
            total_bill=o.get("total_bill", 0) or 0,
            eater_count=counts.get(o["id"], 0),
            note=o.get("note"),
            created_at=o["created_at"],
        )
        for o in docs
    ]
    return DailyOrderPage(items=items, next_cursor=_encode_cursor(docs[-1]) if has_more else None)


@router.get("/stats", response_model=DailyOrderStats)
def order_stats(db=Depends(get_db), _=Depends(get_current_user)):
    """Totals over all orders, without loading full documents."""
    total = finalized = spent = 0
    for snap in db.collection("daily_orders").select(["status", "total_bill"]).stream():
        o = snap.to_dict()
        total += 1
        if o.get("status") == "finalized":
            finalized += 1
            spent += o.get("total_bill", 0) or 0
    return DailyOrderStats(total_orders=total, finalized_count=finalized, total_spent=spent)


@router.get("/today", response_model=list[DailyOrderResponse])
def get_today_order(db=Depends(get_db), _=Depends(get_current_user)):
    today_str = str(datetime.now(VN_TZ).date())
    snaps = db.collection("daily_orders").where("order_date", "==", today_str).stream()
    orders = sorted([_to_ns(s.to_dict()) for s in snaps], key=lambda o: o.created_at)
    return [_build_order_response(o, _load_items_with_names(db, o.id)) for o in orders]


@router.get("/{order_id}", response_model=DailyOrderResponse)
def get_order(order_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    _, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.post("", response_model=DailyOrderResponse, status_code=201)
def create_order(data: DailyOrderCreate, db=Depends(get_db), _=Depends(get_order_manager)):
    order_id = _next_id(db, "daily_orders")
    doc_id = str(order_id)  # Use numeric ID as doc ID to allow multiple per day

    # Resolve restaurant
    restaurant_id = data.restaurant_id
    restaurant_name = None
    menu_link = data.menu_link
    if restaurant_id:
        r_doc = db.collection("restaurants").document(str(restaurant_id)).get()
        if r_doc.exists:
            r = r_doc.to_dict()
            restaurant_name = r.get("name")
            if not menu_link:
                menu_link = r.get("link")

    now = datetime.now(timezone.utc)
    # Pre-populate links from restaurant if available
    initial_links = []
    if restaurant_name and menu_link:
        initial_links = [{"label": restaurant_name, "url": menu_link}]

    order_date_str = str(data.order_date)
    order_data = {
        "id": order_id,
        "order_date": order_date_str,
        "name": data.name or None,
        "status": "open",
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant_name,
        "links": initial_links,
        "order_deadline": _make_deadline(data.order_date, data.deadline_time),
        "total_bill": 0,
        "shared_cost_per_person": 0,
        "note": data.note,
        "created_by": data.created_by,
        "created_at": now,
    }
    db.collection("daily_orders").document(doc_id).set(order_data)

    # Auto-create order items for all active members
    active_members = list(db.collection("members").where("is_active", "==", True).stream())
    item_ids = _next_ids(db, "order_items", len(active_members))
    batch = db.batch()
    for m_snap, item_id in zip(active_members, item_ids):
        m = m_snap.to_dict()
        ref = db.collection("order_items").document(str(item_id))
        batch.set(ref, {
            "id": item_id,
            "daily_order_id": order_id,
            "order_date": order_date_str,
            "member_id": m["id"],
            "dish_name": None,
            "note": None,
            "is_eating": False,
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
    if data.total_bill is not None:
        updates["total_bill"] = data.total_bill
    if data.note is not None:
        updates["note"] = data.note
    if data.status is not None:
        updates["status"] = data.status
    if data.name is not None:
        updates["name"] = data.name.strip() or None

    if updates:
        ref.update(updates)

    order = _to_ns({**ref.get().to_dict()})
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    """Delete an order and all of its order items (admin only)."""
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    batch = db.batch()
    for snap in db.collection("order_items").where("daily_order_id", "==", order_id).stream():
        batch.delete(snap.reference)
    for snap in _payer_credit_snaps(db, order_id):
        batch.delete(snap.reference)
    batch.delete(ref)
    batch.commit()


@router.post("/{order_id}/lock", response_model=DailyOrderResponse)
def lock_order(order_id: int, db=Depends(get_db), _=Depends(get_order_manager)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is already finalized")
    ref.update({"status": "locked"})
    items = _load_items_with_names(db, order_id)
    return _build_order_response(_to_ns(ref.get().to_dict()), items)


@router.post("/{order_id}/reopen", response_model=DailyOrderResponse)
def reopen_order(order_id: int, db=Depends(get_db), current_user=Depends(get_order_manager)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized" and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin được mở lại order đã chốt")
    ref.update({"status": "open"})
    # Costs of a non-finalized order don't count, so neither does the payer credit
    sync_payer_credit(db, ref.get().to_dict())
    items = _load_items_with_names(db, order_id)
    return _build_order_response(_to_ns(ref.get().to_dict()), items)


@router.post("/{order_id}/finalize", response_model=DailyOrderResponse)
def finalize_order(order_id: int, data: DailyOrderFinalize, db=Depends(get_db), _=Depends(get_order_manager)):
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_bill = getattr(order, "total_bill", None)
    order.total_bill = data.total_bill
    updates = {"status": "finalized"}

    if {"payer_member_id", "payer_amount"} & data.model_fields_set:
        payer_id = data.payer_member_id
        payer_name = None
        if payer_id is not None:
            m_doc = db.collection("members").document(str(payer_id)).get()
            if not m_doc.exists:
                raise HTTPException(status_code=404, detail="Không tìm thấy người trả tiền")
            payer_name = m_doc.to_dict().get("name")
        amount = data.payer_amount if data.payer_amount is not None else data.total_bill
        updates.update({
            "payer_member_id": payer_id,
            "payer_name": payer_name,
            "payer_amount": amount if payer_id is not None else 0,
        })
    elif getattr(order, "payer_member_id", None) is not None and getattr(order, "payer_amount", 0) == old_bill:
        # Bill edited without touching the payer: the amount followed the old bill, keep it in sync
        updates["payer_amount"] = data.total_bill

    recalculate_costs(db, ref, order, updates)
    sync_payer_credit(db, ref.get().to_dict())

    order = _to_ns(ref.get().to_dict())
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)


@router.put("/{order_id}/links", response_model=DailyOrderResponse)
def update_links(order_id: int, data: DailyOrderLinksUpdate, db=Depends(get_db), _=Depends(get_order_manager)):
    """Replace the full list of order links (admin only)."""
    ref, order = _get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    ref.update({"links": [{"label": l.label, "url": l.url} for l in data.links]})
    order = _to_ns(ref.get().to_dict())
    items = _load_items_with_names(db, order_id)
    return _build_order_response(order, items)
