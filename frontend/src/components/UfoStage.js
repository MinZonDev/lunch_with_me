'use client';
import { useEffect, useRef, useState } from 'react';
import { formatMoney } from '@/lib/api';
import { ufoFlight, UFO_SEARCH_MS, ufoLiftDuration, ufoLiftPose } from '@/lib/ufoDishes';

function DishCard({ dish, number }) {
  const [broken, setBroken] = useState(false);
  return <>
    {dish.image && !broken ? <img src={dish.image} alt="" onError={() => setBroken(true)} /> : <span className="food-icon" aria-hidden="true">🍱</span>}
    <div className="dish-copy"><span className="number">{number}</span><strong title={dish.name}>{dish.name}</strong><small>{dish.price != null ? `${formatMoney(dish.price)} đ` : 'Chưa có giá'}</small></div>
    <style jsx>{`
      img, .food-icon { width: 48px; height: 48px; border-radius: 12px; object-fit: cover; flex-shrink: 0; }
      .food-icon { display: grid; place-items: center; font-size: 30px; background: #75f4e311; }
      .dish-copy { min-width: 0; text-align: left; }
      .number { color: #75f4e3; font-size: .6rem; }
      strong { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: .78rem; line-height: 1.4; }
      small { display: block; color: #b7c4d5; font-size: .65rem; margin-top: 3px; }
      @media (max-width: 600px) { img, .food-icon { width: 34px; height: 34px; font-size: 24px; } strong { font-size: .6rem; } small { font-size: .55rem; } }
    `}</style>
  </>;
}

export default function UfoStage({ items, run, rolling, reducedMotion, onSpin, onFinish, onSearchEnd }) {
  const board = useRef(null), ship = useRef(null), beam = useRef(null), viewport = useRef(null);
  const finish = useRef(onFinish);
  const endSearch = useRef(onSearchEnd);
  useEffect(() => { finish.current = onFinish; }, [onFinish]);
  useEffect(() => { endSearch.current = onSearchEnd; }, [onSearchEnd]);
  useEffect(() => {
    if (!run) return;
    // React clears DOM refs before passive unmount cleanup. Capture this run's
    // elements so teardown never dereferences a ref that has become null.
    const boardElement = board.current;
    const shipElement = ship.current;
    const beamElement = beam.current;
    const pane = viewport.current;
    if (!boardElement || !shipElement || !beamElement || !pane) return;
    const card = boardElement.querySelector(`[data-ufo-card="${run.winnerSlot}"]`);
    if (!card) return;
    const bounds = boardElement.getBoundingClientRect();
    const target = card.getBoundingClientRect();
    const width = shipElement.offsetWidth;
    const center = bounds.width / 2 - width / 2;
    const landing = target.left - bounds.left + target.width / 2 - width / 2;
    const maxScroll = Math.max(0, pane.scrollHeight - pane.clientHeight);
    const targetScroll = Math.max(0, Math.min(maxScroll, card.offsetTop - (pane.clientHeight - card.offsetHeight) / 2));
    let frame, started, cancelled = false;
    const animations = [];
    const beginLift = () => {
      // Copy the winning card outside the scroll pane so it can rise all the
      // way into the beam, without being clipped by the menu's overflow.
      const rect = card.getBoundingClientRect();
      const scene = boardElement.getBoundingClientRect();
      const saucer = shipElement.querySelector('button').getBoundingClientRect();
      const mouth = { x: saucer.left + saucer.width / 2, y: saucer.top + saucer.height * .72 };
      const deltaX = mouth.x - (rect.left + rect.width / 2);
      const deltaY = mouth.y - (rect.top + rect.height / 2);
      const duration = ufoLiftDuration(Math.hypot(deltaX, deltaY), Math.max(rect.width, rect.height));
      const ghost = card.cloneNode(true);
      ghost.removeAttribute('data-ufo-card'); ghost.setAttribute('aria-hidden', 'true');
      Object.assign(ghost.style, {position:'absolute',left:`${rect.left-scene.left}px`,top:`${rect.top-scene.top}px`,width:`${rect.width}px`,height:`${rect.height}px`,margin:'0',zIndex:'4',boxSizing:'border-box',transformOrigin:'50% 50%',willChange:'transform, opacity'});
      boardElement.appendChild(ghost);
      card.style.visibility = 'hidden';
      beamElement.style.top = `${mouth.y - saucer.top}px`;
      let liftStarted;
      const absorb = now => {
        if (cancelled) return;
        liftStarted ??= now;
        const t = Math.min(1, (now - liftStarted) / duration);
        const pose = ufoLiftPose(t, deltaX, deltaY, rect.height);
        ghost.style.transform = `translate3d(${pose.x}px,${pose.y}px,0) scale(${pose.scale})`;
        ghost.style.opacity = String(pose.opacity);
        beamElement.style.height = `${pose.beamHeight}px`;
        beamElement.style.opacity = String(Math.min(1, t * 12) * Math.min(1, (1 - t) * 12));
        if (t < 1) frame = requestAnimationFrame(absorb);
        else {
          ghost.remove();
          beamElement.style.opacity = '0';
          // Allow the fully absorbed state to paint before presenting the result.
          frame = requestAnimationFrame(() => { if (!cancelled) finish.current(); });
        }
      };
      animations.push({ cancel: () => { ghost.remove(); card.style.visibility = ''; beamElement.style.opacity = '0'; beamElement.style.height = '0px'; } });
      frame = requestAnimationFrame(absorb);
    };
    const scout = now => {
      if (cancelled) return;
      started ??= now;
      const t = Math.min(1, (now - started) / UFO_SEARCH_MS);
      const pose = ufoFlight(t, center, Math.max(0, center - 8), landing, reducedMotion);
      shipElement.style.transform = `translate3d(${pose.x}px,${pose.y}px,0) rotate(${pose.tilt}deg)`;
      pane.scrollTop = pose.scan * maxScroll + pose.blend * targetScroll;
      if (t < 1) frame = requestAnimationFrame(scout);
      else { pane.scrollTop = targetScroll; endSearch.current?.(); beginLift(); }
    };
    frame = requestAnimationFrame(scout);
    return () => { cancelled = true; cancelAnimationFrame(frame); animations.forEach(a=>a.cancel()); };
  }, [run, reducedMotion]);
  const visible = run?.items || items;
  return <section className="ufo-stage" aria-label="UFO gắp món">
    <p className="mission">{rolling ? 'Đang dò tìm tín hiệu món ngon…' : 'Chạm vào UFO để bắt đầu nhiệm vụ'}</p>
    <div className="board" ref={board}>
      <div className="stars" aria-hidden="true">✧ · ✦ · ✧ · ✦ · ✧ · ✦ · ✧</div>
      <div className="ship" ref={ship}>
        <button className="saucer" onClick={onSpin} disabled={rolling} aria-label={rolling ? 'UFO đang gắp món' : 'Bắt đầu gắp món'}>
          <svg viewBox="0 0 160 90" aria-hidden="true"><defs><linearGradient id="ufo-glass" x2="0" y2="1"><stop stopColor="#a7fff4"/><stop offset="1" stopColor="#277e9a"/></linearGradient></defs><path d="M42 49 Q45 4 80 5 Q115 4 118 49" fill="url(#ufo-glass)" stroke="#a7fff4" strokeWidth="2"/><ellipse cx="80" cy="51" rx="73" ry="21" fill="#7069b0" stroke="#d6caff" strokeWidth="3"/><ellipse cx="80" cy="57" rx="48" ry="13" fill="#283851"/><path d="M52 63 Q80 75 108 63" stroke="#75f4e3" strokeWidth="5" fill="none"/>{[30,55,80,105,130].map(x=><circle key={x} cx={x} cy="48" r="4" fill="#fff0a3"/>)}</svg>
        </button>
        <div className="beam" ref={beam} aria-hidden="true" />
      </div>
      <div className={`card-viewport ${rolling ? 'scanning' : ''}`} ref={viewport} tabIndex={rolling ? -1 : 0} aria-label={`Danh sách đầy đủ ${items.length} món, cuộn để xem`}>
        <div className="cards">{visible.map((dish,i)=><div key={`${run?.id || 0}-${i}`} className="dish" data-ufo-card={i}><DishCard dish={dish} number={i+1}/></div>)}</div>
      </div>
    </div>
    <style jsx>{`
      .ufo-stage { width: min(1200px, 94vw); height: min(720px, calc(100dvh - 170px)); display: flex; flex-direction: column; margin: auto; }
      .mission { text-align: center; color: #8af6e3; font-size: .85rem; margin: 0 0 8px; flex-shrink: 0; }
      .board { position: relative; flex: 1; min-height: 0; border: 1px solid #82e8ff30; border-radius: 28px; background: radial-gradient(ellipse at 50% 0%, #203e5c88, #121727 70%); overflow: hidden; }
      .stars { position: absolute; inset: 14px 16px auto; color: #85d8ff88; word-spacing: 2vw; text-align: center; font-size: 22px; pointer-events: none; }
      .ship { position: absolute; z-index: 5; top: 8px; left: 0; width: 120px; transform: translate(calc(min(1200px, 94vw) / 2 - 60px),0); will-change: transform; }
      .saucer { display: block; position: relative; z-index: 2; width: 100%; padding: 0; border: 0; background: transparent; cursor: pointer; filter: drop-shadow(0 0 12px #75f4e34a); }
      .saucer:disabled { cursor: wait; opacity: 1; }
      .saucer:focus-visible { outline: 2px solid #a7fff4; border-radius: 50%; }
      svg { display: block; width: 100%; }
      .beam { position: absolute; top: 54px; left: -18%; width: 136%; opacity: 0; background: linear-gradient(90deg,#00dcb388,#60ffccc9 32%,#d6ff94f5 50%,#60ffccc9 68%,#00dcb388); clip-path: polygon(35% 0,65% 0,100% 100%,0 100%); filter: drop-shadow(0 0 15px #51ffc9); pointer-events: none; }
      .card-viewport { position: absolute; inset: 110px 18px 18px; overflow: auto; overscroll-behavior: contain; scrollbar-color: #75f4e3 #192234; scrollbar-width: thin; }
      .card-viewport.scanning { overflow: hidden; }
      .cards { position: relative; display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); grid-auto-rows: minmax(90px,auto); gap: 12px; padding: 3px; }
      .dish { position: relative; z-index: 1; min-height: 0; display: flex; align-items: center; gap: 10px; padding: 10px; background: #222a40; border: 1px solid #9fffee30; border-radius: 16px; box-shadow: 0 8px 15px #0003; }
      @media (max-width:900px) { .cards { grid-template-columns: repeat(3,minmax(0,1fr)); } }
      @media (max-width:600px) { .ufo-stage { height: min(680px, calc(100dvh - 185px)); } .card-viewport { left: 8px; right: 8px; bottom: 12px; } .cards { gap: 7px; grid-auto-rows: minmax(112px,auto); } .dish { flex-direction: column; align-items: stretch; justify-content: center; padding: 7px; gap: 4px; border-radius: 12px; } .mission { font-size: .75rem; } }
      @media (max-height:450px) { .ufo-stage { height: calc(100dvh - 125px); } .mission { display: none; } .card-viewport { top: 78px; bottom: 8px; } .cards { gap: 5px; } .dish { padding: 2px 6px; gap: 4px; } .ship { width: 90px; } }
    `}</style>
  </section>;
}
