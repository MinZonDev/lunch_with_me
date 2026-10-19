import logging
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from types import SimpleNamespace

from app.database import get_db, _next_id, _to_ns, _doc_ns
from app.schemas import (
    OrderItemCreate, OrderItemUpdate, OrderItemExtraUpdate, OrderItemExceptionUpdate, OrderItemResponse,
)
from app.core.auth import get_current_user, get_current_admin, get_order_manager
from app.services.delegation import has_active_delegation
from app.services.blacklist import is_blocked
from app.services.ledger import member_names

logger = logging.getLogger("lwm.order_items")

router = APIRouter(prefix="/api/orders/{order_id}/items", tags=["order-items"])


def _get_order_ns(db, order_id: int):
    results = list(db.collection("daily_orders").where("id", "==", order_id).limit(1).stream())
    if not results:
        return None, None
    doc = results[0]
    return doc.reference, _to_ns(doc.to_dict())


def _item_response(item, member_name: str) -> OrderItemResponse:
    # Backward compat: old items may have dish_name_chay instead of dish_name
    dish = getattr(item, "dish_name", None) or getattr(item, "dish_name_chay", None)
    return OrderItemResponse(
        id=item.id,
        daily_order_id=item.daily_order_id,
        member_id=item.member_id,
        member_name=member_name,
        dish_name=dish,
        note=getattr(item, "note", None),
        is_eating=item.is_eating,
        extra_item_description=getattr(item, "extra_item_description", None),
        extra_item_cost=getattr(item, "extra_item_cost", 0) or 0,
        is_exception=getattr(item, "is_exception", False) or False,
        exception_amount=getattr(item, "exception_amount", 0) or 0,
        total_cost=getattr(item, "total_cost", 0) or 0,
        created_at=item.created_at,
    )


def _get_member_name(db, member_id: int) -> str:
    doc = db.collection("members").document(str(member_id)).get()
    return doc.to_dict().get("name", "?") if doc.exists else "?"


def _check_order_permission(db, current_user, target_member_id: int) -> None:
    """Raise 403 if current_user cannot act on behalf of target_member_id.

    Admin may always act. Anyone else is refused when the target is
    blacklisted — the member themself and their delegates alike.
    """
    if getattr(current_user, "role", None) == "admin":
        return
    if is_blocked(db, target_member_id):
        raise HTTPException(
            status_code=403,
            detail="Thành viên này đang nợ tiền và bị khoá đặt cơm. Vui lòng thanh toán để được mở lại.",
        )
    my_member_id = getattr(current_user, "member_id", None)
    if my_member_id == target_member_id:
        return
    if not my_member_id or not has_active_delegation(db, target_member_id, my_member_id):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền đặt món cho thành viên này. Yêu cầu ủy quyền từ họ trước.",
        )
    logger.info(
        "Member %s ordering on behalf of member %s (delegation active)",
        my_member_id,
        target_member_id,
    )


@router.get("", response_model=list[OrderItemResponse])
def list_items(order_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    _, order = _get_order_ns(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    docs = [s.to_dict() for s in db.collection("order_items").where("daily_order_id", "==", order_id).stream()]
    names = member_names(db, {d["member_id"] for d in docs})
    return [_item_response(SimpleNamespace(**d), names.get(d["member_id"], "?")) for d in docs]


@router.post("", response_model=OrderItemResponse, status_code=201)
def create_item(
    order_id: int,
    data: OrderItemCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    _, order = _get_order_ns(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    _check_order_permission(db, current_user, data.member_id)

    m_doc = db.collection("members").document(str(data.member_id)).get()
    if not m_doc.exists:
        raise HTTPException(status_code=404, detail="Member not found")
    member_name = m_doc.to_dict().get("name", "?")

    is_eating = bool(data.dish_name)

    existing_snap = list(
        db.collection("order_items")
        .where("daily_order_id", "==", order_id)
        .where("member_id", "==", data.member_id)
        .limit(1)
        .stream()
    )
    if existing_snap:
        ref = existing_snap[0].reference
        updates = {
            "dish_name": data.dish_name,
            "note": data.note,
            "is_eating": is_eating,
        }
        ref.update(updates)
        item = SimpleNamespace(**{**existing_snap[0].to_dict(), **updates})
        logger.info("Updated item for member %d in order %d", data.member_id, order_id)
        return _item_response(item, member_name)

    item_id = _next_id(db, "order_items")
    doc_data = {
        "id": item_id,
        "daily_order_id": order_id,
        "order_date": str(order.order_date),
        "member_id": data.member_id,
        "dish_name": data.dish_name,
        "note": data.note,
        "is_eating": is_eating,
        "extra_item_description": None,
        "extra_item_cost": 0,
        "total_cost": 0,
        "created_at": datetime.now(timezone.utc),
    }
    db.collection("order_items").document(str(item_id)).set(doc_data)
    logger.info("Created item for member %d in order %d", data.member_id, order_id)
    return _item_response(SimpleNamespace(**doc_data), member_name)


@router.put("/{item_id}", response_model=OrderItemResponse)
def update_item(
    order_id: int,
    item_id: int,
    data: OrderItemUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    _, order = _get_order_ns(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    ref = db.collection("order_items").document(str(item_id))
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("daily_order_id") != order_id:
        raise HTTPException(status_code=404, detail="Order item not found")

    d = doc.to_dict()
    _check_order_permission(db, current_user, d["member_id"])

    updates = {}
    if data.dish_name is not None:
        updates["dish_name"] = data.dish_name
        d["dish_name"] = data.dish_name
    if data.note is not None:
        updates["note"] = data.note
        d["note"] = data.note

    updates["is_eating"] = bool(d.get("dish_name") or d.get("dish_name_chay"))
    d["is_eating"] = updates["is_eating"]
    ref.update(updates)

    member_name = _get_member_name(db, d["member_id"])
    logger.info("Updated item %d for member %d", item_id, d["member_id"])
    return _item_response(SimpleNamespace(**d), member_name)


@router.put("/{item_id}/extra", response_model=OrderItemResponse)
def update_item_extra(
    order_id: int,
    item_id: int,
    data: OrderItemExtraUpdate,
    db=Depends(get_db),
    _=Depends(get_current_admin),
):
    ref = db.collection("order_items").document(str(item_id))
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("daily_order_id") != order_id:
        raise HTTPException(status_code=404, detail="Order item not found")

    updates = {
        "extra_item_description": data.extra_item_description,
        "extra_item_cost": data.extra_item_cost,
    }
    ref.update(updates)
    logger.info("Admin set extra for item %d: %s (%dk)", item_id, data.extra_item_description, data.extra_item_cost)
    return _after_cost_edit(db, order_id, ref)


@router.put("/{item_id}/exception", response_model=OrderItemResponse)
def update_item_exception(
    order_id: int,
    item_id: int,
    data: OrderItemExceptionUpdate,
    db=Depends(get_db),
    _=Depends(get_order_manager),
):
    """Đánh dấu ngoại lệ: người này trả đúng số tiền riêng, phần còn lại chia cho người khác."""
    ref = db.collection("order_items").document(str(item_id))
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("daily_order_id") != order_id:
        raise HTTPException(status_code=404, detail="Order item not found")
    if data.is_exception and not doc.to_dict().get("is_eating"):
        raise HTTPException(status_code=400, detail="Thành viên này chưa đặt món")

    ref.update({
        "is_exception": data.is_exception,
        "exception_amount": data.exception_amount if data.is_exception else 0,
    })
    logger.info("Set exception for item %d: %s (%dk)", item_id, data.is_exception, data.exception_amount)
    return _after_cost_edit(db, order_id, ref, rollback=doc.to_dict())


def _after_cost_edit(db, order_id: int, item_ref, rollback: dict | None = None) -> OrderItemResponse:
    """Re-split the bill if the order is already finalized, then return the fresh item."""
    from app.routers.orders import recalculate_costs

    order_ref, order = _get_order_ns(db, order_id)
    if order and order.status == "finalized":
        try:
            recalculate_costs(db, order_ref, order)
        except HTTPException:
            if rollback is not None:
                item_ref.update({k: rollback.get(k) for k in ("is_exception", "exception_amount")})
            raise
    d = item_ref.get().to_dict()
    return _item_response(SimpleNamespace(**d), _get_member_name(db, d["member_id"]))


@router.delete("/{item_id}", status_code=204)
def cancel_item(
    order_id: int,
    item_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    _, order = _get_order_ns(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "finalized":
        raise HTTPException(status_code=400, detail="Order is finalized, cannot modify")

    ref = db.collection("order_items").document(str(item_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Order item not found")

    _check_order_permission(db, current_user, doc.to_dict()["member_id"])

    ref.update({
        "dish_name": None,
        "note": None,
        "is_eating": False,
        "extra_item_description": None,
        "extra_item_cost": 0,
        "is_exception": False,
        "exception_amount": 0,
    })
    logger.info("Cancelled item %d in order %d", item_id, order_id)
