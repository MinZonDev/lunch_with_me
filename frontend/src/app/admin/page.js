'use client';

import { useState, useEffect, useCallback } from 'react';
import { membersAPI, ordersAPI, depositsAPI, formatMoney, getTodayString } from '@/lib/api';
import Link from 'next/link';
import { useToast } from '@/components/Toast';

export default function AdminPage() {
  const [members, setMembers] = useState([]);
  const [todayOrders, setTodayOrders] = useState([]);
  const [summary, setSummary] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [recentOrders, setRecentOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddMember, setShowAddMember] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const addToast = useToast();

  const fetchData = useCallback(async () => {
    try {
      const [membersList, today, summaryData, depositsList, ordersList] = await Promise.all([
        membersAPI.list(false),
        ordersAPI.getToday().catch(() => []),
        depositsAPI.summary().catch(() => []),
        depositsAPI.list().catch(() => []),
        ordersAPI.list({ limit: 14 }).catch(() => []),
      ]);
      setMembers(membersList);
      setTodayOrders(Array.isArray(today) ? today : (today ? [today] : []));
      setSummary(summaryData);
      setPendingCount(depositsList.filter(d => d.status === 'pending').length);
      setRecentOrders(ordersList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddMember = async () => {
    if (!newMemberName.trim()) { addToast('Nhập tên!', 'error'); return; }
    try {
      await membersAPI.create({ name: newMemberName.trim() });
      addToast('Đã thêm thành viên! 🎉');
      setNewMemberName('');
      setShowAddMember(false);
      fetchData();
    } catch (err) { addToast(err.message, 'error'); }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  const activeMembers = members.filter(m => m.is_active);
  const inactiveMembers = members.filter(m => !m.is_active);
  const debtors = summary.filter(m => m.balance < 0);
  const zeroBal = summary.filter(m => m.balance === 0);
  const totalBalance = summary.reduce((s, m) => s + m.balance, 0);
  const totalSpent = summary.reduce((s, m) => s + m.total_spent, 0);

  // Today summary
  const todayEaters = todayOrders.reduce((s, o) => s + (o.eater_count || 0), 0);
  const todayStatus = todayOrders.length === 0 ? null
    : todayOrders.every(o => o.status === 'finalized') ? 'finalized'
    : todayOrders.some(o => o.status === 'open') ? 'open'
    : 'locked';

  // Recent 14 days stats
  const finalizedRecent = recentOrders.filter(o => o.status === 'finalized');

  return (
    <>
      <div className="page-header">
        <div>
          <h1>⚙️ Dashboard Admin</h1>
          <p>{new Date().toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="stats-grid mb-24">
        <Link href="/admin/users" className="stat-card" style={{ textDecoration: 'none', cursor: 'pointer' }}>
          <div className="stat-icon blue">🔑</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Quản Lý Users</h3><p>Tài khoản đăng nhập</p></div>
        </Link>
        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => setShowAddMember(true)}>
          <div className="stat-icon green">👤</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Thêm Thành Viên</h3><p>Thêm người mới vào team</p></div>
        </div>
        <Link href="/admin/restaurants" className="stat-card" style={{ textDecoration: 'none', cursor: 'pointer' }}>
          <div className="stat-icon orange">🏪</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Quán Ăn</h3><p>Quản lý danh sách quán</p></div>
        </Link>
        <Link href="/admin/import" className="stat-card" style={{ textDecoration: 'none', cursor: 'pointer' }}>
          <div className="stat-icon yellow">📥</div>
          <div className="stat-info"><h3 style={{ fontSize: '1rem' }}>Import Excel</h3><p>Import dữ liệu lịch sử</p></div>
        </Link>
      </div>

      {/* System Stats */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div className="stat-icon green">👥</div>
          <div className="stat-info">
            <h3>{activeMembers.length}</h3>
            <p>Thành viên active{inactiveMembers.length > 0 ? ` (+${inactiveMembers.length} inactive)` : ''}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${todayStatus === 'open' ? 'green' : todayStatus === 'finalized' ? 'blue' : todayStatus === 'locked' ? 'yellow' : 'red'}`}>
            {todayStatus === 'open' ? '🟢' : todayStatus === 'finalized' ? '🔴' : todayStatus === 'locked' ? '🟡' : '😴'}
          </div>
          <div className="stat-info">
            <h3>{todayOrders.length === 0 ? 'Chưa có' : `${todayEaters} người`}</h3>
            <p>Hôm nay {todayOrders.length > 0 ? `· ${todayOrders.length} menu` : '· chưa tạo order'}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${pendingCount > 0 ? 'yellow' : 'green'}`}>⏳</div>
          <div className="stat-info">
            <h3>{pendingCount}</h3>
            <p>Yêu cầu nạp tiền chờ duyệt</p>
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${debtors.length > 0 ? 'red' : 'green'}`}>
            {debtors.length > 0 ? '⚠️' : '✅'}
          </div>
          <div className="stat-info">
            <h3>{debtors.length + zeroBal.length}</h3>
            <p>{debtors.length} đang nợ · {zeroBal.length} hết tiền</p>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Today's Orders */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📋 Order Hôm Nay</div>
            <Link href="/" className="btn btn-ghost btn-sm">Xem →</Link>
          </div>
          {todayOrders.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>😴</div>
              Chưa có order hôm nay
            </div>
          ) : todayOrders.map(o => (
            <Link key={o.id} href={`/order/${o.id}`} style={{ textDecoration: 'none', display: 'block', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 12px', borderRadius: 'var(--radius-md)', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                <span className={`badge badge-${o.status}`} style={{ fontSize: '0.72rem' }}>
                  {o.status === 'open' ? '🟢' : o.status === 'locked' ? '🟡' : '🔴'}
                </span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{o.name || 'Menu'}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginLeft: 'auto' }}>
                  {o.eater_count || 0} người
                </span>
              </div>
            </Link>
          ))}
        </div>

        {/* Balance Alerts */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">💳 Cảnh Báo Số Dư</div>
            <Link href="/deposit" className="btn btn-ghost btn-sm">Tất cả →</Link>
          </div>
          {debtors.length === 0 && zeroBal.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#06d6a0', fontSize: '0.85rem' }}>
              <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>✅</div>
              Tất cả đều có số dư dương!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {[...debtors, ...zeroBal].map(m => (
                <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-card)', border: `1px solid ${m.balance < 0 ? 'rgba(255,107,107,0.25)' : 'rgba(255,140,66,0.25)'}` }}>
                  <span style={{ fontWeight: 600, fontSize: '0.88rem', flex: 1 }}>{m.name}</span>
                  {m.username && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>@{m.username}</span>}
                  <span style={{ fontWeight: 700, color: m.balance < 0 ? '#ff6b6b' : '#ff8c42', fontSize: '0.88rem' }}>
                    {m.balance < 0 ? formatMoney(m.balance) : '—'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Orders & Finance Overview */}
      <div className="grid-2" style={{ marginTop: '24px' }}>
        {/* Recent orders */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📊 14 Ngày Gần Đây</div>
            <Link href="/history" className="btn btn-ghost btn-sm">Lịch sử →</Link>
          </div>
          {recentOrders.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Chưa có dữ liệu</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {recentOrders.slice(0, 7).map(o => (
                <Link key={o.id} href={`/order/${o.id}`} style={{ textDecoration: 'none' }}>
                  <div className="flex items-center gap-12" style={{ padding: '7px 8px', borderRadius: 'var(--radius-sm)', fontSize: '0.83rem' }}>
                    <span style={{ color: 'var(--text-muted)', minWidth: '60px' }}>
                      {new Date(o.order_date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}
                    </span>
                    {o.name && <span style={{ color: 'var(--text-secondary)' }}>{o.name}</span>}
                    <span className={`badge badge-${o.status}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                      {o.status === 'open' ? '🟢 Mở' : o.status === 'locked' ? '🟡 Khóa' : '🔴 Chốt'}
                    </span>
                    <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>{o.eater_count || 0}👤</span>
                    {o.status === 'finalized' && o.total_bill > 0 && (
                      <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{formatMoney(o.total_bill)}</span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Finance summary */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">💰 Tổng Quan Tài Chính</div>
            <Link href="/deposit" className="btn btn-ghost btn-sm">Chi tiết →</Link>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="flex items-center justify-between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>👥 Tổng thành viên</span>
              <strong>{activeMembers.length} người</strong>
            </div>
            <div className="flex items-center justify-between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>🍽️ Tổng đã ăn</span>
              <strong style={{ color: '#ff8c42' }}>{formatMoney(totalSpent)}</strong>
            </div>
            <div className="flex items-center justify-between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>💎 Tổng quỹ còn</span>
              <strong style={{ color: totalBalance >= 0 ? '#06d6a0' : '#ff6b6b' }}>{formatMoney(totalBalance)}</strong>
            </div>
            <div className="flex items-center justify-between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>📅 Orders đã chốt (gần đây)</span>
              <strong>{finalizedRecent.length} orders</strong>
            </div>
            <div className="flex items-center justify-between" style={{ padding: '8px 0' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>⚠️ Đang nợ / hết tiền</span>
              <strong style={{ color: debtors.length > 0 ? '#ff6b6b' : '#ff8c42' }}>{debtors.length} / {zeroBal.length} người</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Members quick list (compact) */}
      <div className="card" style={{ marginTop: '24px' }}>
        <div className="card-header">
          <div className="card-title">👥 Thành Viên ({activeMembers.length} active)</div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddMember(true)}>➕ Thêm</button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {activeMembers.map(m => (
            <div key={m.id} style={{
              padding: '6px 12px', borderRadius: 'var(--radius-md)',
              background: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
              fontSize: '0.83rem', color: 'var(--text-primary)',
            }}>
              {m.name}
              {m.username && <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.72rem', marginLeft: '6px' }}>@{m.username}</span>}
            </div>
          ))}
          {inactiveMembers.length > 0 && (
            <div style={{ padding: '6px 12px', borderRadius: 'var(--radius-md)', background: 'rgba(255,107,107,0.06)', border: '1px solid rgba(255,107,107,0.15)', fontSize: '0.83rem', color: 'var(--text-muted)' }}>
              +{inactiveMembers.length} inactive
            </div>
          )}
        </div>
      </div>

      {/* Add Member Modal */}
      {showAddMember && (
        <div className="modal-overlay" onClick={() => setShowAddMember(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">👤 Thêm Thành Viên</div>
            <div className="form-group">
              <label className="form-label">Tên</label>
              <input type="text" className="form-input" placeholder="VD: Nguyễn Văn A" value={newMemberName}
                onChange={e => setNewMemberName(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAddMember()} autoFocus />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowAddMember(false)}>Hủy</button>
              <button className="btn btn-primary" onClick={handleAddMember}>Thêm</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
