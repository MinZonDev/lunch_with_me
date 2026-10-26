'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { ordersAPI, formatMoney } from '@/lib/api';
import { filterDishes, pickRandom } from '@/lib/randomDish';
import WheelGame from './WheelGame';

const MODES = [
  { id: 'all', label: '🎲 Tất cả món' },
  { id: 'price', label: '💰 Theo giá' },
  { id: 'text', label: '🔤 Theo chữ' },
];

const SPIN_MS = 5000; // how long a random spin lasts

const SOURCE_LABEL = { be: 'Menu Be', restaurant: 'Danh sách món của quán', order: 'Danh sách món của menu' };

export default function RandomDishModal({ orderId, onPick, onClose }) {
  const [dishes, setDishes] = useState(null);
  const [source, setSource] = useState(null);
  const [error, setError] = useState(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [brokenImage, setBrokenImage] = useState(null);
  const [mode, setMode] = useState('all');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const [pattern, setPattern] = useState('');
  const [result, setResult] = useState(null);
  const [rolling, setRolling] = useState(false);
  const [game, setGame] = useState('quick');
  const [wheelOpen, setWheelOpen] = useState(false);
  const modalRef = useRef(null);
  const busy = useRef(false);

  useEffect(() => {
    const previous = document.activeElement;
    modalRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  useEffect(() => {
    let cancelled = false;
    ordersAPI.dishes(orderId)
      .then(r => { if (!cancelled) { setDishes(r.items); setSource(r.source); } })
      .catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [orderId, loadAttempt]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const candidates = useMemo(
    () => (dishes ? filterDishes(dishes, mode, { min, max, pattern }) : []),
    [dishes, mode, min, max, pattern],
  );

  const timer = useRef(null);
  const lastPick = useRef(null);
  const stopSpin = () => { clearTimeout(timer.current); timer.current = null; busy.current = false; setRolling(false); };
  useEffect(() => () => clearTimeout(timer.current), []); // closing mid-spin

  // Changing a filter cancels a spin and clears the result, which may no longer match
  const onFilter = (setter) => (value) => { if (busy.current) return; stopSpin(); setter(value); setResult(null); };

  // Slot-machine spin: ~5s, fast at first then slowing down before it stops
  const roll = () => {
    if (!candidates.length || busy.current) return;
    if (game === 'wheel' || game === 'ufo') {
      setResult(null);
      setWheelOpen(true);
      return;
    }
    busy.current = true;
    setRolling(true);
    const delays = [];
    for (let i = 0, total = 0; total < SPIN_MS; i++) {
      const d = 50 + Math.min(i / 25, 1) ** 2 * 450;
      delays.push(d);
      total += d;
    }
    let shown = result;
    const step = (i) => {
      if (i === delays.length - 1) {
        // Final pick: any matching dish except the previous final one
        const pick = pickRandom(candidates, lastPick.current);
        lastPick.current = pick;
        setResult(pick);
        timer.current = null;
        busy.current = false;
        setRolling(false);
        return;
      }
      shown = pickRandom(candidates, shown);
      setResult(shown);
      timer.current = setTimeout(() => step(i + 1), delays[i]);
    };
    step(0);
  };

  const unpriced = dishes ? dishes.filter(d => d.price === null || d.price === undefined).length : 0;

  if (wheelOpen) return <WheelGame mode={game} items={candidates} onBack={() => { setWheelOpen(false); requestAnimationFrame(() => modalRef.current?.focus()); }} onClose={onClose} onPick={onPick} />;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="random-title" ref={modalRef} tabIndex={-1}
        onKeyDown={e => {
          if (e.key !== 'Tab') return;
          const controls = [...modalRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), summary, [tabindex="0"]')].filter(el => el.getClientRects().length);
          const first = controls[0]; const last = controls[controls.length - 1];
          if (e.shiftKey && (document.activeElement === first || document.activeElement === modalRef.current)) { e.preventDefault(); last?.focus(); }
          else if (!e.shiftKey && (document.activeElement === last || document.activeElement === modalRef.current)) { e.preventDefault(); first?.focus(); }
        }} onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="random-header flex items-center justify-between" style={{ marginBottom: 12 }}>
          <h2 id="random-title" className="modal-title" style={{ margin: 0 }}>🎲 Hôm nay ăn gì?</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose} title="Đóng">✕</button>
        </div>

        <div className="tabs" role="group" aria-label="Kiểu random" style={{ marginBottom: 16 }}>
          {[['quick', '🎲 Nhanh'], ['wheel', '🎡 Vòng quay'], ['ufo', '🛸 UFO']].map(([id, label]) => (
            <button key={id} className={`tab ${game === id ? 'active' : ''}`} aria-pressed={game === id} disabled={rolling}
              onClick={() => { setGame(id); setResult(null); }}>{label}</button>
          ))}
        </div>

        {error ? (
          <div><p style={{ color: 'var(--status-finalized)' }}>{error}</p>
            <button className="btn btn-secondary" onClick={() => { setError(null); setDishes(null); setLoadAttempt(n => n + 1); }}>Thử lại</button></div>
        ) : dishes === null ? (
          <div className="loading-spinner"><div className="spinner" /></div>
        ) : dishes.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>
            Menu này chưa có danh sách món để random. Nhờ admin hoặc người đặt cơm nhập danh sách món.
          </p>
        ) : (
          <div>
            <div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 0 }}>
              {SOURCE_LABEL[source] || 'Danh sách món'} · {dishes.length} món
            </p>

            <div className="tabs" style={{ marginBottom: 12 }}>
              {MODES.map(m => (
                <button key={m.id} disabled={rolling} className={`tab ${mode === m.id ? 'active' : ''}`} onClick={() => onFilter(setMode)(m.id)}>
                  {m.label}
                </button>
              ))}
            </div>

            {mode === 'price' && (
              <div className="form-group">
                <label className="form-label">Khoảng giá (k) — để trống = không giới hạn</label>
                <div className="flex gap-8 items-center">
                  <input type="number" min="0" disabled={rolling} aria-label="Giá từ, nghìn đồng" className="form-input" placeholder="Từ" value={min} onChange={e => onFilter(setMin)(e.target.value)} />
                  <span style={{ color: 'var(--text-muted)' }}>–</span>
                  <input type="number" min="0" disabled={rolling} aria-label="Giá đến, nghìn đồng" className="form-input" placeholder="Đến" value={max} onChange={e => onFilter(setMax)(e.target.value)} autoFocus />
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
                <input className="form-input" disabled={rolling} aria-label="Từ khoá món ăn" placeholder="VD: cơm, cơm*, *cơm, *cơm*" value={pattern}
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

            {!candidates.length && <button className="btn btn-secondary btn-sm" onClick={() => { setMode('all'); setMin(''); setMax(''); setPattern(''); setResult(null); }}>Xoá bộ lọc</button>}
            </div>
            <div className="game-stage">
            {game === 'wheel' && <p style={{ fontSize: '.82rem', color: 'var(--text-muted)' }}>Chọn bộ lọc rồi bấm Quay để mở vòng quay lớn. Chạm vào tâm để bắt đầu quay.</p>}
            {game === 'ufo' && <p style={{ fontSize: '.82rem', color: 'var(--text-muted)' }}>Chọn bộ lọc rồi mở sân chơi. Chạm vào UFO để bay và gắp món bất ngờ.</p>}
            <div role="status" aria-live="polite" className="sr-only">{rolling ? 'Đang quay món' : result ? `Kết quả: ${result.name}` : ''}</div>

            {result ? (
              <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, borderLeft: `3px solid ${rolling ? 'var(--border-medium)' : 'var(--accent-primary)'}`, transition: 'border-color 0.3s' }}>
                {result.image && brokenImage !== result.image ? (
                  <img src={result.image} alt={result.name}
                    onError={() => setBrokenImage(result.image)}
                    style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
                ) : <span aria-hidden="true" style={{ fontSize: 36 }}>🍽️</span>}
                <div style={{ flex: 1, minWidth: 0 }}>
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
                  <button className="btn btn-secondary" onClick={roll} disabled={rolling || !candidates.length}>
                    {rolling ? '⏳ Đang quay...' : '🔄 Random lại'}
                  </button>
                  <button className="btn btn-primary" onClick={() => onPick(result)} disabled={rolling}>✅ Dùng món này</button>
                </>
              ) : (
                <>
                  <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
                  <button className="btn btn-primary" onClick={roll} disabled={rolling || !candidates.length}>{rolling ? '⏳ Đang quay...' : game === 'wheel' ? '🎡 Quay' : game === 'ufo' ? '🛸 Mở sân chơi' : '🎲 Random'}</button>
                </>
              )}
            </div>
            {result && !rolling && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 12 }}>Giá tham khảo. Dùng món này sẽ điền vào form; bạn vẫn cần xác nhận đặt món.</p>}
            </div>
          </div>
        )}
      </div>
      <style jsx>{`
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
        .game-stage { min-width: 0; }
      `}</style>
    </div>
  );
}
