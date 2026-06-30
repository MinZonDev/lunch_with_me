import base64
import json
import logging
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/be", tags=["be-menu"])
logger = logging.getLogger("lwm.be_menu")

_BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,vi;q=0.8",
    "app_version": "11325",
    "content-type": "application/json",
    "origin": "https://food.be.com.vn",
    "referer": "https://food.be.com.vn/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
    ),
}

_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_be_token() -> str:
    now = datetime.now(timezone.utc).timestamp()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 120:
        return _token_cache["token"]

    res = requests.post(
        "https://gw.be.com.vn/api/v1/be-delivery-gateway/api/v1/user/guest",
        json={"locale": "vi", "latitude": None, "longitude": None},
        headers={**_BASE_HEADERS, "access_token": "PENDING"},
        timeout=10,
    )
    res.raise_for_status()
    token = res.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Không lấy được token từ Be")

    # Decode JWT expiry without verification
    try:
        padding = "=" * (-len(token.split(".")[1]) % 4)
        payload = json.loads(base64.b64decode(token.split(".")[1] + padding))
        exp = float(payload.get("exp", now + 86400))
    except Exception:
        exp = now + 86400

    _token_cache["token"] = token
    _token_cache["expires_at"] = exp
    logger.info("Got new Be token, expires in %.0fs", exp - now)
    return token


@router.get("/menu/{restaurant_id}")
def get_be_menu(restaurant_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Lấy danh sách món ăn từ Be cho một quán đã cấu hình be_restaurant_id."""
    doc = db.collection("restaurants").document(str(restaurant_id)).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Quán không tồn tại")

    r = doc.to_dict()
    be_id = r.get("be_restaurant_id")
    if not be_id:
        raise HTTPException(status_code=404, detail="Quán chưa cấu hình Be restaurant ID")

    be_lat = r.get("be_lat") or 10.77253621500006
    be_lon = r.get("be_lon") or 106.69798153800008

    try:
        token = _get_be_token()
        res = requests.post(
            "https://gw.be.com.vn/api/v1/be-marketplace/web/restaurant/detail",
            json={"restaurant_id": str(be_id), "latitude": be_lat, "longitude": be_lon},
            headers={**_BASE_HEADERS, "authorization": token},
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Be API error: %s", e)
        raise HTTPException(status_code=502, detail="Không thể lấy menu từ Be")

    categories = data.get("data", {}).get("categories", [])
    restaurant_info = data.get("data", {}).get("restaurant_info", {})

    items = []
    for cat in categories:
        if not cat.get("category_active"):
            continue
        for item in cat.get("items", []):
            if item.get("is_active") != 1:
                continue
            items.append({
                "id": item["restaurant_item_id"],
                "name": item["item_name"].strip(),
                "price": item["price"],
                "price_display": item.get("display_price", ""),
                "category": cat["category_name"],
                "image": item.get("item_image_compressed_web") or item.get("item_image_compressed") or "",
                "order_count": item.get("order_count", 0),
                "is_best_seller": any(t.get("tag") == "top_highest_order" for t in item.get("tags", [])),
            })

    items.sort(key=lambda x: x["order_count"], reverse=True)

    return {
        "restaurant_name": restaurant_info.get("name") or r["name"],
        "items": items,
    }
