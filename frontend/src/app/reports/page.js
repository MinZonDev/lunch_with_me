'use client';

import { useState, useCallback } from 'react';
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

export default function ReportsPage() {
  const now = new Date();
  const [mode, setMode] = useState('monthly');
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [week, setWeek] = useState(getISOWeek(now));
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Năm</label>
            <select className="form-select" value={year} onChange={e => setYear(Number(e.target.value))}>
              {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>

          {mode === 'monthly' ? (
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Tháng</label>
              <select className="form-select" value={month} onChange={e => setMonth(Number(e.target.value))}>
                {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>Tháng {m}</option>)}
              </select>
            </div>
          ) : (
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Tuần</label>
              <input type="number" className="form-input" value={week} min={1} max={53} onChange={e => setWeek(Number(e.target.value))} style={{ width: '80px' }} />
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

          {/* Member summary */}
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
