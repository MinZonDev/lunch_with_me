'use client';
import { useEffect, useRef } from 'react';

export const WHEEL_DURATION = 10000;
const COLORS = ['#bc492f', '#237b6a', '#7453a3', '#306fa3', '#a87325', '#a74371'];
const point = (angle, radius) => {
  const radians = (angle - 90) * Math.PI / 180;
  return [160 + radius * Math.cos(radians), 160 + radius * Math.sin(radians)];
};

export default function DishWheel({ items, rotation, rolling, reducedMotion, onSpin, onFinish, itemLabel = 'món', hubIcon = '🍱' }) {
  const rotor = useRef(null);
  const previous = useRef(0);
  const finish = useRef(onFinish);
  useEffect(() => { finish.current = onFinish; }, [onFinish]);
  useEffect(() => {
    const element = rotor.current;
    if (!element || rotation === previous.current) return;
    const from = previous.current;
    previous.current = rotation;
    // A persistent HTML rotor guarantees a real animation from the last angle.
    const animation = element.animate([{ transform: `rotate(${from}deg)` }, { transform: `rotate(${rotation}deg)` }], {
      // Cubic ease-out: start fast, continuously lose speed, finish at rest.
      duration: WHEEL_DURATION, easing: 'cubic-bezier(.333333,1,.666667,1)', fill: 'forwards',
    });
    animation.onfinish = () => {
      element.style.transform = `rotate(${rotation}deg)`;
      animation.cancel(); finish.current();
    };
    return () => { animation.onfinish = null; animation.cancel(); };
  }, [rotation, reducedMotion]);
  const step = 360 / items.length;
  return <div className="wheel" aria-label={`Vòng quay ${items.length} ${itemLabel}`}>
    <span className="pointer" aria-hidden="true" />
    <div ref={rotor} className="rotor" data-wheel-rotor data-motion={reducedMotion ? 'gentle' : 'standard'}>
      <svg viewBox="0 0 320 320" aria-hidden="true">
        {items.map((dish, index) => {
          const start = point(index * step, 155), end = point((index + 1) * step, 155);
          const angle = (index + 0.5) * step, label = point(angle, 145);
          return <g key={index}>
            {items.length === 1 ? <circle data-wheel-sector={index} cx="160" cy="160" r="155" fill={COLORS[0]} /> :
              <path data-wheel-sector={index} d={`M160 160 L${start.join(' ')} A155 155 0 ${step > 180 ? 1 : 0} 1 ${end.join(' ')} Z`} fill={COLORS[index % COLORS.length]} stroke="#fff8" strokeWidth="0.5" />}
            <text x={label[0]} y={label[1]} fill="white" textAnchor="end" dominantBaseline="middle" fontSize={Math.min(8, 440 / items.length)} fontWeight="600"
              transform={`rotate(${angle - 90} ${label[0]} ${label[1]})`}>
              {`${index + 1}. ${dish.name.length > 28 ? `${dish.name.slice(0, 27)}…` : dish.name}`}
            </text>
          </g>;
        })}
        <circle cx="160" cy="160" r="156" fill="none" stroke="#ffd99e" strokeWidth="2" />
      </svg>
    </div>
    <button className="hub" onClick={onSpin} disabled={rolling} aria-label={rolling ? 'Đang quay' : 'Bắt đầu quay'}>
      <span aria-hidden="true">{hubIcon}</span>
    </button>
    <style jsx>{`
      .wheel { position: relative; width: min(88vw, calc(100dvh - 185px), 1000px); aspect-ratio: 1; margin: auto; flex-shrink: 0; }
      .rotor { width: 100%; height: 100%; border-radius: 50%; box-shadow: 0 0 55px #fa984522; will-change: transform; }
      svg { display: block; width: 100%; height: 100%; }
      .pointer { position: absolute; z-index: 2; left: 50%; top: -8px; transform: translateX(-50%); width: 0; height: 0; border-left: 15px solid transparent; border-right: 15px solid transparent; border-top: 32px solid #ffe4b6; filter: drop-shadow(0 3px 3px #0008); }
      .hub { position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%); width: clamp(64px, 15%, 120px); aspect-ratio: 1; border-radius: 50%; border: 4px solid #f7c77d; background: #fff2d6; color: #713b1c; box-shadow: 0 4px 18px #0006; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 3px; }
      .hub span { font-size: clamp(22px, 3vw, 40px); }
      .hub:disabled { cursor: wait; opacity: 1; }
      .hub:focus-visible { outline: 3px solid white; outline-offset: 5px; }
      @media (max-height: 450px) { .wheel { width: min(75vw, calc(100dvh - 115px)); } .hub { border-width: 2px; } }
    `}</style>
  </div>;
}
