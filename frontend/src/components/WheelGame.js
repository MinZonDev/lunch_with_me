'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import DishWheel from './DishWheel';
import UfoStage from './UfoStage';
import { prepareWheel, wheelLanding } from '@/lib/dishWheel';
import { prepareUfo } from '@/lib/ufoDishes';
import { formatMoney } from '@/lib/api';
import useUfoSound from '@/lib/useUfoSound';

export default function WheelGame({ items, onBack, onClose, onPick, mode = 'wheel' }) {
  const isUfo = mode === 'ufo';
  const { enabled: ufoSoundEnabled, unavailable: ufoSoundUnavailable, start: startUfoSound, stop: stopUfoSound, toggle: toggleUfoSound } = useUfoSound(isUfo);
  const gameName = isUfo ? 'UFO gắp món' : 'Vòng quay bữa trưa';
  const closeLabel = isUfo ? 'Đóng UFO' : 'Đóng vòng quay';
  const [rotation, setRotation] = useState(0);
  const [rolling, setRolling] = useState(false);
  const [result, setResult] = useState(null);
  const [brokenImage, setBrokenImage] = useState(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const pending = useRef(null), busy = useRef(false);
  const dialog = useRef(null), resultDialog = useRef(null);
  const [showList, setShowList] = useState(false);
  const [ufoRun, setUfoRun] = useState(null);
  const runId = useRef(0);
  useEffect(() => {
    const previous = document.activeElement, overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden'; dialog.current?.focus();
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update(); query.addEventListener('change', update);
    return () => { query.removeEventListener('change', update); document.body.style.overflow = overflow; previous?.focus?.(); };
  }, []);
  useEffect(() => { if (result) resultDialog.current?.focus(); else dialog.current?.focus(); }, [result]);
  const spin = () => {
    if (busy.current || !items.length) return;
    if (isUfo) startUfoSound();
    busy.current = true;
    const pick = isUfo ? prepareUfo(items) : prepareWheel(items);
    pending.current = pick.winner;
    setResult(null); setShowList(false); setRolling(true);
    if (isUfo) setUfoRun({ ...pick, id: ++runId.current });
    else setRotation(previous => wheelLanding(previous, pick.winnerSlot, items.length, reducedMotion ? 4 : 12));
  };
  const finish = useCallback(() => {
    if (!pending.current) return;
    if (isUfo) stopUfoSound();
    setResult(pending.current); pending.current = null;
    busy.current = false; setRolling(false);
  }, [stopUfoSound, isUfo]);
  const trapFocus = e => {
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
    if (e.key !== 'Tab') return;
    const root = result ? resultDialog.current : dialog.current;
    const controls = [...root.querySelectorAll('button:not(:disabled), [tabindex="0"]')].filter(el => el.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === root)) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || document.activeElement === root)) { e.preventDefault(); first?.focus(); }
  };
  return <div className={`wheel-screen ${isUfo ? 'ufo-screen' : ''}`} role="dialog" aria-modal="true" aria-labelledby="wheel-title" tabIndex={-1} ref={dialog} onKeyDown={trapFocus}>
    <div className="screen-header" inert={result ? true : undefined}>
      <button className="btn btn-secondary btn-sm" onClick={onBack} disabled={rolling}>← Bộ lọc</button>
      <div><h2 id="wheel-title">{gameName}</h2><p>{items.length} món · Mỗi món có cơ hội như nhau</p></div>
      <button className="close" onClick={onClose} aria-label={closeLabel}>✕</button>
    </div>
    <div className="arena" inert={result ? true : undefined}>
      {isUfo ? <UfoStage items={items} run={ufoRun} rolling={rolling} reducedMotion={reducedMotion} onSpin={spin} onFinish={finish} onSearchEnd={stopUfoSound} /> :
        <DishWheel items={items} rotation={rotation} rolling={rolling} reducedMotion={reducedMotion} onSpin={spin} onFinish={finish} />}
    </div>
    <div className="screen-footer" inert={result ? true : undefined}>
      <p role="status">{rolling ? 'Đang chọn bữa trưa cho bạn…' : isUfo ? 'Một chuyến bay, một món ngon bất ngờ' : 'Chạm vào tâm vòng quay để bắt đầu'}</p>
      {isUfo && <button className="sound-toggle" onClick={toggleUfoSound} aria-pressed={ufoSoundEnabled} aria-label={`${ufoSoundEnabled ? 'Tắt' : 'Bật'} âm thanh UFO`}>{ufoSoundEnabled ? '🔊 Âm thanh bật' : '🔇 Âm thanh tắt'}</button>}
      {isUfo && ufoSoundUnavailable && <span className="sound-notice" role="status">Âm thanh chưa sẵn sàng</span>}
      <button className="list-toggle" disabled={rolling} onClick={() => setShowList(value => !value)} aria-expanded={showList}>Danh sách {items.length} món {showList ? '▴' : '▾'}</button>
      {showList && <ol className="menu-list" tabIndex={0}>{items.map((dish, i) => <li key={i}>{dish.name}</li>)}</ol>}
    </div>
    {result && <div className="result-overlay">
      <div className="result-popup" role="dialog" aria-modal="true" aria-labelledby="wheel-result-title" tabIndex={-1} ref={resultDialog}>
        <div className="eyebrow">BỮA TRƯA ĐƯỢC GỌI TÊN ✨</div>
        {result.image && brokenImage !== result.image ? <img className="result-image" src={result.image} alt="" onError={() => setBrokenImage(result.image)} /> : <div className="dish-placeholder" aria-hidden="true">🍱</div>}
        <h2 id="wheel-result-title">{result.name}</h2>
        <p className="price">{result.price != null ? `${formatMoney(result.price)} đ` : 'Chưa có giá'}{result.category ? ` · ${result.category}` : ''}</p>
        <p className="note">Vừa lòng chưa?</p>
        <div className="result-actions">
          <button className="btn btn-primary" onClick={() => onPick(result)}>✓ Chọn món này</button>
          <button className="btn btn-secondary" onClick={spin}>{isUfo ? '↻ Gắp thêm lần nữa' : '↻ Quay thêm lần nữa'}</button>
          <button className="btn close-result" onClick={onClose}>{closeLabel}</button>
        </div>
      </div>
    </div>}
    <style jsx>{`
      .wheel-screen { position: fixed; inset: 0; z-index: 1100; display: flex; flex-direction: column; overflow: hidden; color: var(--text-primary); background: radial-gradient(ellipse at 50% 45%, #35263f 0%, #141320 55%, #0d0e16 100%); padding: 18px 28px; box-sizing: border-box; }
      .ufo-screen { background: radial-gradient(ellipse at 50% 35%, #153c4d, #101524 65%, #0b0f19); }
      .screen-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-shrink: 0; }
      .screen-header > div { text-align: center; }
      h2 { margin: 0; font-size: 1.35rem; }
      .screen-header p { margin: 5px 0 0; font-size: .8rem; color: #b8b4ca; }
      .close { border: 1px solid #fb718566; background: #a52d3c; color: white; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; }
      .close-result { background: #a52d3c; border: 1px solid #fb718566; color: #fff; justify-content: center; }
      .close:hover, .close-result:hover { background: #c7384b; }
      .close:focus-visible, .close-result:focus-visible { outline: 2px solid #fda4af; outline-offset: 3px; }
      .arena { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding: 14px 0 0; }
      .screen-footer { text-align: center; flex-shrink: 0; position: relative; }
      .screen-footer p { font-size: .85rem; margin: 8px 0; color: #ded8e9; }
      .list-toggle { border: 0; background: transparent; color: #f3bd79; padding: 8px; cursor: pointer; }
      .sound-toggle { background: #ffffff0a; border: 1px solid #ffffff26; border-radius: 20px; color: #ded8e9; padding: 6px 12px; font-size: .75rem; cursor: pointer; margin-right: 6px; }
      .sound-toggle:focus-visible { outline: 2px solid #f3bd79; outline-offset: 3px; }
      .sound-notice { display: block; color: #b8b4ca; font-size: .7rem; }
      .menu-list { position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); width: min(640px, 85vw); max-height: 45dvh; overflow: auto; background: #202031; border: 1px solid #ffffff30; border-radius: 16px; text-align: left; padding: 20px 20px 20px 42px; box-sizing: border-box; box-shadow: 0 10px 40px #0008; }
      .menu-list li { padding: 5px; }
      .result-overlay { position: absolute; inset: 0; z-index: 5; background: #080912bb; backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; padding: 20px; }
      .result-popup { width: min(100%, 440px); max-height: 90dvh; overflow: auto; background: #1c1b2b; border: 1px solid #f3bd7955; border-radius: 28px; padding: 28px; text-align: center; box-shadow: 0 24px 90px #0009; animation: reveal .3s ease-out; box-sizing: border-box; }
      .eyebrow { color: #f3bd79; font-size: .7rem; letter-spacing: .12em; font-weight: 700; margin-bottom: 18px; }
      .result-image { width: 112px; height: 112px; object-fit: cover; border-radius: 24px; margin-bottom: 16px; }
      .dish-placeholder { font-size: 64px; margin-bottom: 14px; }
      .result-popup h2 { overflow-wrap: anywhere; font-size: 1.6rem; }
      .price { color: #f3bd79; }
      .note { color: #b8b4ca; font-size: .8rem; line-height: 1.6; }
      .result-actions { display: grid; gap: 10px; margin-top: 22px; }
      @keyframes reveal { from { opacity: 0; transform: translateY(12px) scale(.97); } to { opacity: 1; transform: none; } }
      @media (max-width: 600px) { .wheel-screen { padding: 14px 12px; } .screen-header h2 { font-size: 1rem; } .screen-header p { font-size: .65rem; } .screen-header .btn { font-size: .7rem; padding: 8px; } .close { width: 32px; height: 32px; flex-shrink: 0; } .result-popup { padding: 22px; } }
      @media (max-height: 450px) { .wheel-screen { padding: 8px 12px; } .screen-header h2 { font-size: 1rem; } .screen-header p { display: none; } .screen-footer p { margin: 2px; } .list-toggle { padding: 3px; } }
      @media (prefers-reduced-motion: reduce) { .result-popup { animation: none; } }
    `}</style>
  </div>;
}
