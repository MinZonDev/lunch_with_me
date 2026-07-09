'use client';

import { useState, useEffect, useCallback, use } from 'react';
import { ordersAPI, orderItemsAPI, membersAPI, formatMoney, getInitials, formatDate } from '@/lib/api';
import { isAdmin, getUser } from '@/lib/auth';
import { useToast } from '@/components/Toast';
import { useOrderRealtime } from '@/lib/useOrderRealtime';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

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
  const [editingBill, setEditingBill] = useState(false);
  const [newBill, setNewBill] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  const [beChecked, setBeChecked] = useState(new Set());
  const addToast = useToast();
  const admin = isAdmin();
  const currentUser = getUser();

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

  useEffect(() => { fetchOrder(); }, [fetchOrder]);

  useEffect(() => {
    if (!orderId) return;
    try {
      const stored = JSON.parse(localStorage.getItem(`lwm_be_ordered_${orderId}`) || '[]');
      setBeChecked(new Set(stored));
    } catch {}
  }, [orderId]);

  const toggleBeChecked = (itemId) => {
    setBeChecked(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId); else next.add(itemId);
      try { localStorage.setItem(`lwm_be_ordered_${orderId}`, JSON.stringify([...next])); } catch {}
      return next;
    });
  };

  // Real-time: refetch whenever anyone changes this order/items in Firestore
  useOrderRealtime(orderId ? Number(orderId) : null, fetchOrder);

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

  const handleCancelItem = async (itemId) => {
    try {
      await orderItemsAPI.delete(orderId, itemId);
      addToast('Đã hủy món');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleFinalize = async () => {
    if (submitting) return;
    const bill = parseInt(totalBill) || 0;
    if (bill === 0) {
      addToast('Nhập tổng tiền bill!', 'error');
      return;
    }
    const eaters = order.items.filter(i => i.is_eating);
    const totalExtra = eaters.reduce((s, i) => s + (i.extra_item_cost || 0), 0);
    const perPerson = eaters.length > 0 ? Math.ceil((bill - totalExtra) / eaters.length) : 0;
    if (!confirm(`Chốt bill ${formatMoney(bill)} đ cho ${eaters.length} người ăn (~${formatMoney(perPerson)} đ/người)?`)) return;
    setSubmitting(true);
    try {
      await ordersAPI.finalize(orderId, { total_bill: bill });
      addToast('Đã chốt order! 🎉');
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteOrder = async () => {
    if (!confirm('Xóa order này? Toàn bộ món đặt và chi phí của order sẽ bị xóa vĩnh viễn.')) return;
    try {
      await ordersAPI.delete(orderId);
      addToast('Đã xóa order');
      router.push('/');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleSaveName = async () => {
    try {
      await ordersAPI.update(orderId, { name: nameDraft.trim() });
      addToast('Đã cập nhật tên order');
      setEditingName(false);
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleUpdateBill = async () => {
    if (submitting) return;
    const bill = parseInt(newBill) || 0;
    if (bill === 0) {
      addToast('Nhập tổng tiền bill!', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await ordersAPI.finalize(orderId, { total_bill: bill });
      addToast('Đã cập nhật bill & chia lại tiền!');
      setEditingBill(false);
      fetchOrder();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmitting(false);
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
      if (order.status === 'finalized') {
        await ordersAPI.finalize(orderId, { total_bill: order.total_bill });
        addToast('Đã cập nhật món thêm & chia lại tiền');
      } else {
        addToast('Đã cập nhật món thêm');
      }
      setEditingExtra(null);
      setExtraDesc('');
      setExtraCost('');
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
  const deadlinePassed = order.order_deadline && new Date(order.order_deadline + 'Z') <= new Date();
  const canCancel = order.status === 'open' && !deadlinePassed && !isFinalized;

  return (
    <>
      <div className="page-header">
        <div className="flex items-center gap-16">
          <Link href="/" className="btn btn-ghost">← Quay lại</Link>
          <div>
            <h1>📋 Chi Tiết Order</h1>
            {editingName ? (
              <div className="flex gap-8 items-center mt-8">
                <input
                  className="form-input"
                  placeholder="Tên order (VD: Cơm trưa)"
                  value={nameDraft}
                  onChange={(e) => setNameDraft(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveName()}
                  style={{ width: 220 }}
                  autoFocus
                />
                <button className="btn btn-primary btn-sm" onClick={handleSaveName}>💾</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditingName(false)}>✕</button>
              </div>
            ) : (
              <p>
                {formatDate(order.order_date)}{order.name ? ` · ${order.name}` : ''}
                {admin && (
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginLeft: 6, padding: '2px 6px' }}
                    title="Sửa tên order"
                    onClick={() => { setNameDraft(order.name || ''); setEditingName(true); }}
                  >✏️</button>
                )}
              </p>
            )}
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
          {admin && isFinalized && (
            <button className="btn btn-secondary btn-sm" onClick={handleReopen}>🔓 Mở lại order</button>
          )}
          {admin && (
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--status-finalized)' }}
              onClick={handleDeleteOrder}
            >🗑️ Xóa order</button>
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

      {/* Eaters — grouped by dish */}
      {eatingItems.length > 0 && (() => {
        const beCheckedCount = eatingItems.filter(i => beChecked.has(i.id)).length;

        const dishGroups = (() => {
          const map = {};
          eatingItems.forEach(i => {
            if (!map[i.dish_name]) map[i.dish_name] = [];
            map[i.dish_name].push(i);
          });
          return Object.entries(map).sort(([a], [b]) => a.localeCompare(b, 'vi'));
        })();

        const toggleGroupCheck = (items) => {
          const allChecked = items.every(i => beChecked.has(i.id));
          setBeChecked(prev => {
            const next = new Set(prev);
            if (allChecked) items.forEach(i => next.delete(i.id));
            else items.forEach(i => next.add(i.id));
            try { localStorage.setItem(`lwm_be_ordered_${orderId}`, JSON.stringify([...next])); } catch {}
            return next;
          });
        };

        const toggleCollapse = (dish) => {
          setCollapsedGroups(prev => {
            const next = new Set(prev);
            if (next.has(dish)) next.delete(dish); else next.add(dish);
            return next;
          });
        };

        const tickBtn = (item) => (
          <button
            onClick={() => toggleBeChecked(item.id)}
            title={beChecked.has(item.id) ? 'Bỏ đánh dấu' : 'Đánh dấu đã đặt trên Be'}
            style={{
              width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
              border: beChecked.has(item.id) ? '2px solid #06d6a0' : '2px solid var(--border-color)',
              background: beChecked.has(item.id) ? '#06d6a0' : 'transparent',
              color: beChecked.has(item.id) ? '#fff' : 'transparent',
              cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            ✓
          </button>
        );

        return (
          <div className="mb-24">
            <div className="flex items-center gap-12 mb-16">
              <div className="card-title" style={{ margin: 0 }}>🍽️ Đã chọn món ({eatingItems.length})</div>
              <div style={{ flex: 1 }} />
              <div style={{ fontSize: '0.8rem', color: beCheckedCount === eatingItems.length && eatingItems.length > 0 ? '#06d6a0' : 'var(--text-muted)', fontWeight: 600 }}>
                🛵 Be: {beCheckedCount}/{eatingItems.length}
              </div>
            </div>

            {dishGroups.map(([dish, items]) => {
              const groupChecked = items.filter(i => beChecked.has(i.id)).length;
              const allGroupChecked = groupChecked === items.length;
              const isCollapsed = collapsedGroups.has(dish);

              return (
                <div key={dish} className="card mb-12" style={{ padding: 0, overflow: 'hidden' }}>
                  {/* Group header — click to collapse */}
                  <div
                    onClick={() => toggleCollapse(dish)}
                    style={{
                      padding: '11px 14px', cursor: 'pointer', userSelect: 'none',
                      background: allGroupChecked ? '#06d6a010' : 'var(--bg-subtle)',
                      borderBottom: isCollapsed ? 'none' : '1px solid var(--border-color)',
                      display: 'flex', alignItems: 'center', gap: 10,
                    }}
                  >
                    <span style={{
                      fontSize: '0.65rem', color: 'var(--text-muted)',
                      display: 'inline-block', transition: 'transform 0.15s',
                      transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                    }}>▼</span>
                    <span style={{ fontWeight: 700, fontSize: '0.9rem', flex: 1 }}>{dish}</span>
                    <span style={{
                      fontSize: '0.78rem', fontWeight: 700, padding: '2px 8px',
                      borderRadius: 10, background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)', color: 'var(--text-secondary)',
                    }}>SL: {items.length}</span>
                    <span style={{ fontSize: '0.78rem', color: allGroupChecked ? '#06d6a0' : 'var(--text-muted)', fontWeight: 600, minWidth: 52, textAlign: 'right' }}>
                      🛵 {groupChecked}/{items.length}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleGroupCheck(items); }}
                      title={allGroupChecked ? 'Bỏ tick tất cả' : 'Tick tất cả'}
                      style={{
                        fontSize: '0.7rem', padding: '3px 9px', borderRadius: 10, fontWeight: 600,
                        border: `1.5px solid ${allGroupChecked ? '#06d6a0' : 'var(--border-color)'}`,
                        background: allGroupChecked ? '#06d6a020' : 'transparent',
                        color: allGroupChecked ? '#06d6a0' : 'var(--text-muted)',
                        cursor: 'pointer', flexShrink: 0,
                      }}
                    >
                      {allGroupChecked ? '✓ Tất cả' : 'Tick tất cả'}
                    </button>
                  </div>

                  {/* Member rows */}
                  {!isCollapsed && items.map((item, idx) => (
                    <div key={item.id}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 14px',
                        borderBottom: idx < items.length - 1 || (admin && editingExtra === item.id) ? '1px solid var(--border-subtle)' : 'none',
                        opacity: beChecked.has(item.id) ? 0.5 : 1,
                        transition: 'opacity 0.15s',
                        background: beChecked.has(item.id) ? 'var(--bg-subtle)' : 'transparent',
                      }}>
                        {tickBtn(item)}
                        <div className="member-avatar" style={{ width: 28, height: 28, fontSize: '0.7rem', flexShrink: 0 }}>
                          {getInitials(item.member_name)}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <span style={{ fontWeight: 600, fontSize: '0.88rem', textDecoration: beChecked.has(item.id) ? 'line-through' : 'none' }}>
                            {item.member_name}
                          </span>
                          {admin && memberUsernameMap[item.member_id] && (
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'monospace', marginLeft: 6 }}>
                              @{memberUsernameMap[item.member_id]}
                            </span>
                          )}
                          {item.note && (
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginLeft: 8, fontStyle: 'italic' }}>📝 {item.note}</span>
                          )}
                          {item.extra_item_description && (
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginLeft: 8 }}>
                              + {item.extra_item_description} ({formatMoney(item.extra_item_cost)})
                            </span>
                          )}
                        </div>
                        {isFinalized && <div className="item-cost">{formatMoney(item.total_cost)}</div>}
                        {admin && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => { setEditingExtra(item.id); setExtraDesc(item.extra_item_description || ''); setExtraCost(item.extra_item_cost ? item.extra_item_cost.toString() : ''); }}
                            title={isFinalized ? 'Sửa món thêm (sẽ chia lại tiền)' : 'Set món thêm'}
                          >{isFinalized ? '✏️' : '➕'}</button>
                        )}
                        {canCancel && (admin || item.member_id === currentUser?.member_id) && (
                          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--status-finalized)' }} onClick={() => handleCancelItem(item.id)} title="Hủy món">✕</button>
                        )}
                      </div>
                      {admin && editingExtra === item.id && (
                        <div className="flex gap-8" style={{ padding: '10px 14px', flexWrap: 'wrap', borderBottom: idx < items.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                          <input type="text" className="form-input" placeholder="VD: Trà tắc, Cơm thêm" value={extraDesc} onChange={(e) => setExtraDesc(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSaveExtra(item.id)} style={{ flex: '1', minWidth: '150px' }} />
                          <input type="number" className="form-input" placeholder="Giá (k)" value={extraCost} onChange={(e) => setExtraCost(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSaveExtra(item.id)} style={{ width: '100px' }} />
                          <button className="btn btn-primary btn-sm" onClick={() => handleSaveExtra(item.id)}>💾</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditingExtra(null)}>✕</button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        );
      })()}

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
              onKeyDown={(e) => e.key === 'Enter' && handleFinalize()}
            />
            {parseInt(totalBill) > 0 && (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '6px 0 0' }}>
                = <strong style={{ color: 'var(--accent-primary)' }}>{formatMoney(parseInt(totalBill))} đ</strong>
                {eatingItems.length > 0 && ` · ~${formatMoney(Math.ceil((parseInt(totalBill) - eatingItems.reduce((s, i) => s + (i.extra_item_cost || 0), 0)) / eatingItems.length))} đ/người`}
              </p>
            )}
          </div>
          <button className="btn btn-primary btn-lg w-full" onClick={handleFinalize} disabled={submitting}>
            {submitting ? '⏳ Đang chốt...' : '🎉 Chốt Order & Chia Tiền'}
          </button>
        </div>
      )}

      {/* Cost Breakdown (after finalized) */}
      {isFinalized && (
        <div className="cost-breakdown">
          <div className="flex items-center justify-between mb-16">
            <div className="card-title" style={{ margin: 0 }}>📊 Chi Tiết Chia Tiền</div>
            {admin && !editingBill && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setNewBill(order.total_bill ? order.total_bill.toString() : ''); setEditingBill(true); }}
              >✏️ Cập nhật bill</button>
            )}
          </div>

          {admin && editingBill && (
            <div className="mb-16">
              <div className="flex gap-8" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                  type="number"
                  className="form-input"
                  placeholder="Tổng bill (k)"
                  value={newBill}
                  onChange={(e) => setNewBill(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleUpdateBill()}
                  style={{ flex: '1', minWidth: '120px' }}
                  autoFocus
                />
                <button className="btn btn-primary btn-sm" onClick={handleUpdateBill} disabled={submitting}>
                  {submitting ? '⏳...' : '💾 Lưu & chia lại'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditingBill(false)}>✕</button>
              </div>
              {parseInt(newBill) > 0 && (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '6px 0 0' }}>
                  = <strong style={{ color: 'var(--accent-primary)' }}>{formatMoney(parseInt(newBill))} đ</strong>
                </p>
              )}
            </div>
          )}

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
