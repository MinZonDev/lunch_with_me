'use client';

import { useState } from 'react';
import { ordersAPI } from '@/lib/api';

// Who collects the food today. Picked automatically at the deadline;
// admins/orderers can re-roll (which re-sends the email).
export default function PickupBanner({ order, manager, currentMemberId, onChanged, addToast }) {
  const [busy, setBusy] = useState(false);
  const picked = order.pickup_names?.length > 0;
  const eaters = order.items?.filter(i => i.is_eating).length || 0;

  if (!picked && !(manager && eaters > 0)) return null;

  const reroll = async () => {
    if (busy) return;
    const msg = picked
      ? 'Random lại người lấy cơm? Mọi người đã đặt món sẽ nhận email mới.'
      : 'Random người lấy cơm ngay bây giờ (không chờ deadline)?';
    if (!confirm(msg)) return;
    setBusy(true);
    try {
      await ordersAPI.pickup(order.id);
      addToast('Đã random người lấy cơm 🎲');
      onChanged();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const isMe = currentMemberId && order.pickup_member_ids?.includes(currentMemberId);

  return (
    <div className="card mb-16" style={{
      borderLeft: '3px solid #ff8c42',
      background: isMe ? 'rgba(255,140,66,0.08)' : undefined,
      display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
    }}>
      <span style={{ fontSize: '1.4rem' }}>🥡</span>
      <div style={{ flex: 1, minWidth: 180 }}>
        {picked ? (
          <>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Người lấy cơm hôm nay</div>
            <div style={{ fontWeight: 700 }}>
              {order.pickup_names.join(', ')}
              {isMe && <span style={{ color: '#ff8c42', marginLeft: 8 }}>— là bạn đó!</span>}
            </div>
          </>
        ) : (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Sẽ random {order.pickup_count || 1} người lấy cơm khi hết deadline.
          </div>
        )}
      </div>
      {manager && eaters > 0 && (
        <button className="btn btn-secondary btn-sm" onClick={reroll} disabled={busy}>
          {busy ? '⏳...' : picked ? '🎲 Random lại' : '🎲 Random ngay'}
        </button>
      )}
    </div>
  );
}
