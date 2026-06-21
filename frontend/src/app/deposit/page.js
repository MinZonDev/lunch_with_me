'use client';

import { useState, useEffect, useCallback } from 'react';
import { depositsAPI, membersAPI, formatMoney } from '@/lib/api';
import { isAdmin, getUser } from '@/lib/auth';
import { useToast } from '@/components/Toast';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const BANK = {
  id: process.env.NEXT_PUBLIC_BANK_ID || 'VIKKI',
  account: process.env.NEXT_PUBLIC_BANK_ACCOUNT || '880011988',
  name: process.env.NEXT_PUBLIC_BANK_ACCOUNT_NAME || 'PHAM MINH TRONG',
  bankName: process.env.NEXT_PUBLIC_BANK_NAME || 'Vikki Digital Bank',
};

function vietQRUrl(amount = 0, info = '') {
  const params = new URLSearchParams({ accountName: BANK.name });
  if (amount > 0) params.set('amount', String(amount * 1000));
  if (info) params.set('addInfo', info);
  return `https://img.vietqr.io/image/${BANK.id}-${BANK.account}-compact2.png?${params}`;
}

function BankQR({ amount = 0, info = '' }) {
  return (
    <div style={{ textAlign: 'center', padding: '16px 0' }}>
      <img
        src={vietQRUrl(amount, info)}
        alt="QR chuyển khoản"
        style={{ width: 180, height: 180, borderRadius: 12, border: '3px solid var(--border-medium)', background: '#fff' }}
      />
      <div style={{ marginTop: 10, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Quét bằng app ngân hàng bất kỳ
      </div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.82rem', color: 'var(--text-secondary)', alignItems: 'center' }}>
        <span><span style={{ color: 'var(--text-muted)' }}>Ngân hàng:</span> <strong>{BANK.bankName}</strong></span>
        <span><span style={{ color: 'var(--text-muted)' }}>Tên:</span> <strong>{BANK.name}</strong></span>
        <span>
          <span style={{ color: 'var(--text-muted)' }}>STK:</span>{' '}
          <strong style={{ fontSize: '1rem', letterSpacing: 1, color: '#ffe66d' }}>{BANK.account}</strong>
        </span>
        {info && <span><span style={{ color: 'var(--text-muted)' }}>ND:</span> <strong>{info}</strong></span>}
        {amount > 0 && <span><span style={{ color: 'var(--text-muted)' }}>Số tiền:</span> <strong style={{ color: '#ff8c42' }}>{Number(amount).toLocaleString('vi-VN')}k</strong></span>}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === 'approved') {
    return <span className="badge" style={{ background: 'rgba(6,214,160,0.15)', color: '#06d6a0', border: '1px solid rgba(6,214,160,0.3)' }}>✅ Đã duyệt</span>;
  }
  return <span className="badge" style={{ background: 'rgba(255,230,109,0.15)', color: '#ffe66d', border: '1px solid rgba(255,230,109,0.3)' }}>⏳ Chờ duyệt</span>;
}

export default function DepositPage() {
  const admin = isAdmin();
  const currentUser = getUser();

  const [summary, setSummary] = useState([]);
  const [deposits, setDeposits] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState('deposit'); // 'deposit' | 'charge'
  const [depositAmount, setDepositAmount] = useState('');
  const [depositNote, setDepositNote] = useState('');
  const [adminMemberId, setAdminMemberId] = useState('');
  const [activeTab, setActiveTab] = useState('summary');
  const [historyData, setHistoryData] = useState(null);
  const [histMonth, setHistMonth] = useState(() => new Date().getMonth() + 1);
  const [histYear, setHistYear] = useState(() => new Date().getFullYear());
  const [histLoading, setHistLoading] = useState(false);
  const addToast = useToast();

  const fetchData = useCallback(async () => {
    try {
      const tasks = [depositsAPI.summary(), depositsAPI.list()];
      if (admin) tasks.push(membersAPI.list());
      const [summaryData, depositsData, membersData] = await Promise.all(tasks);
      setSummary(summaryData);
      setDeposits(depositsData);
      if (admin && membersData) setMembers(membersData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [admin]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openModal = (mode) => { setModalMode(mode); setDepositAmount(''); setDepositNote(''); setAdminMemberId(''); setShowModal(true); };

  const handleDeposit = async () => {
    if (!depositAmount || parseInt(depositAmount) <= 0) {
      addToast('Nhập số tiền hợp lệ!', 'error');
      return;
    }
    try {
      if (modalMode === 'charge') {
        if (!adminMemberId) { addToast('Chọn thành viên!', 'error'); return; }
        await depositsAPI.charge({ member_id: parseInt(adminMemberId), amount: parseInt(depositAmount), note: depositNote || null });
        addToast('Đã thêm khoản chi! 📤');
      } else {
        const payload = { amount: parseInt(depositAmount), note: depositNote || null };
        if (admin && adminMemberId) payload.member_id = parseInt(adminMemberId);
        await depositsAPI.create(payload);
        addToast(admin ? 'Đã nạp tiền! 💰' : 'Đã gửi yêu cầu! Chờ admin duyệt.');
      }
      setShowModal(false);
      fetchData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleApprove = async (id) => {
    try {
      await depositsAPI.approve(id);
      addToast('Đã duyệt yêu cầu! 💰');
      fetchData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Xóa giao dịch này?')) return;
    try {
      await depositsAPI.delete(id);
      addToast('Đã xóa');
      fetchData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const fetchHistory = useCallback(async (month, year) => {
    setHistLoading(true);
    try {
      const { getToken } = await import('@/lib/auth');
      const res = await fetch(`${API_BASE}/api/deposits/history?month=${month}&year=${year}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const data = await res.json();
      setHistoryData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setHistLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'daily') fetchHistory(histMonth, histYear);
  }, [activeTab, histMonth, histYear, fetchHistory]);

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  const pendingDeposits = deposits.filter(d => d.status === 'pending');
  const myBalance = summary[0] || null;

  // Admin stats
  const totalDeposited = summary.reduce((s, m) => s + m.total_deposited, 0);
  const totalSpent = summary.reduce((s, m) => s + m.total_spent, 0);
  const totalBalance = summary.reduce((s, m) => s + m.balance, 0);
  const debtCount = summary.filter(m => m.balance < 0).length;

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>💰 Deposit</h1>
            <p>{admin ? 'Quản lý tiền nạp của cả nhóm' : 'Số dư và lịch sử nạp tiền của bạn'}</p>
          </div>
          <div className="flex gap-8">
            {admin && (
              <button className="btn btn-secondary" onClick={() => openModal('charge')}>📤 Thêm Khoản Chi</button>
            )}
            <button className="btn btn-primary" onClick={() => openModal('deposit')}>
              ➕ {admin ? 'Nạp Tiền' : 'Yêu Cầu Nạp'}
            </button>
          </div>
        </div>
      </div>

      {/* Admin: pending requests banner */}
      {admin && pendingDeposits.length > 0 && (
        <div className="card mb-24" style={{ borderLeft: '3px solid #ffe66d', background: 'rgba(255,230,109,0.05)' }}>
          <div className="card-title" style={{ marginBottom: '12px', color: '#ffe66d' }}>
            ⏳ Yêu Cầu Nạp Tiền Chờ Duyệt ({pendingDeposits.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {pendingDeposits.map(d => (
              <div key={d.id} className="flex items-center gap-12" style={{ flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600 }}>{d.member_name}</span>
                <span style={{ color: 'var(--accent-primary)', fontWeight: 700 }}>+{formatMoney(d.amount)}</span>
                {d.note && <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{d.note}</span>}
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{new Date(d.created_at).toLocaleString('vi-VN')}</span>
                <button className="btn btn-primary btn-sm" onClick={() => handleApprove(d.id)}>✅ Duyệt</button>
                <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }} onClick={() => handleDelete(d.id)}>🗑️</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* User: own balance card */}
      {!admin && myBalance && (
        <div className="card mb-24" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>Số dư của bạn</div>
          <div style={{
            fontSize: '2rem', fontWeight: 800,
            color: myBalance.balance >= 0 ? '#06d6a0' : '#ff6b6b',
            marginBottom: '12px',
          }}>
            {myBalance.balance >= 0 ? '+' : ''}{formatMoney(myBalance.balance)}
          </div>
          <div className="flex gap-16" style={{ justifyContent: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
            <span>💵 Đã nạp: {formatMoney(myBalance.total_deposited)}</span>
            {myBalance.total_charged > 0 && <span style={{ color: '#ff6b6b' }}>📤 Khoản chi: {formatMoney(myBalance.total_charged)}</span>}
            <span>🛒 Tiền ăn: {formatMoney(myBalance.total_spent)}</span>
          </div>
        </div>
      )}

      {/* Admin: stats */}
      {admin && (
        <div className="stats-grid" style={{ marginBottom: '24px' }}>
          <div className="stat-card">
            <div className="stat-icon green">💵</div>
            <div className="stat-info"><h3>{formatMoney(totalDeposited)}</h3><p>Tổng nạp vào</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon orange">🛒</div>
            <div className="stat-info"><h3>{formatMoney(totalSpent)}</h3><p>Tổng sử dụng</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon blue">💎</div>
            <div className="stat-info"><h3>{formatMoney(totalBalance)}</h3><p>Tổng còn lại</p></div>
          </div>
          <div className="stat-card">
            <div className="stat-icon red">⚠️</div>
            <div className="stat-info"><h3>{debtCount}</h3><p>Đang nợ</p></div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        {admin && <button className={`tab ${activeTab === 'summary' ? 'active' : ''}`} onClick={() => setActiveTab('summary')}>📊 Tổng Hợp</button>}
        <button className={`tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>📝 Lịch Sử Nạp</button>
        <button className={`tab ${activeTab === 'daily' ? 'active' : ''}`} onClick={() => setActiveTab('daily')}>📅 Chi Tiết Ngày</button>
      </div>

      {/* Summary Tab (admin only) */}
      {activeTab === 'summary' && admin && (
        <div className="deposit-summary-grid">
          {summary.map(member => (
            <div key={member.id} className="member-balance-card">
              <div className="balance-header">
                <div className="member-avatar" style={{
                  width: '40px', height: '40px', borderRadius: '50%',
                  background: member.balance >= 0 ? 'linear-gradient(135deg, #06d6a0, #4ecdc4)' : 'linear-gradient(135deg, #ff6b6b, #ff8c42)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: '700', fontSize: '0.85rem', color: '#0a0a0f',
                }}>
                  {member.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)}
                </div>
                <div>
                  <div style={{ fontWeight: '600' }}>{member.name}</div>
                  <span className={`badge ${member.balance >= 0 ? 'badge-credit' : 'badge-debt'}`}>
                    {member.balance >= 0 ? 'Còn dư' : 'Đang nợ'}
                  </span>
                </div>
              </div>
              <div className={`balance-amount ${member.balance >= 0 ? 'positive' : 'negative'}`}>
                {member.balance >= 0 ? '+' : ''}{formatMoney(member.balance)}
              </div>
              <div className="balance-details">
                <span>💵 Nạp: {formatMoney(member.total_deposited)}</span>
                {member.total_charged > 0 && <span style={{ color: '#ff6b6b' }}>📤 Chi: {formatMoney(member.total_charged)}</span>}
                <span>🛒 Ăn: {formatMoney(member.total_spent)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Thời gian</th>
                {admin && <th>Người</th>}
                <th>Số tiền</th>
                <th>Ghi chú</th>
                <th>Trạng thái</th>
                {admin && <th></th>}
              </tr>
            </thead>
            <tbody>
              {deposits.length === 0 ? (
                <tr>
                  <td colSpan={admin ? 6 : 4} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Chưa có giao dịch nào
                  </td>
                </tr>
              ) : (
                deposits.map(d => (
                  <tr key={d.id}>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                      {new Date(d.created_at).toLocaleString('vi-VN')}
                    </td>
                    {admin && <td style={{ fontWeight: '600' }}>{d.member_name}</td>}
                    <td>
                      {d.type === 'charge' ? (
                        <span style={{ color: '#ff6b6b', fontWeight: '700' }}>−{formatMoney(d.amount)}</span>
                      ) : (
                        <span style={{ color: 'var(--status-success)', fontWeight: '700' }}>+{formatMoney(d.amount)}</span>
                      )}
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {d.type === 'charge' && <span style={{ color: '#ff6b6b', fontSize: '0.8rem', marginRight: '4px' }}>📤 Chi ngoài</span>}
                      {d.note || (d.type !== 'charge' ? '—' : '')}
                    </td>
                    <td>{d.type === 'charge' ? <span className="badge" style={{ background: 'rgba(255,107,107,0.12)', color: '#ff6b6b', border: '1px solid rgba(255,107,107,0.3)' }}>📤 Đã trừ</span> : <StatusBadge status={d.status} />}</td>
                    {admin && (
                      <td>
                        <div className="flex gap-8">
                          {d.status === 'pending' && (
                            <button className="btn btn-primary btn-sm" onClick={() => handleApprove(d.id)}>✅ Duyệt</button>
                          )}
                          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }} onClick={() => handleDelete(d.id)}>🗑️</button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Daily History Tab */}
      {activeTab === 'daily' && (
        <div>
          <div className="flex gap-12 mb-16 items-center">
            <select className="form-select" style={{ width: 'auto' }} value={histMonth} onChange={e => setHistMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>Tháng {m}</option>)}
            </select>
            <select className="form-select" style={{ width: 'auto' }} value={histYear} onChange={e => setHistYear(Number(e.target.value))}>
              {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {histLoading ? (
            <div className="loading-spinner"><div className="spinner" /></div>
          ) : !historyData || historyData.dates.length === 0 ? (
            <div className="empty-state" style={{ padding: '40px' }}>
              <div className="empty-icon">📅</div>
              <p>Không có dữ liệu tháng {histMonth}/{histYear}</p>
            </div>
          ) : (
            <div className="table-wrapper" style={{ overflowX: 'auto' }}>
              <table className="table" style={{ minWidth: admin ? `${200 + historyData.members.length * 80}px` : '400px' }}>
                <thead>
                  <tr>
                    <th style={{ minWidth: '100px' }}>Ngày</th>
                    {historyData.members.map(m => (
                      <th key={m.member_id} style={{ minWidth: '70px', textAlign: 'right' }}>{m.member_name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {historyData.dates.map(d => (
                    <tr key={d}>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                        {new Date(d).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                      </td>
                      {historyData.members.map(m => (
                        <td key={m.member_id} style={{ textAlign: 'right', color: m.daily_costs[d] ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                          {m.daily_costs[d] ? formatMoney(m.daily_costs[d]) : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr style={{ borderTop: '2px solid var(--border-medium)', fontWeight: '700' }}>
                    <td>Tổng</td>
                    {historyData.members.map(m => (
                      <td key={m.member_id} style={{ textAlign: 'right', color: 'var(--accent-primary)' }}>
                        {formatMoney(m.total_spent)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">
              {modalMode === 'charge' ? '📤 Thêm Khoản Chi Ngoài' : admin ? '💰 Nạp Tiền' : '💰 Yêu Cầu Nạp Tiền'}
            </div>

            {modalMode === 'charge' && (
              <div style={{ background: 'rgba(255,107,107,0.06)', border: '1px solid rgba(255,107,107,0.2)', padding: '10px 14px', borderRadius: 'var(--radius-md)', marginBottom: '14px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                📤 Khoản này sẽ <strong style={{ color: '#ff6b6b' }}>trừ trực tiếp</strong> vào số dư của thành viên.
              </div>
            )}

            {!admin && modalMode === 'deposit' && (
              <>
                <BankQR
                  amount={parseInt(depositAmount) || 0}
                  info={currentUser ? `${currentUser.full_name} nap com` : 'nap com'}
                />
                <div style={{ background: 'rgba(255,230,109,0.06)', border: '1px solid rgba(255,230,109,0.2)', padding: '10px 14px', borderRadius: 'var(--radius-md)', marginBottom: '14px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  ⏳ Chuyển khoản xong → nhập số tiền → bấm <strong>Gửi Yêu Cầu</strong>. Admin sẽ xác nhận và cộng vào số dư.
                </div>
              </>
            )}

            {admin && (
              <div className="form-group">
                <label className="form-label">{modalMode === 'charge' ? 'Thành viên bị trừ tiền' : 'Nạp cho thành viên'}</label>
                <select className="form-select" value={adminMemberId} onChange={e => setAdminMemberId(e.target.value)}>
                  <option value="">— Chọn thành viên —</option>
                  {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Số tiền (nghìn đồng)</label>
              <input
                type="number"
                className="form-input"
                placeholder="VD: 50"
                value={depositAmount}
                onChange={e => setDepositAmount(e.target.value)}
                autoFocus
                onKeyDown={e => e.key === 'Enter' && handleDeposit()}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Ghi chú {modalMode === 'charge' ? '(bắt buộc)' : '(tùy chọn)'}</label>
              <input
                type="text"
                className="form-input"
                placeholder={modalMode === 'charge' ? 'VD: Mua thêm nước, bơi lội...' : 'VD: Nạp tháng 6'}
                value={depositNote}
                onChange={e => setDepositNote(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Hủy</button>
              <button
                className={`btn ${modalMode === 'charge' ? 'btn-secondary' : 'btn-primary'}`}
                style={modalMode === 'charge' ? { background: 'rgba(255,107,107,0.15)', color: '#ff6b6b', border: '1px solid rgba(255,107,107,0.3)' } : {}}
                onClick={handleDeposit}
              >
                {modalMode === 'charge' ? '📤 Thêm Khoản Chi' : admin ? '💰 Nạp Tiền' : '📤 Gửi Yêu Cầu'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
