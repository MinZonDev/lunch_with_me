'use client';

import { useEffect, useRef, useState } from 'react';
import DishWheel from './DishWheel';
import { wheelLanding } from '@/lib/dishWheel';

export default function PickupWheel({ participants, onSpin, onClose, savedResult }) {
  const [rotation, setRotation] = useState(0);
  const [rolling, setRolling] = useState(false);
  const [result, setResult] = useState(savedResult || null);
  const [error, setError] = useState('');
  const [reducedMotion, setReducedMotion] = useState(false);
  const busy = useRef(false), pending = useRef(null), root = useRef(null), popup = useRef(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const previous = document.activeElement, overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    root.current?.focus();
    const query = matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update(); query.addEventListener('change', update);
    return () => {
      mounted.current = false;
      query.removeEventListener('change', update);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, []);
  useEffect(() => { if (result) popup.current?.focus(); }, [result]);
  const spin = async () => {
    if (busy.current || result) return;
    busy.current = true; setRolling(true); setError('');
    try {
      const winner = await onSpin();
      if (!mounted.current) return;
      pending.current = winner;
      setRotation(wheelLanding(0, participants.findIndex(p => p.id === winner.id), participants.length, reducedMotion ? 4 : 12));
    } catch (err) {
      if (mounted.current) { setError(err.message); setRolling(false); busy.current = false; }
    }
  };
  const trap = e => {
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
    if (e.key !== 'Tab') return;
    const dialog = result ? popup.current : root.current;
    const controls = [...dialog.querySelectorAll('button:not(:disabled), [tabindex="0"]')];
    const first = controls[0], last = controls.at(-1);
    if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || document.activeElement === dialog)) { e.preventDefault(); first?.focus(); }
  };
  return <div className="screen" ref={root} role="dialog" aria-modal="true" aria-labelledby="pickup-wheel-title" tabIndex={-1} onKeyDown={trap}>
    <header inert={result ? true : undefined}>
      <h2 id="pickup-wheel-title">🎡 Vòng quay người lấy cơm</h2>
      <button className="btn close" onClick={onClose} aria-label="Đóng vòng quay">✕</button>
    </header>
    <div className="arena" inert={result ? true : undefined}>
      <DishWheel items={participants} rotation={rotation} rolling={rolling} reducedMotion={reducedMotion}
        itemLabel="người" hubIcon="🥡" onSpin={spin}
        onFinish={() => { setResult(pending.current); setRolling(false); }} />
    </div>
    <footer inert={result ? true : undefined}>
      <p role="status">{rolling ? 'Đang quay…' : 'Mỗi người chỉ có một lượt. Chạm vào tâm để bắt đầu.'}</p>
      {error && <p role="alert" style={{ color: 'var(--status-finalized)' }}>{error}</p>}
      <details><summary>Danh sách {participants.length} người</summary><ol>{participants.map(p => <li key={p.id}>{p.name}</li>)}</ol></details>
    </footer>
    {result && <div className="overlay"><div className="popup" ref={popup} role="dialog" aria-modal="true" aria-labelledby="pickup-result-title" aria-describedby="pickup-result-note" tabIndex={-1}>
      <div className="result-emblem" aria-hidden="true"><span>🥡</span><span className="emblem-check">✓</span></div>
      <p className="result-eyebrow">VÒNG QUAY ĐÃ GỌI TÊN</p>
      <h2 id="pickup-result-title">{result.name}</h2>
      <div className="recorded-badge"><span aria-hidden="true">✓</span> Đã ghi nhận <strong>+1 lượt</strong></div>
      <div className="result-note" id="pickup-result-note">
        <span className="note-icon" aria-hidden="true">↗</span>
        <p>Người lấy cơm cuối cùng sẽ là người bị quay trúng nhiều nhất.</p>
      </div>
      <button className="btn btn-primary result-back" onClick={onClose}>Về bảng tiến độ <span aria-hidden="true">→</span></button>
    </div></div>}
    <style jsx>{`
      .screen { position: fixed; inset: 0; z-index: 1100; display: flex; flex-direction: column; padding: 18px 28px; background: radial-gradient(ellipse at 50% 45%, #35263f, #141320 55%, #0d0e16); color: var(--text-primary); box-sizing: border-box; overflow: hidden; }
      header { display: flex; justify-content: space-between; align-items: center; gap: 10px; } h2 { font-size: 1.3rem; overflow-wrap: anywhere; }
      .close { background: #a52d3c; color: white; } .arena { flex: 1; min-height: 0; display: flex; align-items: center; }
      footer { text-align: center; font-size: .8rem; } details { position: relative; } ol { position: absolute; bottom: 100%; left: 0; right: 0; z-index: 4; max-height: 130px; overflow: auto; text-align: left; background: #1c1b2b; margin: 0; padding-top: 10px; padding-bottom: 10px; }
      .overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: #080912cc; backdrop-filter: blur(10px); padding: 20px; }
      .popup { position: relative; width: min(100%, 440px); max-height: 90dvh; overflow: auto; padding: 36px 32px 28px; box-sizing: border-box; background: radial-gradient(ellipse at 50% 0%, #ff8c4210, transparent 60%), #1c1b2b; border: 1px solid #f3bd7933; border-radius: 28px; text-align: center; box-shadow: 0 28px 90px #0007, inset 0 1px 0 #ffffff08; animation: result-enter .25s ease-out; }
      .result-emblem { position: relative; display: grid; place-items: center; width: 88px; height: 88px; margin: 0 auto 24px; border-radius: 26px; background: linear-gradient(145deg, #ffb46718, #ff8c4208); border: 1px solid #ffb46726; box-shadow: 0 0 40px #ff8c420b; }
      .result-emblem > span:first-child { font-size: 46px; line-height: 1; }
      .emblem-check { position: absolute; bottom: -6px; right: -6px; display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: #64dcb4; color: #132c24; border: 4px solid #1c1b2b; font-size: 13px; font-weight: 800; }
      .result-eyebrow { margin: 0 0 10px; color: #c3a383; font-size: .65rem; font-weight: 600; letter-spacing: .16em; }
      .popup h2 { margin: 0 0 16px; color: #f7f3ee; font-size: clamp(1.65rem, 5vw, 2.1rem); font-weight: 750; line-height: 1.25; overflow-wrap: anywhere; }
      .recorded-badge { display: inline-flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 6px; padding: 7px 12px; border: 1px solid #64dcb41f; border-radius: 100px; color: #8be3c4; background: #64dcb40d; font-size: .75rem; }
      .recorded-badge > span { font-size: .8rem; } .recorded-badge strong { font-weight: 700; }
      .result-note { display: flex; align-items: flex-start; gap: 10px; margin: 26px 0 22px; padding: 14px 16px; background: #ffffff03; border: 1px solid #ffffff0a; border-radius: 12px; text-align: left; }
      .note-icon { flex-shrink: 0; color: #e6b783; font-size: 1rem; line-height: 1.6; }
      .result-note p { margin: 0; color: #b8b4c7; font-size: .8rem; line-height: 1.65; }
      .result-back { width: 100%; min-height: 46px; justify-content: center; gap: 12px; border-radius: 12px; font-size: .85rem; }
      .result-back:focus-visible { outline: 2px solid #ffd2a3; outline-offset: 4px; }
      @keyframes result-enter { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      @media(prefers-reduced-motion: reduce) { .popup { animation: none; } }
      @media(max-width: 480px) { .popup { padding: 28px 22px 22px; border-radius: 22px; } .result-emblem { width: 76px; height: 76px; border-radius: 23px; margin-bottom: 22px; } .result-emblem > span:first-child { font-size: 40px; } }
      @media(max-width: 600px) { .screen { padding: 12px; } h2 { font-size: 1rem; } }
    `}</style>
  </div>;
}
