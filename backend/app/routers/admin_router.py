"""Admin endpoints: Excel import, member name mapping."""

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
import io

from app.database import get_db
from app.core.auth import get_current_admin
from app.services.excel_importer import preview_import, commit_import

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/members/name-map")
def get_member_name_map(db=Depends(get_db), _=Depends(get_current_admin)):
    members = [s.to_dict() for s in db.collection("members").where("is_active", "==", True).stream()]
    return [{"id": m["id"], "name": m["name"]} for m in members]


@router.post("/import/preview")
async def import_preview(
    file: UploadFile = File(...),
    db=Depends(get_db),
    _=Depends(get_current_admin),
):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .xlsx")
    content = await file.read()
    return preview_import(io.BytesIO(content))


@router.post("/import/commit")
async def import_commit(
    file: UploadFile = File(...),
    member_name_map: dict = {},
    db=Depends(get_db),
    _=Depends(get_current_admin),
):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .xlsx")
    content = await file.read()
    return commit_import(io.BytesIO(content), member_name_map, db)
