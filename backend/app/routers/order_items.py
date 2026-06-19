from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import OrderItem, DailyOrder, Member
from app.schemas import (
    OrderItemCreate, OrderItemUpdate, OrderItemExtraUpdate, OrderItemResponse,
)
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/orders/{order_id}/items", tags=["order-items"])


def _get_order_or_404(order_id: int, db: Session) -> DailyOrder:
    order = db.query(DailyOrder).filter(DailyOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _item_response(item: OrderItem) -> OrderItemResponse:
    return OrderItemResponse(
        id=item.id,
        daily_order_id=item.daily_order_id,
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
        created_at=item.created_at,
    )


@router.get("", response_model=list[OrderItemResponse])
def list_items(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """List all items for an order."""
    _get_order_or_404(order_id, db)
    items = (
        db.query(OrderItem)
        .options(joinedload(OrderItem.member))
        .filter(OrderItem.daily_order_id == order_id)
        .all()
    )
    return [_item_response(item) for item in items]


@router.post("", response_model=OrderItemResponse, status_code=201)
def create_item(order_id: int, data: OrderItemCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Submit a dish selection for a member."""
    order = _get_order_or_404(order_id, db)
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    # Check member exists
    member = db.query(Member).filter(Member.id == data.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Check for existing item
    existing = (
        db.query(OrderItem)
        .filter(OrderItem.daily_order_id == order_id, OrderItem.member_id == data.member_id)
        .first()
    )

    if existing:
        # Update existing item instead of creating new
        existing.dish_name = data.dish_name
        existing.dish_name_chay = data.dish_name_chay
        existing.note = data.note
        existing.is_chay = data.is_chay
        existing.is_eating = bool(data.dish_name or data.dish_name_chay)
        db.commit()
        db.refresh(existing)
        return _item_response(existing)

    item = OrderItem(
        daily_order_id=order_id,
        member_id=data.member_id,
        dish_name=data.dish_name,
        dish_name_chay=data.dish_name_chay,
        note=data.note,
        is_chay=data.is_chay,
        is_eating=bool(data.dish_name or data.dish_name_chay),
    )
    db.add(item)
    db.commit()

    item = (
        db.query(OrderItem)
        .options(joinedload(OrderItem.member))
        .filter(OrderItem.id == item.id)
        .first()
    )
    return _item_response(item)


@router.put("/{item_id}", response_model=OrderItemResponse)
def update_item(order_id: int, item_id: int, data: OrderItemUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Update a dish selection."""
    order = _get_order_or_404(order_id, db)
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    item = (
        db.query(OrderItem)
        .options(joinedload(OrderItem.member))
        .filter(OrderItem.id == item_id, OrderItem.daily_order_id == order_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    if data.dish_name is not None:
        item.dish_name = data.dish_name
    if data.dish_name_chay is not None:
        item.dish_name_chay = data.dish_name_chay
    if data.note is not None:
        item.note = data.note
    if data.is_chay is not None:
        item.is_chay = data.is_chay

    item.is_eating = bool(item.dish_name or item.dish_name_chay)

    db.commit()
    db.refresh(item)
    return _item_response(item)


@router.put("/{item_id}/extra", response_model=OrderItemResponse)
def update_item_extra(
    order_id: int, item_id: int, data: OrderItemExtraUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    """Admin: set extra item cost for a member."""
    item = (
        db.query(OrderItem)
        .options(joinedload(OrderItem.member))
        .filter(OrderItem.id == item_id, OrderItem.daily_order_id == order_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    item.extra_item_description = data.extra_item_description
    item.extra_item_cost = data.extra_item_cost

    db.commit()
    db.refresh(item)
    return _item_response(item)


@router.delete("/{item_id}", status_code=204)
def cancel_item(order_id: int, item_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Cancel a dish selection (set to not eating)."""
    order = _get_order_or_404(order_id, db)
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    item = (
        db.query(OrderItem)
        .filter(OrderItem.id == item_id, OrderItem.daily_order_id == order_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    # Don't delete, just reset
    item.dish_name = None
    item.dish_name_chay = None
    item.note = None
    item.is_eating = False
    item.is_chay = False
    item.extra_item_description = None
    item.extra_item_cost = 0

    db.commit()
