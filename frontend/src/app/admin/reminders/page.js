'use client';

import { useState, useEffect, useCallback } from 'react';
import { remindersAPI, formatMoney } from '@/lib/api';
import { useToast } from '@/components/Toast';

const DAYS = [
  { value: 'mon', label: 'Thứ Hai' },
  { value: 'tue', label: 'Thứ Ba' },
  { value: 'wed', label: 'Thứ Tư' },
  { value: 'thu', label: 'Thứ Năm' },
  { value: 'fri', label: 'Thứ Sáu' },
  { value: 'sat', label: 'Thứ Bảy' },
  { value: 'sun', label: 'Chủ Nhật' },
];

const SCHEDULES = [
  { value: 'daily', label: 'Hàng ngày' },
  { value: 'weekly', label: 'Hàng tuần' },
  { value: 'biweekly', label: '2 tuần / lần' },
];

export default function RemindersPage() {
  const addToast = useToast();
  const [debtors, setDebtors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null); // `${memberId ?? 'bulk'}:${channel}` | null
  const [sendingOrder, setSendingOrder] = useState(false);
  const [settings, setSettings] = useState({ enabled: false, schedule: 'weekly', day_of_week: 'mon', time: '09:00', teams_webhook_url: '' });
  const [savingSettings, setSavingSettings] = useState(false);
  const [activeTab, setActiveTab] = useState('order');

  const fetchAll = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([remindersAPI.debtors(), remindersAPI.getSettings()]);
      setDebtors(d);
      setSettings(s);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleSend = async (memberId, channel = 'email') => {
    const key = `${memberId ?? 'bulk'}:${channel}`;
    setSending(key);
    try {
      const res = await remindersAPI.send(memberId ?? null, channel);
      const msg = channel === 'teams'
        ? `Đã gửi thông báo Teams cho ${res.sent} người`
        : (res.sent === 0
          ? 'Không có ai cần nhắc (đã có email)'
          : `Đã gửi email nhắc nợ tới ${res.sent} người${res.skipped_no_email ? ` (bỏ qua ${res.skipped_no_email} người chưa có email)` : ''}`);
      addToast(msg);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSending(null);
    }
  };

  const handleSendOrderReminder = async () => {
    setSendingOrder(true);
    try {
      const res = await remindersAPI.sendOrderReminder();
      addToast(res.message || `Đã nhắc ${res.sent} người`);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSendingOrder(false);
    }
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await remindersAPI.saveSettings(settings);
      addToast('Đã lưu cài đặt nhắc nợ tự động! 🔔');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSavingSettings(false);
    }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>🔔 Nhắc Nợ</h1>
          <p>Gửi email nhắc nợ cho thành viên — thủ công hoặc tự động theo lịch</p>
        </div>
      </div>

      {/* Summary */}
      <div className="stats-grid" style={{ marginBottom: '24px' }}>
        <div className="stat-card">
          <div className="stat-icon red">⚠️</div>
          <div className="stat-info">
            <h3>{debtors.length}</h3>
            <p>Người đang nợ</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon orange">💸</div>
          <div className="stat-info">
            <h3>{formatMoney(debtors.reduce((s, d) => s + Math.abs(d.balance), 0))}</h3>
            <p>Tổng nợ</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">✉️</div>
          <div className="stat-info">
            <h3>{debtors.filter(d => d.email).length}</h3>
            <p>Có email</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue">🔔</div>
          <div className="stat-info">
            <h3>{settings.enabled ? 'Bật' : 'Tắt'}</h3>
            <p>Nhắc tự động</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'order' ? 'active' : ''}`} onClick={() => setActiveTab('order')}>
          🍱 Nhắc Đặt Cơm
        </button>
        <button className={`tab ${activeTab === 'manual' ? 'active' : ''}`} onClick={() => setActiveTab('manual')}>
          ✉️ Nhắc Nợ
        </button>
        <button className={`tab ${activeTab === 'auto' ? 'active' : ''}`} onClick={() => setActiveTab('auto')}>
          🕐 Lịch Tự Động
        </button>
      </div>

      {/* Order reminder tab */}
      {activeTab === 'order' && (
        <div className="card" style={{ maxWidth: 520 }}>
          <div className="card-title" style={{ marginBottom: '12px' }}>🍱 Nhắc Đặt Cơm Hôm Nay</div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '20px', lineHeight: 1.6 }}>
            Gửi email nhắc tất cả thành viên <strong>chưa đặt cơm</strong> hôm nay.
            Chỉ gửi cho đơn hàng đang ở trạng thái <strong>mở</strong>.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleSendOrderReminder}
            disabled={sendingOrder}
            style={{ minWidth: 200 }}
          >
            {sendingOrder ? '⏳ Đang gửi...' : '📧 Nhắc Đặt Cơm Ngay'}
          </button>
        </div>
      )}

      {/* Debt manual tab */}
      {activeTab === 'manual' && (
        <div>
          {debtors.length === 0 ? (
            <div className="empty-state" style={{ padding: '48px' }}>
              <div className="empty-icon">🎉</div>
              <h3>Không có ai nợ!</h3>
              <p>Tất cả thành viên đều đã nạp đủ tiền.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-16" style={{ flexWrap: 'wrap', gap: '8px' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>
                  {debtors.length} người đang nợ · {debtors.filter(d => d.email).length} người có email
                </p>
                <div className="flex gap-8">
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSend(null, 'email')}
                    disabled={sending !== null || debtors.filter(d => d.email).length === 0}
                  >
                    {sending === 'bulk:email' ? '⏳ Đang gửi...' : `📧 Email Tất Cả (${debtors.filter(d => d.email).length})`}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleSend(null, 'teams')}
                    disabled={sending !== null || !settings.teams_webhook_url}
                    title={!settings.teams_webhook_url ? 'Chưa cấu hình Teams Webhook URL (xem tab Lịch Tự Động)' : ''}
                  >
                    {sending === 'bulk:teams' ? '⏳ Đang gửi...' : `📢 Teams Tất Cả (${debtors.length})`}
                  </button>
                </div>
              </div>

              <div className="card">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Thành viên</th>
                      <th style={{ textAlign: 'right' }}>Số nợ</th>
                      <th>Email</th>
                      <th style={{ width: 200 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {debtors.map(d => (
                      <tr key={d.member_id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{d.name}</div>
                          {d.name !== d.full_name && (
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{d.full_name}</div>
                          )}
                          {d.username && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                              @{d.username}
                            </div>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <span style={{ color: '#ff6b6b', fontWeight: 700 }}>
                            -{formatMoney(Math.abs(d.balance))}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          {d.email || <span style={{ color: 'var(--text-muted)' }}>Chưa có email</span>}
                        </td>
                        <td>
                          <div className="flex gap-6">
                            <button
                              className="btn btn-secondary btn-sm"
                              disabled={!d.email || sending !== null}
                              onClick={() => handleSend(d.member_id, 'email')}
                              title={!d.email ? 'Thành viên chưa có email' : ''}
                            >
                              {sending === `${d.member_id}:email` ? '⏳' : '📧 Email'}
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              disabled={sending !== null || !settings.teams_webhook_url}
                              onClick={() => handleSend(d.member_id, 'teams')}
                              title={!settings.teams_webhook_url ? 'Chưa cấu hình Teams Webhook URL' : ''}
                            >
                              {sending === `${d.member_id}:teams` ? '⏳' : '📢 Teams'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Auto schedule tab */}
      {activeTab === 'auto' && (
        <div className="card" style={{ maxWidth: 480 }}>
          <div className="card-title" style={{ marginBottom: '20px' }}>🕐 Cài Đặt Nhắc Nợ Tự Động</div>

          <div className="form-group">
            <label className="form-label">📢 Microsoft Teams Webhook URL</label>
            <input
              type="text"
              className="form-input"
              placeholder="https://xxx.webhook.office.com/..."
              value={settings.teams_webhook_url || ''}
              onChange={e => setSettings(s => ({ ...s, teams_webhook_url: e.target.value }))}
            />
            <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '6px', lineHeight: 1.5 }}>
              Nếu điền, hệ thống sẽ gửi thêm 1 thông báo tổng hợp danh sách người đang nợ vào group Teams này
              mỗi khi nhắc nợ (thủ công hoặc tự động theo lịch). Để trống nếu không muốn dùng.
            </p>
          </div>

          <div className="form-group">
            <label className="form-label">Trạng thái</label>
            <div className="flex gap-8">
              <button
                className={`btn btn-sm ${settings.enabled ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setSettings(s => ({ ...s, enabled: true }))}
              >
                🔔 Bật
              </button>
              <button
                className={`btn btn-sm ${!settings.enabled ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setSettings(s => ({ ...s, enabled: false }))}
              >
                🔕 Tắt
              </button>
            </div>
          </div>

          {settings.enabled && (
            <>
              <div className="form-group">
                <label className="form-label">Tần suất</label>
                <select
                  className="form-select"
                  value={settings.schedule}
                  onChange={e => setSettings(s => ({ ...s, schedule: e.target.value }))}
                >
                  {SCHEDULES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>

              {settings.schedule !== 'daily' && (
                <div className="form-group">
                  <label className="form-label">Ngày trong tuần</label>
                  <div className="flex gap-6" style={{ flexWrap: 'wrap' }}>
                    {DAYS.map(d => (
                      <button
                        key={d.value}
                        className={`btn btn-sm ${settings.day_of_week === d.value ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setSettings(s => ({ ...s, day_of_week: d.value }))}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Giờ gửi (giờ Việt Nam)</label>
                <input
                  type="time"
                  className="form-input"
                  value={settings.time}
                  onChange={e => setSettings(s => ({ ...s, time: e.target.value }))}
                  style={{ maxWidth: 160 }}
                />
              </div>

              <div className="card" style={{ background: 'rgba(78,205,196,0.06)', border: '1px solid rgba(78,205,196,0.2)', padding: '12px 14px', marginBottom: '16px' }}>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  📋 Hệ thống sẽ tự động gửi email nhắc nợ{' '}
                  <strong>{SCHEDULES.find(s => s.value === settings.schedule)?.label.toLowerCase()}</strong>
                  {settings.schedule !== 'daily' && (
                    <> vào <strong>{DAYS.find(d => d.value === settings.day_of_week)?.label}</strong></>
                  )}{' '}
                  lúc <strong>{settings.time}</strong> tới tất cả người đang có số dư âm.
                </p>
              </div>
            </>
          )}

          <button
            className="btn btn-primary"
            onClick={handleSaveSettings}
            disabled={savingSettings}
          >
            {savingSettings ? '⏳ Đang lưu...' : '💾 Lưu Cài Đặt'}
          </button>
        </div>
      )}
    </>
  );
}
