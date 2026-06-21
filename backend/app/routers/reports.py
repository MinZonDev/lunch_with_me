from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import io

from app.database import get_db
from app.schemas import ReportResponse, ReportDayRow, ReportMemberRow
from app.services.report_generator import weekly_report, monthly_report, export_csv
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _to_response(data: dict) -> ReportResponse:
    return ReportResponse(
        period_label=data["period_label"],
        days=[ReportDayRow(**d) for d in data["days"]],
        members=[ReportMemberRow(**m) for m in data["members"]],
        grand_total=data["grand_total"],
    )


@router.get("/weekly", response_model=ReportResponse)
def get_weekly_report(
    year: int = Query(...),
    week: int = Query(..., ge=1, le=53),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    return _to_response(weekly_report(db, year, week))


@router.get("/monthly", response_model=ReportResponse)
def get_monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    return _to_response(monthly_report(db, year, month))


@router.get("/weekly/export")
def export_weekly_csv(
    year: int = Query(...),
    week: int = Query(..., ge=1, le=53),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    data = weekly_report(db, year, week)
    csv_bytes = export_csv(data)
    filename = f"bao-cao-tuan-{week}-{year}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/export")
def export_monthly_csv(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    data = monthly_report(db, year, month)
    csv_bytes = export_csv(data)
    filename = f"bao-cao-thang-{month:02d}-{year}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
