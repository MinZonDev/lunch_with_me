from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from datetime import datetime, timezone

from app.database import get_db, _next_id, _to_ns
from app.core.auth import get_current_user, get_current_admin
from app.schemas import RestaurantCreate, RestaurantUpdate, RestaurantResponse, MenuImage
from app.services import storage

MAX_MENU_IMAGES = 20

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
        menu_images=[MenuImage(**img) for img in (getattr(ns, "menu_images", None) or [])],
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
    from google.cloud.firestore import Query as FsQuery

    # Recent orders only; most days have a restaurant, so 20 is plenty
    recent = (db.collection("daily_orders")
              .order_by("order_date", direction=FsQuery.DESCENDING)
              .select(["restaurant_id"]).limit(20).stream())
    restaurant_id = next((s.to_dict().get("restaurant_id") for s in recent if s.to_dict().get("restaurant_id")), None)
    if not restaurant_id:
        return None
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


@router.post("/{restaurant_id}/menu-images", response_model=RestaurantResponse)
async def upload_menu_images(
    restaurant_id: int,
    files: list[UploadFile] = File(...),
    db=Depends(get_db),
    _=Depends(get_current_admin),
):
    """Upload one or more menu photos for a restaurant (JPEG/PNG/WebP/GIF, ≤ 5MB each)."""
    ref = db.collection("restaurants").document(str(restaurant_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Quán không tồn tại")
    images = list(doc.to_dict().get("menu_images") or [])
    if len(images) + len(files) > MAX_MENU_IMAGES:
        raise HTTPException(status_code=400, detail=f"Mỗi quán tối đa {MAX_MENU_IMAGES} ảnh menu")

    # Validate everything before uploading anything
    payloads = []
    for f in files:
        if f.content_type not in storage.ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"{f.filename}: chỉ hỗ trợ ảnh JPG, PNG, WebP, GIF")
        data = await f.read()
        if len(data) > storage.MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"{f.filename}: ảnh vượt quá 5MB")
        if not data:
            raise HTTPException(status_code=400, detail=f"{f.filename}: file rỗng")
        payloads.append((data, f.content_type))

    try:
        for data, content_type in payloads:
            images.append(storage.upload_menu_image(restaurant_id, data, content_type))
    except storage.StorageNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        # Keep whatever made it to storage referenced, even if a later upload failed
        ref.update({"menu_images": images})
    return _res(_to_ns(ref.get().to_dict()))


@router.delete("/{restaurant_id}/menu-images", response_model=RestaurantResponse)
def delete_menu_image(
    restaurant_id: int,
    path: str = Query(..., description="path của ảnh trong menu_images"),
    db=Depends(get_db),
    _=Depends(get_current_admin),
):
    ref = db.collection("restaurants").document(str(restaurant_id))
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Quán không tồn tại")
    images = list(doc.to_dict().get("menu_images") or [])
    remaining = [img for img in images if img["path"] != path]
    if len(remaining) == len(images):
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    ref.update({"menu_images": remaining})
    try:
        storage.delete_object(path)
    except Exception:  # the reference is gone either way; an orphaned file is harmless
        pass
    return _res(_to_ns(ref.get().to_dict()))
