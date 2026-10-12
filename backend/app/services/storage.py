"""Firebase Storage helpers for restaurant menu images.

Files are served through Firebase download-token URLs, so the bucket can stay
private: anyone with the URL can view the image, nobody can list the bucket.
"""

import uuid
from urllib.parse import quote

from app.core.config import settings

ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
MAX_BYTES = 5 * 1024 * 1024


class StorageNotConfigured(RuntimeError):
    pass


def _bucket():
    from firebase_admin import storage

    if not settings.storage_bucket:
        raise StorageNotConfigured("FIREBASE_STORAGE_BUCKET chưa được cấu hình")
    return storage.bucket(settings.storage_bucket)


def upload_menu_image(restaurant_id: int, data: bytes, content_type: str) -> dict:
    """Upload one image and return {path, url}."""
    bucket = _bucket()
    path = f"menu-images/{restaurant_id}/{uuid.uuid4().hex}.{ALLOWED_TYPES[content_type]}"
    token = uuid.uuid4().hex
    blob = bucket.blob(path)
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    blob.cache_control = "public, max-age=31536000"
    blob.upload_from_string(data, content_type=content_type)
    url = (f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/"
           f"{quote(path, safe='')}?alt=media&token={token}")
    return {"path": path, "url": url}


def delete_object(path: str) -> None:
    blob = _bucket().blob(path)
    if blob.exists():
        blob.delete()
