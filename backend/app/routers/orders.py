from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app.core.auth import get_current_user, get_current_admin

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

from app.database import get_db
from app.models import DailyOrder, OrderItem, Member
from app.schemas import (
    DailyOrderCreate, DailyOrderUpdate, DailyOrderFinalize,
    DailyOrderResponse, DailyOrderListResponse, OrderItemInOrder,
)
from app.services.cost_calculator import calculate_costs

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _build_order_response(order: DailyOrder) -> DailyOrderResponse:
    """Build a detailed order response with item details."""
    items = []
    eater_count = 0
    chay_eater_count = 0

    for item in order.items:
        items.append(OrderItemInOrder(
            id=item.id,
            member_id=item.member_id,
            member_name=item.member.name,
            dish_name=item.dish_name,
            dish_name_chay=item.dish_name_chay,
            note=item.note,
            is_eating=item.is_eating,
            is_chay=item.is_chay,
            extra_item_description=item.extra_item_description,
            extra_item_cost=item.extra_item_cost or 0,
            total_cost=item.total_cost or 0,
        ))
        if item.is_eating:
            if item.is_chay:
                chay_eater_count += 1
            else:
                eater_count += 1

    return DailyOrderResponse(
        id=order.id,
        order_date=order.order_date,
        status=order.status,
        menu_link=order.menu_link,
        menu_link_chay=order.menu_link_chay,
        total_bill=order.total_bill or 0,
        total_bill_chay=order.total_bill_chay or 0,
        shared_cost_per_person=order.shared_cost_per_person or 0,
        shared_cost_per_person_chay=order.shared_cost_per_person_chay or 0,
        note=order.note,
        created_by=order.created_by,
        created_at=order.created_at,
        items=items,
        eater_count=eater_count,
        chay_eater_count=chay_eater_count,
    )


@router.get("", response_model=list[DailyOrderListResponse])
def list_orders(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=30, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """List orders, optionally filtered by date range."""
    query = db.query(DailyOrder)

    if start_date:
        query = query.filter(DailyOrder.order_date >= start_date)
    if end_date:
        query = query.filter(DailyOrder.order_date <= end_date)

    orders = query.order_by(DailyOrder.order_date.desc()).limit(limit).all()

    result = []
    for order in orders:
        eater_count = sum(1 for item in order.items if item.is_eating and not item.is_chay)
        chay_eater_count = sum(1 for item in order.items if item.is_eating and item.is_chay)
        result.append(DailyOrderListResponse(
            id=order.id,
            order_date=order.order_date,
            status=order.status,
            total_bill=order.total_bill or 0,
            total_bill_chay=order.total_bill_chay or 0,
            eater_count=eater_count,
            chay_eater_count=chay_eater_count,
            note=order.note,
            created_at=order.created_at,
        ))
    return result


@router.get("/today", response_model=DailyOrderResponse | None)
def get_today_order(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Get today's order if it exists."""
    from datetime import datetime
    today = datetime.now(VN_TZ).date()
    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.order_date == today)
        .first()
    )
    if not order:
        return None
    return _build_order_response(order)


@router.get("/{order_id}", response_model=DailyOrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Get a specific order with all items."""
    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _build_order_response(order)


@router.post("", response_model=DailyOrderResponse, status_code=201)
def create_order(data: DailyOrderCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Create a new daily order. Auto-creates order items for all active members."""
    existing = db.query(DailyOrder).filter(DailyOrder.order_date == data.order_date).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order for this date already exists")

    order = DailyOrder(
        order_date=data.order_date,
        menu_link=data.menu_link,
        menu_link_chay=data.menu_link_chay,
        note=data.note,
        created_by=data.created_by,
        status="open",
    )
    db.add(order)
    db.flush()  # Get the order ID

    # Auto-create order items for all active members
    active_members = db.query(Member).filter(Member.is_active == True).all()
    for member in active_members:
        item = OrderItem(
            daily_order_id=order.id,
            member_id=member.id,
            is_eating=False,
        )
        db.add(item)

    db.commit()

    # Reload with relationships
    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order.id)
        .first()
    )
    return _build_order_response(order)


@router.put("/{order_id}", response_model=DailyOrderResponse)
def update_order(order_id: int, data: DailyOrderUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Update order details (menu links, notes, etc)."""
    order = db.query(DailyOrder).filter(DailyOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if data.menu_link is not None:
        order.menu_link = data.menu_link
    if data.menu_link_chay is not None:
        order.menu_link_chay = data.menu_link_chay
    if data.total_bill is not None:
        order.total_bill = data.total_bill
    if data.total_bill_chay is not None:
        order.total_bill_chay = data.total_bill_chay
    if data.note is not None:
        order.note = data.note
    if data.status is not None:
        order.status = data.status

    db.commit()

    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    return _build_order_response(order)


@router.post("/{order_id}/lock", response_model=DailyOrderResponse)
def lock_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Lock an order - no more dish selections allowed."""
    order = db.query(DailyOrder).filter(DailyOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is already finalized")

    order.status = "locked"
    db.commit()

    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    return _build_order_response(order)


@router.post("/{order_id}/reopen", response_model=DailyOrderResponse)
def reopen_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Reopen a locked order."""
    order = db.query(DailyOrder).filter(DailyOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "open"
    db.commit()

    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    return _build_order_response(order)


@router.post("/{order_id}/finalize", response_model=DailyOrderResponse)
def finalize_order(order_id: int, data: DailyOrderFinalize, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """
    Finalize the order: set total bill and calculate cost per person.
    This computes and saves how much each member needs to pay.
    """
    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.total_bill = data.total_bill
    order.total_bill_chay = data.total_bill_chay
    order.status = "finalized"

    # Calculate costs
    cost_result = calculate_costs(order, order.items)
    order.shared_cost_per_person = cost_result["shared_cost_per_person"]
    order.shared_cost_per_person_chay = cost_result["shared_cost_per_person_chay"]

    # Update individual item costs
    cost_map = {c["item_id"]: c["total_cost"] for c in cost_result["item_costs"]}
    for item in order.items:
        item.total_cost = cost_map.get(item.id, 0)

    db.commit()

    # Reload
    order = (
        db.query(DailyOrder)
        .options(joinedload(DailyOrder.items).joinedload(OrderItem.member))
        .filter(DailyOrder.id == order_id)
        .first()
    )
    return _build_order_response(order)
