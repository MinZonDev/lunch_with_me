import logging
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from types import SimpleNamespace

from app.database import get_db, _next_id, _to_ns, _doc_ns
from app.schemas import (
    OrderItemCreate, OrderItemUpdate, OrderItemExtraUpdate, OrderItemResponse,
)
from app.core.auth import get_current_user, get_current_admin
from app.services.delegation import has_active_delegation

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
        total_cost=getattr(item, "total_cost", 0) or 0,
        created_at=item.created_at,
    )


def _get_member_name(db, member_id: int) -> str:
    doc = db.collection("members").document(str(member_id)).get()
    return doc.to_dict().get("name", "?") if doc.exists else "?"


def _check_order_permission(db, current_user, target_member_id: int) -> None:
    """Raise 403 if current_user cannot act on behalf of target_member_id."""
    if getattr(current_user, "role", None) == "admin":
        return
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

    members_cache: dict[int, str] = {}
    result = []
    for snap in db.collection("order_items").where("daily_order_id", "==", order_id).stream():
        d = snap.to_dict()
        mid = d["member_id"]
        if mid not in members_cache:
            members_cache[mid] = _get_member_name(db, mid)
        result.append(_item_response(SimpleNamespace(**d), members_cache[mid]))
    return result


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
    d = {**doc.to_dict(), **updates}
    member_name = _get_member_name(db, d["member_id"])
    logger.info("Admin set extra for item %d: %s (%dk)", item_id, data.extra_item_description, data.extra_item_cost)
    return _item_response(SimpleNamespace(**d), member_name)


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
    })
    logger.info("Cancelled item %d in order %d", item_id, order_id)
