'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { UFO_SEARCH_MS } from './ufoDishes';

const PREFERENCE_KEY = 'lwm-ufo-sound';

export default function useUfoSound(active) {
  const [enabled, setEnabled] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const enabledRef = useRef(true), audio = useRef(null);
  const deadline = useRef(0), timer = useRef(null);

  const stop = useCallback(() => {
    clearTimeout(timer.current); timer.current = null; deadline.current = 0;
    if (audio.current) { audio.current.pause(); audio.current.currentTime = 0; }
  }, []);

  const playRemaining = useCallback(() => {
    const clip = audio.current;
    const remaining = deadline.current - performance.now();
    if (!clip || !enabledRef.current || remaining <= 0) return;
    // Unmuting resumes the position in the current flight, not a fresh ten seconds.
    if (Number.isFinite(clip.duration) && clip.duration > 0) {
      clip.currentTime = ((UFO_SEARCH_MS - remaining) / 1000) % clip.duration;
    }
    clip.play().then(() => {
      if (audio.current !== clip || !enabledRef.current || performance.now() >= deadline.current) clip.pause();
      else setUnavailable(false);
    }).catch(() => { if (audio.current === clip && enabledRef.current && deadline.current > performance.now()) setUnavailable(true); });
  }, []);

  const start = useCallback(() => {
    stop();
    deadline.current = performance.now() + UFO_SEARCH_MS;
    timer.current = setTimeout(stop, UFO_SEARCH_MS);
    playRemaining();
  }, [stop, playRemaining]);

  const toggle = useCallback(() => {
    const next = !enabledRef.current;
    enabledRef.current = next; setEnabled(next);
    try { localStorage.setItem(PREFERENCE_KEY, String(next)); } catch { /* Optional storage. */ }
    if (next) playRemaining(); else audio.current?.pause();
  }, [playRemaining]);

  useEffect(() => {
    if (!active) return;
    try {
      const saved = localStorage.getItem(PREFERENCE_KEY);
      enabledRef.current = saved !== 'false'; setEnabled(enabledRef.current);
    } catch { /* Default to enabled. */ }
    const clip = new Audio('/sounds/ufo.mp3');
    clip.preload = 'auto'; clip.loop = true; clip.volume = .55;
    clip.onerror = () => { if (audio.current === clip) setUnavailable(true); };
    audio.current = clip;
    clip.load();
    return () => { stop(); clip.onerror = null; clip.removeAttribute('src'); clip.load(); audio.current = null; };
  }, [active, stop]);

  return { enabled, unavailable, start, stop, toggle };
}
