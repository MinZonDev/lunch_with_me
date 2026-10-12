"""Entry point for Cloud Scheduler: POST /api/internal/cron/tick every minute.

Protected by a shared secret (CRON_SECRET) sent in the X-Cron-Secret header.
When CRON_SECRET is not configured the endpoint doesn't exist (404).
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.database import get_db
from app.services.cron import run_tick

router = APIRouter(prefix="/api/internal/cron", tags=["internal"], include_in_schema=False)


@router.post("/tick")
def tick(x_cron_secret: str | None = Header(default=None), db=Depends(get_db)):
    if not settings.cron_secret:
        raise HTTPException(status_code=404)
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ran": run_tick(db)}
