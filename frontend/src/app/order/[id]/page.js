'use client';

import { useState, useEffect, useCallback, use } from 'react';
import { ordersAPI, orderItemsAPI, membersAPI, formatMoney, getInitials, formatDate } from '@/lib/api';
import { isAdmin } from '@/lib/auth';
import { useToast } from '@/components/Toast';
import Link from 'next/link';

export default function OrderDetailPage({ params }) {
  const resolvedParams = use(params);
  const orderId = resolvedParams.id;
  const [order, setOrder] = useState(null);
  const [memberUsernameMap, setMemberUsernameMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [totalBill, setTotalBill] = useState('');
  const [editingExtra, setEditingExtra] = useState(null);
  const [extraDesc, setExtraDesc] = useState('');
  const [extraCost, setExtraCost] = useState('');
  const [editingLinks, setEditingLinks] = useState(false);
  const [linksDraft, setLinksDraft] = useState([]);
  const addToast = useToast();
  const admin = isAdmin();

  const fetchOrder = useCallback(async () => {
    try {
      const [data, membersList] = await Promise.all([
        ordersAPI.get(orderId),
        membersAPI.list().catch(() => []),
      ]);
      setOrder(data);
      if (data.total_bill) setTotalBill(data.total_bill.toString());
      setMemberUsernameMap(
        Object.fromEntries(membersList.filter(m => m.username).map(m => [m.id, m.username]))
      );
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [orderId, addToast]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const handleLock = async () => {
    try {
      await ordersAPI.lock(orderId);
      addToast('Đã khóa order!');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleReopen = async () => {
    try {
      await ordersAPI.reopen(orderId);
      addToast('Đã mở lại order!');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleFinalize = async () => {
    const bill = parseInt(totalBill) || 0;
    if (bill === 0) {
      addToast('Nhập tổng tiền bill!', 'error');
      return;
    }
    try {
      await ordersAPI.finalize(orderId, { total_bill: bill });
      addToast('Đã chốt order! 🎉');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const openLinksEditor = () => {
    setLinksDraft((order.links || []).map(l => ({ ...l })));
    setEditingLinks(true);
  };

  const handleSaveLinks = async () => {
    try {
      const valid = linksDraft.filter(l => l.label.trim() && l.url.trim());
      await ordersAPI.updateLinks(orderId, valid.map(l => ({ label: l.label.trim(), url: l.url.trim() })));
      addToast('Đã cập nhật links!');
      setEditingLinks(false);
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleSaveExtra = async (itemId) => {
    try {
      await orderItemsAPI.updateExtra(orderId, itemId, {
        extra_item_description: extraDesc || null,
        extra_item_cost: parseInt(extraCost) || 0,
      });
      setEditingExtra(null);
      setExtraDesc('');
      setExtraCost('');
      addToast('Đã cập nhật món thêm');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  if (!order) {
    return (
      <div className="empty-state">
        <div className="empty-icon">❌</div>
        <h3>Không tìm thấy order</h3>
        <Link href="/" className="btn btn-primary mt-24">← Về trang chủ</Link>
      </div>
    );
  }

  const eatingItems = order.items.filter((i) => i.is_eating);
  const notEatingItems = order.items.filter((i) => !i.is_eating);
  const isFinalized = order.status === 'finalized';

  return (
    <>
      <div className="page-header">
        <div className="flex items-center gap-16">
          <Link href="/" className="btn btn-ghost">← Quay lại</Link>
          <div>
            <h1>📋 Chi Tiết Order</h1>
            <p>{formatDate(order.order_date)}</p>
          </div>
        </div>
        <div className="flex gap-8 items-center mt-8">
          <span className={`badge badge-${order.status}`}>
            {order.status === 'open' ? '🟢 Đang mở' :
              order.status === 'locked' ? '🟡 Đã khóa' : '🔴 Đã chốt'}
          </span>
          {order.status === 'open' && (
            <button className="btn btn-secondary btn-sm" onClick={handleLock}>🔒 Khóa order</button>
          )}
          {order.status === 'locked' && (
            <button className="btn btn-secondary btn-sm" onClick={handleReopen}>🔓 Mở lại</button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon orange">🍽️</div>
          <div className="stat-info">
            <h3>{eatingItems.length}</h3>
            <p>Người ăn</p>
          </div>
        </div>
        {isFinalized && (
          <>
            <div className="stat-card">
              <div className="stat-icon blue">💰</div>
              <div className="stat-info">
                <h3>{formatMoney(order.total_bill)}</h3>
                <p>Tổng bill</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon yellow">👤</div>
              <div className="stat-info">
                <h3>{formatMoney(order.shared_cost_per_person)}</h3>
                <p>Mỗi người</p>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Order Links */}
      <div className="card mb-24">
        <div className="flex items-center justify-between" style={{ marginBottom: '12px' }}>
          <div className="card-title" style={{ margin: 0 }}>🔗 Link Đặt Món</div>
          {admin && !editingLinks && (
            <button className="btn btn-ghost btn-sm" onClick={openLinksEditor}>✏️ Sửa</button>
          )}
        </div>

        {editingLinks ? (
          <div>
            {linksDraft.map((link, idx) => (
              <div key={idx} className="flex gap-8 mb-8" style={{ flexWrap: 'wrap' }}>
                <input
                  className="form-input"
                  placeholder="Tên link"
                  value={link.label}
                  onChange={e => { const d = [...linksDraft]; d[idx].label = e.target.value; setLinksDraft(d); }}
                  style={{ flex: '1', minWidth: '140px' }}
                />
                <input
                  className="form-input"
                  placeholder="URL"
                  value={link.url}
                  onChange={e => { const d = [...linksDraft]; d[idx].url = e.target.value; setLinksDraft(d); }}
                  style={{ flex: '2', minWidth: '200px' }}
                />
                <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }}
                  onClick={() => setLinksDraft(linksDraft.filter((_, i) => i !== idx))}>🗑️</button>
              </div>
            ))}
            <div className="flex gap-8 mt-8">
              <button className="btn btn-ghost btn-sm" onClick={() => setLinksDraft([...linksDraft, { label: '', url: '' }])}>
                + Thêm link
              </button>
              <div style={{ flex: 1 }} />
              <button className="btn btn-secondary btn-sm" onClick={() => setEditingLinks(false)}>Hủy</button>
              <button className="btn btn-primary btn-sm" onClick={handleSaveLinks}>💾 Lưu</button>
            </div>
          </div>
        ) : (order.links && order.links.length > 0) ? (
          <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
            {order.links.map((link, idx) => (
              <a key={idx} href={link.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                🔗 {link.label}
              </a>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
            Chưa có link đặt món.{admin ? ' Bấm ✏️ Sửa để thêm.' : ''}
          </p>
        )}
      </div>

      {/* Eaters */}
      {eatingItems.length > 0 && (
        <div className="mb-24">
          <div className="card-title mb-16">🍽️ Đã chọn món ({eatingItems.length})</div>
          <div className="order-items-list">
            {eatingItems.map((item) => (
              <div key={item.id} className="order-item eating">
                <div className="member-avatar">{getInitials(item.member_name)}</div>
                <div className="item-info">
                  <div className="member-name">
                    {item.member_name}
                    {admin && memberUsernameMap[item.member_id] && (
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace', marginLeft: '6px' }}>
                        @{memberUsernameMap[item.member_id]}
                      </span>
                    )}
                  </div>
                  <div className="dish-name">{item.dish_name}</div>
                  {item.note && <div className="dish-name" style={{ fontStyle: 'italic' }}>📝 {item.note}</div>}
                  {item.extra_item_description && (
                    <div className="extra-info">+ {item.extra_item_description} ({formatMoney(item.extra_item_cost)})</div>
                  )}
                  {admin && !isFinalized && editingExtra === item.id && (
                    <div className="flex gap-8 mt-8" style={{ flexWrap: 'wrap' }}>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="VD: Trà tắc, Cơm thêm"
                        value={extraDesc}
                        onChange={(e) => setExtraDesc(e.target.value)}
                        style={{ flex: '1', minWidth: '150px' }}
                      />
                      <input
                        type="number"
                        className="form-input"
                        placeholder="Giá (k)"
                        value={extraCost}
                        onChange={(e) => setExtraCost(e.target.value)}
                        style={{ width: '100px' }}
                      />
                      <button className="btn btn-primary btn-sm" onClick={() => handleSaveExtra(item.id)}>💾</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditingExtra(null)}>✕</button>
                    </div>
                  )}
                </div>
                <div className="flex gap-8 items-center">
                  {isFinalized && <div className="item-cost">{formatMoney(item.total_cost)}</div>}
                  {admin && !isFinalized && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        setEditingExtra(item.id);
                        setExtraDesc(item.extra_item_description || '');
                        setExtraCost(item.extra_item_cost ? item.extra_item_cost.toString() : '');
                      }}
                      title="Set món thêm"
                    >
                      ➕
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Not eating */}
      {notEatingItems.length > 0 && (
        <div className="mb-24">
          <div className="card-title mb-16" style={{ color: 'var(--text-muted)' }}>
            😴 Không ăn ({notEatingItems.length})
          </div>
          <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
            {notEatingItems.map((item) => (
              <span key={item.id} className="badge" style={{ background: 'var(--bg-card)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
                {item.member_name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Finalize Section */}
      {admin && !isFinalized && eatingItems.length > 0 && (
        <div className="finalize-section">
          <h3>💰 Chốt Bill</h3>
          <p className="text-muted mb-16" style={{ fontSize: '0.85rem' }}>
            Nhập tổng tiền từ app Be sau khi đã đặt xong. Hệ thống sẽ tự động chia tiền.
          </p>
          <div className="form-group">
            <label className="form-label">Tổng bill (k)</label>
            <input
              type="number"
              className="form-input"
              placeholder="VD: 252"
              value={totalBill}
              onChange={(e) => setTotalBill(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-lg w-full" onClick={handleFinalize}>
            🎉 Chốt Order & Chia Tiền
          </button>
        </div>
      )}

      {/* Cost Breakdown (after finalized) */}
      {isFinalized && (
        <div className="cost-breakdown">
          <div className="card-title mb-16">📊 Chi Tiết Chia Tiền</div>

          <div className="cost-row">
            <span className="text-muted">Tổng bill</span>
            <span className="font-bold">{formatMoney(order.total_bill)}</span>
          </div>
          {eatingItems.filter(i => i.extra_item_cost > 0).map(item => (
            <div key={item.id} className="cost-row">
              <span className="text-muted">Trừ: {item.member_name} ({item.extra_item_description})</span>
              <span style={{ color: 'var(--status-finalized)' }}>-{formatMoney(item.extra_item_cost)}</span>
            </div>
          ))}
          <div className="cost-row">
            <span className="text-muted">Chia đều cho {eatingItems.length} người</span>
            <span className="font-bold text-accent">{formatMoney(order.shared_cost_per_person)}/người</span>
          </div>

          <div className="cost-row" style={{ borderTop: '2px solid var(--border-medium)', paddingTop: '16px', marginTop: '8px' }}>
            <span>Tổng</span>
            <span className="font-bold text-accent" style={{ fontSize: '1.2rem' }}>
              {formatMoney(order.total_bill)}
            </span>
          </div>
        </div>
      )}
    </>
  );
}
