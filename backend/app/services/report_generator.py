"""Generate weekly/monthly reports and CSV exports."""

import csv
import io
from datetime import date, timedelta


def _get_week_range(year: int, week: int):
    jan4 = date(year, 1, 4)
    start = jan4 - timedelta(days=jan4.isoweekday() - 1) + timedelta(weeks=week - 1)
    end = start + timedelta(days=6)
    return start, end


def generate_report(db, start: date, end: date, period_label: str) -> dict:
    """Build report data between two dates (inclusive)."""
    start_str, end_str = str(start), str(end)

    all_orders = [s.to_dict() for s in db.collection("daily_orders").where("status", "==", "finalized").stream()]
    orders = [o for o in all_orders if start_str <= o["order_date"] <= end_str]
    orders.sort(key=lambda o: o["order_date"])
    order_ids = {o["id"] for o in orders}

    if not order_ids:
        return {"period_label": period_label, "days": [], "members": [], "grand_total": 0}

    all_items = [s.to_dict() for s in db.collection("order_items").where("is_eating", "==", True).stream()]
    items = [i for i in all_items if i["daily_order_id"] in order_ids]

    # Member name cache
    member_names: dict[int, str] = {}
    for item in items:
        mid = item["member_id"]
        if mid not in member_names:
            m_doc = db.collection("members").document(str(mid)).get()
            member_names[mid] = m_doc.to_dict().get("name", "?") if m_doc.exists else "?"

    # Per member aggregates
    member_data: dict[int, dict] = {}
    for item in items:
        mid = item["member_id"]
        if mid not in member_data:
            member_data[mid] = {"member_id": mid, "member_name": member_names[mid], "days_eaten": 0, "total_cost": 0}
        member_data[mid]["days_eaten"] += 1
        member_data[mid]["total_cost"] += item.get("total_cost", 0) or 0

    # Per day summary
    order_id_to_items = {}
    for item in [s.to_dict() for s in db.collection("order_items").stream()]:
        oid = item["daily_order_id"]
        order_id_to_items.setdefault(oid, []).append(item)

    days = []
    grand_total = 0
    for o in orders:
        eaters = sum(1 for i in order_id_to_items.get(o["id"], []) if i.get("is_eating"))
        bill = (o.get("total_bill") or 0) + (o.get("total_bill_chay") or 0)
        grand_total += bill
        days.append({
            "order_date": date.fromisoformat(o["order_date"]),
            "total_bill": bill,
            "eater_count": eaters,
        })

    return {
        "period_label": period_label,
        "days": days,
        "members": sorted(member_data.values(), key=lambda x: x["member_name"]),
        "grand_total": grand_total,
    }


def weekly_report(db, year: int, week: int) -> dict:
    start, end = _get_week_range(year, week)
    return generate_report(db, start, end, f"Tuần {week}/{year} ({start.strftime('%d/%m')} – {end.strftime('%d/%m/%Y')})")


def monthly_report(db, year: int, month: int) -> dict:
    import calendar
    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return generate_report(db, start, end, f"Tháng {month}/{year}")


def export_csv(report: dict) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([report["period_label"]])
    writer.writerow([])
    writer.writerow(["Thành viên", "Số ngày ăn", "Tổng chi phí (k)"])
    for m in report["members"]:
        writer.writerow([m["member_name"], m["days_eaten"], m["total_cost"]])
    writer.writerow(["TỔNG", "", report["grand_total"]])
    writer.writerow([])
    writer.writerow(["Ngày", "Tổng bill (k)", "Số người"])
    for d in report["days"]:
        writer.writerow([d["order_date"].strftime("%d/%m/%Y"), d["total_bill"], d["eater_count"]])

    return output.getvalue().encode("utf-8-sig")
