'use client';

import { useState, useEffect, useMemo } from 'react';
import { ordersAPI, formatMoney } from '@/lib/api';
import { filterDishes, pickRandom } from '@/lib/randomDish';

const MODES = [
  { id: 'all', label: '🎲 Tất cả món' },
  { id: 'price', label: '💰 Theo giá' },
  { id: 'text', label: '🔤 Theo chữ' },
];

const SOURCE_LABEL = { be: 'Menu Be', restaurant: 'Danh sách món của quán', order: 'Danh sách món của menu' };

export default function RandomDishModal({ orderId, onPick, onClose }) {
  const [dishes, setDishes] = useState(null);
  const [source, setSource] = useState(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('all');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const [pattern, setPattern] = useState('');
  const [result, setResult] = useState(null);
  const [rolling, setRolling] = useState(false);

  useEffect(() => {
    ordersAPI.dishes(orderId)
      .then(r => { setDishes(r.items); setSource(r.source); })
      .catch(err => setError(err.message));
  }, [orderId]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const candidates = useMemo(
    () => (dishes ? filterDishes(dishes, mode, { min, max, pattern }) : []),
    [dishes, mode, min, max, pattern],
  );

  // Changing a filter clears the shown result, which may no longer match
  const onFilter = (setter) => (value) => { setter(value); setResult(null); };

  const roll = () => {
    if (!candidates.length) return;
    setRolling(true);
    // Short shuffle so a re-roll visibly changes, then settle on the pick
    let ticks = 0;
    const iv = setInterval(() => {
      setResult(pickRandom(candidates));
      if (++ticks >= 6) {
        clearInterval(iv);
        setResult(prev => pickRandom(candidates, prev));
        setRolling(false);
      }
    }, 60);
  };

  const unpriced = dishes ? dishes.filter(d => d.price === null || d.price === undefined).length : 0;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <div className="modal-title" style={{ margin: 0 }}>🎲 Random Món</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Đóng">✕</button>
        </div>

        {error ? (
          <p style={{ color: 'var(--status-finalized)' }}>{error}</p>
        ) : dishes === null ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : dishes.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>
            Menu này chưa có danh sách món để random. Nhờ admin hoặc người đặt cơm nhập danh sách món.
          </p>
        ) : (
          <>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 0 }}>
              {SOURCE_LABEL[source] || 'Danh sách món'} · {dishes.length} món
            </p>

            <div className="tabs" style={{ marginBottom: 12 }}>
              {MODES.map(m => (
                <button key={m.id} className={`tab ${mode === m.id ? 'active' : ''}`} onClick={() => onFilter(setMode)(m.id)}>
                  {m.label}
                </button>
              ))}
            </div>

            {mode === 'price' && (
              <div className="form-group">
                <label className="form-label">Khoảng giá (k) — để trống = không giới hạn</label>
                <div className="flex gap-8 items-center">
                  <input type="number" min="0" className="form-input" placeholder="Từ" value={min} onChange={e => onFilter(setMin)(e.target.value)} />
                  <span style={{ color: 'var(--text-muted)' }}>–</span>
                  <input type="number" min="0" className="form-input" placeholder="Đến" value={max} onChange={e => onFilter(setMax)(e.target.value)} autoFocus />
                </div>
                {unpriced > 0 && (
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '6px 0 0' }}>
                    {unpriced} món chưa có giá sẽ không được tính khi lọc theo giá.
                  </p>
                )}
              </div>
            )}

            {mode === 'text' && (
              <div className="form-group">
                <label className="form-label">Món có chữ</label>
                <input className="form-input" placeholder="VD: cơm, cơm*, *cơm, *cơm*" value={pattern}
                  onChange={e => onFilter(setPattern)(e.target.value)} onKeyDown={e => e.key === 'Enter' && roll()} autoFocus />
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '6px 0 0' }}>
                  <code>cơm*</code> bắt đầu bằng · <code>*cơm</code> kết thúc bằng · <code>cơm</code> hoặc <code>*cơm*</code> có chứa.
                  Gõ không dấu để tìm bất kể dấu.
                </p>
              </div>
            )}

            <p style={{ fontSize: '0.82rem', margin: '0 0 12px', color: candidates.length ? 'var(--text-secondary)' : 'var(--status-finalized)' }}>
              {candidates.length ? `${candidates.length} món phù hợp` : 'Không có món nào phù hợp'}
            </p>

            {result ? (
              <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, borderLeft: '3px solid var(--accent-primary)' }}>
                {result.image && (
                  <img src={result.image} alt={result.name}
                    style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
                )}
                <div style={{ flex: 1, minWidth: 0, opacity: rolling ? 0.5 : 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>{result.name}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {result.price !== null && result.price !== undefined ? `${formatMoney(result.price)} đ` : 'Chưa có giá'}
                    {result.category ? ` · ${result.category}` : ''}
                  </div>
                </div>
              </div>
            ) : null}

            <div className="modal-actions">
              {result ? (
                <>
                  <button className="btn btn-secondary" onClick={roll} disabled={rolling || !candidates.length}>🔄 Random lại</button>
                  <button className="btn btn-primary" onClick={() => onPick(result)} disabled={rolling}>✅ Chốt món</button>
                </>
              ) : (
                <>
                  <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
                  <button className="btn btn-primary" onClick={roll} disabled={!candidates.length}>🎲 Random</button>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
