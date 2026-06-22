'use client';

import { useState, useCallback, useMemo } from 'react';
import { getToken } from '@/lib/auth';
import { formatMoney } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchWithAuth(url) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function getISOWeek(d) {
  const date = new Date(d);
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  const week1 = new Date(date.getFullYear(), 0, 4);
  return Math.round(((date - week1) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7) + 1;
}

// Mirrors backend _get_week_range (ISO week, Monday start) so we can show the
// date range to the user before they even fetch the report.
function getWeekRange(year, week) {
  const jan4 = new Date(year, 0, 4);
  const jan4Offset = (jan4.getDay() + 6) % 7; // Monday = 0
  const start = new Date(jan4);
  start.setDate(jan4.getDate() - jan4Offset + (week - 1) * 7);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return [start, end];
}

function fmtShort(d) {
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
}

export default function ReportsPage() {
  const now = new Date();
  const [mode, setMode] = useState('monthly');
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [week, setWeek] = useState(getISOWeek(now));
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [weekStart, weekEnd] = useMemo(() => getWeekRange(year, week), [year, week]);

  const fetchReport = useCallback(async () => {
    setLoading(true); setError(''); setReport(null);
    try {
      const url = mode === 'monthly'
        ? `${API_BASE}/api/reports/monthly?year=${year}&month=${month}`
        : `${API_BASE}/api/reports/weekly?year=${year}&week=${week}`;
      const data = await fetchWithAuth(url);
      setReport(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [mode, year, month, week]);

  const handleExport = async () => {
    const url = mode === 'monthly'
      ? `${API_BASE}/api/reports/monthly/export?year=${year}&month=${month}`
      : `${API_BASE}/api/reports/weekly/export?year=${year}&week=${week}`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = res.headers.get('Content-Disposition')?.split('filename="')[1]?.replace('"', '') || 'report.csv';
    a.click();
  };

  const handleWeekInput = (e) => {
    const val = e.target.value; // "YYYY-Www"
    const m = /^(\d{4})-W(\d{2})$/.exec(val);
    if (!m) return;
    setYear(Number(m[1]));
    setWeek(Number(m[2]));
  };

  const shiftWeek = (delta) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + delta * 7);
    setYear(d.getFullYear());
    setWeek(getISOWeek(d));
  };

  const maxDayBill = report ? Math.max(1, ...report.days.map(d => d.total_bill)) : 1;
  const topMembers = report ? [...report.members].sort((a, b) => b.total_cost - a.total_cost) : [];
  const maxMemberCost = report ? Math.max(1, ...topMembers.map(m => m.total_cost)) : 1;
  const operatingDays = report ? report.days.length : 0;
  const avgPerDay = operatingDays ? Math.round(report.grand_total / operatingDays) : 0;
  const totalEaterDays = report ? report.members.reduce((s, m) => s + m.days_eaten, 0) : 0;

  return (
    <>
      <div className="page-header">
        <h1>📊 Báo Cáo</h1>
        <p>Thống kê chi phí theo tuần / tháng, xuất CSV</p>
      </div>

      {/* Controls */}
      <div className="card mb-24">
        <div className="flex gap-12 items-end" style={{ flexWrap: 'wrap' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Loại</label>
            <div className="flex gap-8">
              <button className={`btn btn-sm ${mode === 'monthly' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setMode('monthly')}>📅 Tháng</button>
              <button className={`btn btn-sm ${mode === 'weekly' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setMode('weekly')}>📆 Tuần</button>
            </div>
          </div>

          {mode === 'monthly' ? (
            <>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Năm</label>
                <select className="form-select" value={year} onChange={e => setYear(Number(e.target.value))}>
                  {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Tháng</label>
                <select className="form-select" value={month} onChange={e => setMonth(Number(e.target.value))}>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>Tháng {m}</option>)}
                </select>
              </div>
            </>
          ) : (
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Tuần</label>
              <div className="flex gap-8 items-center">
                <button className="btn btn-secondary btn-sm" onClick={() => shiftWeek(-1)} title="Tuần trước">←</button>
                <input
                  type="week"
                  className="form-input"
                  value={`${year}-W${String(week).padStart(2, '0')}`}
                  onChange={handleWeekInput}
                  style={{ width: '160px' }}
                />
                <button className="btn btn-secondary btn-sm" onClick={() => shiftWeek(1)} title="Tuần sau">→</button>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                {fmtShort(weekStart)} – {fmtShort(weekEnd)}/{weekEnd.getFullYear()}
              </p>
            </div>
          )}

          <button className="btn btn-primary" onClick={fetchReport} disabled={loading}>
            {loading ? '⏳' : '🔍'} Xem báo cáo
          </button>
          {report && (
            <button className="btn btn-secondary" onClick={handleExport}>⬇️ Xuất CSV</button>
          )}
        </div>
      </div>

      {error && <div className="card mb-16" style={{ color: 'var(--status-finalized)' }}>⚠️ {error}</div>}

      {report && (
        <>
          <div className="page-header" style={{ marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.1rem' }}>{report.period_label}</h2>
          </div>

          {/* Summary stats */}
          <div className="stats-grid mb-24">
            <div className="stat-card">
              <div className="stat-icon orange">💰</div>
              <div className="stat-info">
                <h3>{formatMoney(report.grand_total)}</h3>
                <p>Tổng chi phí</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon blue">📅</div>
              <div className="stat-info">
                <h3>{operatingDays}</h3>
                <p>Ngày có đơn</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green">🍱</div>
              <div className="stat-info">
                <h3>{totalEaterDays}</h3>
                <p>Lượt ăn</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon red">📊</div>
              <div className="stat-info">
                <h3>{formatMoney(avgPerDay)}</h3>
                <p>Trung bình / ngày</p>
              </div>
            </div>
          </div>

          {report.days.length === 0 ? (
            <div className="card mb-24 empty-state" style={{ padding: '32px' }}>
              <div className="empty-icon">📭</div>
              <p>Không có ngày nào được chốt trong khoảng thời gian này.</p>
            </div>
          ) : (
            <>
              {/* Spend trend chart */}
              <div className="card mb-24">
                <div className="card-title mb-16">📈 Xu Hướng Chi Tiêu Theo Ngày</div>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', height: '180px', overflowX: 'auto', padding: '8px 4px' }}>
                  {report.days.map(d => {
                    const h = Math.max(4, Math.round((d.total_bill / maxDayBill) * 140));
                    return (
                      <div key={d.order_date} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '44px' }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                          {formatMoney(d.total_bill)}
                        </span>
                        <div
                          title={`${formatMoney(d.total_bill)} · ${d.eater_count} người`}
                          style={{
                            width: '28px',
                            height: `${h}px`,
                            background: 'linear-gradient(180deg, var(--accent-secondary), var(--accent-primary))',
                            borderRadius: '6px 6px 2px 2px',
                          }}
                        />
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', whiteSpace: 'nowrap' }}>
                          {new Date(d.order_date).toLocaleDateString('vi-VN', { weekday: 'short' })}
                        </span>
                        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                          {new Date(d.order_date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Top members chart */}
              <div className="card mb-24">
                <div className="card-title mb-16">🏆 Top Chi Tiêu Theo Người</div>
                {topMembers.map(m => (
                  <div key={m.member_id} style={{ marginBottom: '12px' }}>
                    <div className="flex items-center justify-between" style={{ fontSize: '0.85rem', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600 }}>{m.member_name} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· {m.days_eaten} ngày</span></span>
                      <span style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>{formatMoney(m.total_cost)}</span>
                    </div>
                    <div style={{ background: 'var(--bg-input)', borderRadius: '6px', height: '8px', overflow: 'hidden' }}>
                      <div style={{
                        width: `${(m.total_cost / maxMemberCost) * 100}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))',
                        borderRadius: '6px',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Member summary table */}
          <div className="card mb-24">
            <div className="card-title mb-16">👥 Tổng Hợp Theo Người</div>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr><th>Tên</th><th style={{ textAlign: 'right' }}>Số ngày ăn</th><th style={{ textAlign: 'right' }}>Tổng chi phí</th></tr>
                </thead>
                <tbody>
                  {report.members.length === 0 ? (
                    <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>Không có dữ liệu</td></tr>
                  ) : report.members.map(m => (
                    <tr key={m.member_id}>
                      <td style={{ fontWeight: '600' }}>{m.member_name}</td>
                      <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{m.days_eaten} ngày</td>
                      <td style={{ textAlign: 'right', color: 'var(--accent-primary)', fontWeight: '700' }}>{formatMoney(m.total_cost)}</td>
                    </tr>
                  ))}
                  <tr style={{ borderTop: '2px solid var(--border-medium)', fontWeight: '700' }}>
                    <td>TỔNG CỘNG</td>
                    <td />
                    <td style={{ textAlign: 'right', color: 'var(--accent-primary)' }}>{formatMoney(report.grand_total)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Day by day */}
          <div className="card">
            <div className="card-title mb-16">📋 Chi Tiết Từng Ngày</div>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr><th>Ngày</th><th style={{ textAlign: 'right' }}>Số người</th><th style={{ textAlign: 'right' }}>Tổng bill</th></tr>
                </thead>
                <tbody>
                  {report.days.length === 0 ? (
                    <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>Không có ngày nào được chốt</td></tr>
                  ) : report.days.map(d => (
                    <tr key={d.order_date}>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {new Date(d.order_date).toLocaleDateString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' })}
                      </td>
                      <td style={{ textAlign: 'right' }}>{d.eater_count} người</td>
                      <td style={{ textAlign: 'right', fontWeight: '600' }}>{formatMoney(d.total_bill)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
