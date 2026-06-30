from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from app.database import get_db, _next_id, _to_ns
from app.core.auth import get_current_user, get_current_admin
from app.schemas import RestaurantCreate, RestaurantUpdate, RestaurantResponse

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


def _res(ns) -> RestaurantResponse:
    return RestaurantResponse(
        id=ns.id,
        name=ns.name,
        link=getattr(ns, "link", None),
        is_active=getattr(ns, "is_active", True),
        be_restaurant_id=getattr(ns, "be_restaurant_id", None),
        be_lat=getattr(ns, "be_lat", None),
        be_lon=getattr(ns, "be_lon", None),
        created_at=ns.created_at,
    )


@router.get("", response_model=list[RestaurantResponse])
def list_restaurants(db=Depends(get_db), _=Depends(get_current_user)):
    items = [_to_ns(s.to_dict()) for s in db.collection("restaurants").where("is_active", "==", True).stream()]
    items.sort(key=lambda r: r.name)
    return [_res(r) for r in items]


@router.get("/last-used", response_model=RestaurantResponse | None)
def get_last_used(db=Depends(get_db), _=Depends(get_current_user)):
    """Return the restaurant used in the most recent finalized or locked order."""
    orders = [s.to_dict() for s in db.collection("daily_orders").stream()]
    orders = [o for o in orders if o.get("restaurant_id")]
    if not orders:
        return None
    orders.sort(key=lambda o: o["order_date"], reverse=True)
    restaurant_id = orders[0]["restaurant_id"]
    doc = db.collection("restaurants").document(str(restaurant_id)).get()
    if not doc.exists:
        return None
    return _res(_to_ns(doc.to_dict()))


@router.post("", response_model=RestaurantResponse, status_code=201)
def create_restaurant(data: RestaurantCreate, db=Depends(get_db), _=Depends(get_current_admin)):
    if list(db.collection("restaurants").where("name", "==", data.name).limit(1).stream()):
        raise HTTPException(status_code=400, detail="Tên quán đã tồn tại")
    new_id = _next_id(db, "restaurants")
    now = datetime.now(timezone.utc)
    doc = {
        "id": new_id, "name": data.name, "link": data.link, "is_active": True, "created_at": now,
        "be_restaurant_id": data.be_restaurant_id,
        "be_lat": data.be_lat,
        "be_lon": data.be_lon,
    }
    db.collection("restaurants").document(str(new_id)).set(doc)
    return _res(_to_ns(doc))


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
def update_restaurant(restaurant_id: int, data: RestaurantUpdate, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("restaurants").document(str(restaurant_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Quán không tồn tại")
    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.link is not None:
        updates["link"] = data.link
    if data.is_active is not None:
        updates["is_active"] = data.is_active
    if data.be_restaurant_id is not None:
        updates["be_restaurant_id"] = data.be_restaurant_id
    if data.be_lat is not None:
        updates["be_lat"] = data.be_lat
    if data.be_lon is not None:
        updates["be_lon"] = data.be_lon
    if updates:
        ref.update(updates)
    return _res(_to_ns(ref.get().to_dict()))


@router.delete("/{restaurant_id}", status_code=204)
def delete_restaurant(restaurant_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("restaurants").document(str(restaurant_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Quán không tồn tại")
    ref.update({"is_active": False})
