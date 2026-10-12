"""Cron tick: which jobs run when, once per period, and the secret-protected endpoint."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import cron

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def vn(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=VN)


@pytest.fixture()
def calls(monkeypatch):
    import app.services.pickup as pickup
    import app.services.scheduler as scheduler
    log = []
    for name in ("_job_auto_lock_past_deadline", "_job_monthly_statement", "_job_debt_reminder"):
        monkeypatch.setattr(scheduler, name, lambda _n=name: log.append(_n))
    monkeypatch.setattr(pickup, "run_due", lambda db, now: log.append("pickup") or 0)
    return log


def _reminder(db, **cfg):
    db.collection("_settings").document("debt_reminder").set(
        {"enabled": True, "schedule": "weekly", "day_of_week": "mon", "time": "09:00", **cfg})


class TestSchedule:
    def test_pickup_only_during_day(self, db, calls):
        cron.run_tick(db, vn(2026, 10, 13, 5, 59))
        cron.run_tick(db, vn(2026, 10, 13, 23, 0))
        assert "pickup" not in calls
        cron.run_tick(db, vn(2026, 10, 13, 11, 31))
        assert calls.count("pickup") == 1

    def test_auto_lock_once_per_day_after_1205(self, db, calls):
        cron.run_tick(db, vn(2026, 10, 13, 12, 4))
        assert "_job_auto_lock_past_deadline" not in calls
        cron.run_tick(db, vn(2026, 10, 13, 12, 5))
        cron.run_tick(db, vn(2026, 10, 13, 12, 6))
        cron.run_tick(db, vn(2026, 10, 13, 18, 0))
        assert calls.count("_job_auto_lock_past_deadline") == 1
        cron.run_tick(db, vn(2026, 10, 14, 12, 30))  # next day, late tick still catches up
        assert calls.count("_job_auto_lock_past_deadline") == 2

    def test_monthly_statement_first_of_month(self, db, calls):
        cron.run_tick(db, vn(2026, 11, 1, 7, 59))
        cron.run_tick(db, vn(2026, 11, 2, 8, 0))
        assert "_job_monthly_statement" not in calls
        cron.run_tick(db, vn(2026, 11, 1, 8, 0))
        cron.run_tick(db, vn(2026, 11, 1, 9, 0))
        assert calls.count("_job_monthly_statement") == 1

    def test_debt_reminder_weekly(self, db, calls):
        _reminder(db)
        cron.run_tick(db, vn(2026, 10, 12, 8, 59))   # Monday, too early
        cron.run_tick(db, vn(2026, 10, 13, 9, 0))    # Tuesday
        assert "_job_debt_reminder" not in calls
        cron.run_tick(db, vn(2026, 10, 12, 9, 0))
        cron.run_tick(db, vn(2026, 10, 12, 9, 1))
        assert calls.count("_job_debt_reminder") == 1

    def test_debt_reminder_daily_and_disabled(self, db, calls):
        _reminder(db, schedule="daily", time="10:30")
        cron.run_tick(db, vn(2026, 10, 15, 10, 30))
        cron.run_tick(db, vn(2026, 10, 16, 10, 30))
        assert calls.count("_job_debt_reminder") == 2
        _reminder(db, enabled=False, schedule="daily")
        cron.run_tick(db, vn(2026, 10, 17, 10, 30))
        assert calls.count("_job_debt_reminder") == 2

    def test_debt_reminder_biweekly_odd_iso_weeks(self, db, calls):
        _reminder(db, schedule="biweekly")
        cron.run_tick(db, vn(2026, 10, 12, 9, 0))   # ISO week 42 (even): skip
        assert "_job_debt_reminder" not in calls
        cron.run_tick(db, vn(2026, 10, 19, 9, 0))   # week 43 (odd): run
        assert calls.count("_job_debt_reminder") == 1

    def test_settings_change_applies_without_restart(self, db, calls):
        _reminder(db, schedule="daily", time="15:00")
        cron.run_tick(db, vn(2026, 10, 15, 14, 0))
        _reminder(db, schedule="daily", time="13:00")
        cron.run_tick(db, vn(2026, 10, 15, 14, 1))
        assert calls.count("_job_debt_reminder") == 1

    def test_failing_job_does_not_block_others(self, db, calls, monkeypatch):
        import app.services.scheduler as scheduler

        def boom():
            raise RuntimeError("smtp down")
        monkeypatch.setattr(scheduler, "_job_auto_lock_past_deadline", boom)
        ran = cron.run_tick(db, vn(2026, 11, 1, 12, 30))
        assert "monthly_statement" in ran and "auto_lock" not in ran


class TestEndpoint:
    def test_disabled_without_secret(self, client, monkeypatch, calls):
        monkeypatch.setattr(cron_router_settings(), "cron_secret", "")
        assert client.post("/api/internal/cron/tick", headers={"X-Cron-Secret": "x"}).status_code == 404

    def test_wrong_or_missing_secret(self, client, monkeypatch, calls):
        monkeypatch.setattr(cron_router_settings(), "cron_secret", "s3cret")
        assert client.post("/api/internal/cron/tick").status_code == 403
        assert client.post("/api/internal/cron/tick", headers={"X-Cron-Secret": "nope"}).status_code == 403
        assert calls == []

    def test_runs_tick(self, client, monkeypatch, calls):
        monkeypatch.setattr(cron_router_settings(), "cron_secret", "s3cret")
        res = client.post("/api/internal/cron/tick", headers={"X-Cron-Secret": "s3cret"})
        assert res.status_code == 200 and isinstance(res.json()["ran"], list)


def cron_router_settings():
    from app.routers import cron as cron_router
    return cron_router.settings
