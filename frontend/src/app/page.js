'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { ordersAPI, orderItemsAPI, membersAPI, restaurantsAPI, delegationsAPI, formatMoney, getInitials, getTodayString } from '@/lib/api';
import { useToast } from '@/components/Toast';
import { isAdmin, getUser } from '@/lib/auth';
import logger from '@/lib/logger';
import Link from 'next/link';

function useCountdown(deadlineUtcStr) {
  const [mins, setMins] = useState(null);
  useEffect(() => {
    if (!deadlineUtcStr) return;
    const update = () => {
      const diff = Math.floor((new Date(deadlineUtcStr + 'Z') - Date.now()) / 60000);
      setMins(diff);
    };
    update();
    const t = setInterval(update, 30000);
    return () => clearInterval(t);
  }, [deadlineUtcStr]);
  return mins;
}

export default function HomePage() {
  const [todayOrder, setTodayOrder] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMember, setSelectedMember] = useState(null);
  const [dishName, setDishName] = useState('');
  const [dishNote, setDishNote] = useState('');
  const [isChay, setIsChay] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [restaurants, setRestaurants] = useState([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [deadlineTime, setDeadlineTime] = useState('11:30');
  // member_ids I am allowed to order for (my own + delegated to me)
  const [allowedMemberIds, setAllowedMemberIds] = useState(new Set());
  const addToast = useToast();
  const admin = isAdmin();
  const currentUser = getUser();

  const minutesLeft = useCountdown(todayOrder?.order_deadline);
  const deadlinePassed = minutesLeft !== null && minutesLeft <= 0;
  const canOrder = todayOrder?.status === 'open' && !deadlinePassed;

  const fetchData = useCallback(async () => {
    try {
      const [order, membersList, restaurantList, delegationList] = await Promise.all([
        ordersAPI.getToday(),
        membersAPI.list(),
        restaurantsAPI.list().catch(() => []),
        delegationsAPI.list().catch(() => []),
      ]);
      setTodayOrder(order);
      setMembers(membersList);
      setRestaurants(restaurantList);

      // Build set of member_ids this user can order for
      const myMemberId = currentUser?.member_id;
      const allowed = new Set();
      if (myMemberId) allowed.add(myMemberId);
      delegationList
        .filter(d => d.delegate_member_id === myMemberId && d.status === 'active')
        .forEach(d => allowed.add(d.grantor_member_id));
      setAllowedMemberIds(allowed);
    } catch (err) {
      logger.error('Failed to fetch home data', { error: err.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openCreateModal = async () => {
    setShowCreateModal(true);
    // Default to last-used restaurant
    try {
      const last = await restaurantsAPI.lastUsed();
      if (last) setSelectedRestaurant(last.id);
    } catch {}
  };

  const handleCreateOrder = async () => {
    try {
      const order = await ordersAPI.create({
        order_date: getTodayString(),
        restaurant_id: selectedRestaurant || null,
        deadline_time: deadlineTime || '11:30',
      });
      setTodayOrder(order);
      setShowCreateModal(false);
      setSelectedRestaurant(null);
      addToast('Đã tạo order hôm nay!');
    } catch (err) { addToast(err.message, 'error'); }
  };

  const handleSubmitDish = async () => {
    if (!selectedMember) { addToast('Chọn tên trước!', 'error'); return; }
    if (!dishName.trim()) { addToast('Nhập tên món!', 'error'); return; }
    try {
      await orderItemsAPI.create(todayOrder.id, {
        member_id: selectedMember,
        dish_name: isChay ? null : dishName.trim(),
        dish_name_chay: isChay ? dishName.trim() : null,
        note: dishNote.trim() || null,
        is_chay: isChay,
      });
      setDishName(''); setDishNote(''); setSelectedMember(null);
      const isProxy = selectedMember !== currentUser?.member_id;
      addToast(isProxy ? 'Đã đặt món giùm! 🤝' : 'Đã chọn món! 🍚');
      fetchData();
    } catch (err) {
      logger.error('Submit dish failed', { member_id: selectedMember, error: err.message });
      addToast(err.message, 'error');
    }
  };

  const handleCancelItem = async (itemId) => {
    try {
      await orderItemsAPI.delete(todayOrder.id, itemId);
      addToast('Đã hủy chọn món');
      fetchData();
    } catch (err) {
      logger.error('Cancel item failed', { itemId, error: err.message });
      addToast(err.message, 'error');
    }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  if (!todayOrder) {
    return (
      <>
        <div className="page-header">
          <h1>🍚 Hôm Nay</h1>
          <p>{new Date().toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}</p>
        </div>
        <div className="empty-state">
          <div className="empty-icon">🍱</div>
          <h3>Chưa có order hôm nay</h3>
          <p>Tạo order mới để team bắt đầu chọn món!</p>
          {admin && (
            <button className="btn btn-primary btn-lg mt-24" onClick={openCreateModal}>
              ✨ Tạo Order Hôm Nay
            </button>
          )}
        </div>

        {showCreateModal && (
          <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-title">🍱 Tạo Order Hôm Nay</div>
              <div className="form-group">
                <label className="form-label">Quán ăn</label>
                {restaurants.length > 0 ? (
                  <select
                    className="form-select"
                    value={selectedRestaurant || ''}
                    onChange={e => setSelectedRestaurant(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">— Chưa chọn quán —</option>
                    {restaurants.map(r => (
                      <option key={r.id} value={r.id}>{r.name}{r.link ? ' 🔗' : ''}</option>
                    ))}
                  </select>
                ) : (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                    Chưa có quán nào. <a href="/admin/restaurants" style={{ color: 'var(--accent-primary)' }}>Thêm quán →</a>
                  </p>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Deadline chọn món</label>
                <input type="time" className="form-input" value={deadlineTime} onChange={e => setDeadlineTime(e.target.value)} />
              </div>
              <div className="modal-actions">
                <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>Hủy</button>
                <button className="btn btn-primary" onClick={handleCreateOrder}>✨ Tạo Order</button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  const eatingItems = todayOrder.items.filter(i => i.is_eating);
  const notEatingItems = todayOrder.items.filter(i => !i.is_eating);
  const isFinalized = todayOrder.status === 'finalized';
  const isOpen = todayOrder.status === 'open';

  // Pending members alert
  const pendingNames = notEatingItems.map(i => i.member_name);

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>🍚 Order Hôm Nay</h1>
            <p>{new Date().toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}</p>
          </div>
          <div className="flex gap-8 items-center">
            <span className={`badge badge-${todayOrder.status}`}>
              {todayOrder.status === 'open' ? '🟢 Đang mở' : todayOrder.status === 'locked' ? '🟡 Đã khóa' : '🔴 Đã chốt'}
            </span>
            <Link href={`/order/${todayOrder.id}`} className="btn btn-secondary btn-sm">Chi tiết →</Link>
          </div>
        </div>
      </div>

      {/* Deadline Banner */}
      {todayOrder.order_deadline && isOpen && (
        <div className={`deadline-banner ${deadlinePassed ? 'expired' : minutesLeft <= 30 ? 'warning' : ''}`}>
          {deadlinePassed ? (
            <span>⏰ Đã hết giờ chọn món</span>
          ) : minutesLeft <= 60 ? (
            <span>⏳ Còn <strong>{minutesLeft} phút</strong> để chọn món</span>
          ) : (
            <span>🕐 Deadline: {new Date(todayOrder.order_deadline + 'Z').toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
          )}
        </div>
      )}

      {/* Pending members alert */}
      {isOpen && !deadlinePassed && pendingNames.length > 0 && (
        <div className="pending-alert">
          😴 Chưa chọn món: <strong>{pendingNames.join(', ')}</strong>
        </div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon orange">🍽️</div>
          <div className="stat-info"><h3>{todayOrder.eater_count + todayOrder.chay_eater_count}</h3><p>Người ăn</p></div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">🥗</div>
          <div className="stat-info"><h3>{todayOrder.chay_eater_count}</h3><p>Ăn chay</p></div>
        </div>
        {isFinalized && (
          <>
            <div className="stat-card">
              <div className="stat-icon blue">💰</div>
              <div className="stat-info"><h3>{formatMoney(todayOrder.total_bill)}</h3><p>Tổng bill</p></div>
            </div>
            <div className="stat-card">
              <div className="stat-icon yellow">👤</div>
              <div className="stat-info"><h3>{formatMoney(todayOrder.shared_cost_per_person)}</h3><p>Mỗi người</p></div>
            </div>
          </>
        )}
      </div>

      {/* Order Links */}
      {(todayOrder.restaurant_name || (todayOrder.links && todayOrder.links.length > 0)) && (
        <div className="card mb-24">
          <div className="flex gap-12 items-center" style={{ flexWrap: 'wrap' }}>
            {todayOrder.restaurant_name && (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>🏪 {todayOrder.restaurant_name}</span>
            )}
            {(todayOrder.links || []).map((link, idx) => (
              <a key={idx} href={link.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                🔗 {link.label}
              </a>
            ))}
            <Link href={`/order/${todayOrder.id}`} className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto', fontSize: '0.8rem' }}>
              Quản lý links →
            </Link>
          </div>
        </div>
      )}

      <div className="grid-2">
        {/* Order Form */}
        {canOrder && (
          <div className="card">
            <div className="card-title" style={{ marginBottom: '16px' }}>✏️ Chọn Món</div>
            <div className="form-group">
              <label className="form-label">
                Đặt cho ai?
                {!admin && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '6px' }}>
                    (chỉ bản thân + người đã ủy quyền)
                  </span>
                )}
              </label>
              <div className="member-select-grid">
                {(admin ? members : members.filter(m => allowedMemberIds.has(m.id))).map(m => {
                  const hasOrdered = eatingItems.some(i => i.member_id === m.id);
                  const isProxy = m.id !== currentUser?.member_id;
                  return (
                    <button
                      key={m.id}
                      className={`member-select-item ${selectedMember === m.id ? 'selected' : ''}`}
                      onClick={() => setSelectedMember(m.id)}
                      style={hasOrdered ? { opacity: 0.5, borderColor: 'var(--status-success)' } : {}}
                      title={isProxy ? `Đặt giùm ${m.name} (được ủy quyền)` : m.name}
                    >
                      {hasOrdered ? '✅ ' : ''}{m.name}{isProxy ? ' 🤝' : ''}
                    </button>
                  );
                })}
              </div>
              {!admin && allowedMemberIds.size <= 1 && (
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Muốn đặt giùm người khác?{' '}
                  <a href="/delegation" style={{ color: 'var(--accent-primary)' }}>Yêu cầu ủy quyền →</a>
                </p>
              )}
            </div>
            <div className="form-group">
              <label className="form-label">Loại</label>
              <div className="flex gap-8">
                <button className={`btn btn-sm ${!isChay ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setIsChay(false)}>🍖 Thường</button>
                <button className={`btn btn-sm ${isChay ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setIsChay(true)}>🥬 Chay</button>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Tên Món</label>
              <input type="text" className="form-input" placeholder="VD: Gà phi lê, Cá ngừ kho tiêu..." value={dishName} onChange={e => setDishName(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSubmitDish()} />
            </div>
            <div className="form-group">
              <label className="form-label">Ghi chú (tùy chọn)</label>
              <input type="text" className="form-input" placeholder="VD: Ít cay, thêm rau..." value={dishNote} onChange={e => setDishNote(e.target.value)} />
            </div>
            <button className="btn btn-primary w-full" onClick={handleSubmitDish}>🍚 Chọn Món</button>
          </div>
        )}

        {/* Order Items List */}
        <div>
          <div className="card-title mb-16">👥 Đã chọn ({eatingItems.length} người)</div>
          <div className="order-items-list">
            {eatingItems.map(item => (
              <div key={item.id} className="order-item eating">
                <div className="member-avatar">{getInitials(item.member_name)}</div>
                <div className="item-info">
                  <div className="member-name">{item.member_name}</div>
                  <div className="dish-name">{item.is_chay ? '🥬 ' : '🍖 '}{item.dish_name || item.dish_name_chay}</div>
                  {item.note && <div className="dish-name" style={{ fontStyle: 'italic' }}>📝 {item.note}</div>}
                  {item.extra_item_description && <div className="extra-info">+ {item.extra_item_description} ({formatMoney(item.extra_item_cost)})</div>}
                </div>
                {isFinalized ? (
                  <div className="item-cost">{formatMoney(item.total_cost)}</div>
                ) : canOrder ? (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleCancelItem(item.id)} title="Hủy">✕</button>
                ) : null}
              </div>
            ))}
            {eatingItems.length === 0 && (
              <div className="empty-state" style={{ padding: '30px' }}>
                <div className="empty-icon">🍽️</div><p>Chưa ai chọn món</p>
              </div>
            )}
          </div>

          {notEatingItems.length > 0 && !deadlinePassed && isOpen && (
            <>
              <div className="card-title mt-24 mb-16" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                😴 Chưa chọn ({notEatingItems.length})
              </div>
              <div className="flex gap-8" style={{ flexWrap: 'wrap' }}>
                {notEatingItems.map(item => (
                  <span key={item.id} className="badge" style={{ background: 'var(--bg-card)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
                    {item.member_name}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <style jsx>{`
        .deadline-banner {
          background: rgba(78, 205, 196, 0.1);
          border: 1px solid rgba(78, 205, 196, 0.3);
          border-radius: var(--radius-md);
          padding: 10px 16px;
          margin-bottom: 16px;
          color: var(--status-open);
          font-size: 0.9rem;
        }
        .deadline-banner.warning {
          background: rgba(255, 230, 109, 0.1);
          border-color: rgba(255, 230, 109, 0.3);
          color: var(--status-locked);
        }
        .deadline-banner.expired {
          background: rgba(255, 107, 107, 0.1);
          border-color: rgba(255, 107, 107, 0.3);
          color: var(--status-finalized);
        }
        .pending-alert {
          background: rgba(255, 140, 66, 0.08);
          border: 1px solid rgba(255, 140, 66, 0.2);
          border-radius: var(--radius-md);
          padding: 10px 16px;
          margin-bottom: 16px;
          font-size: 0.875rem;
          color: var(--text-secondary);
        }
      `}</style>
    </>
  );
}
