// Every eligible dish stays on the board, in its original order.
export function prepareUfo(candidates, rand = Math.random) {
  if (!candidates.length) return null;
  const winnerIndex = Math.floor(rand() * candidates.length);
  return { winner: candidates[winnerIndex], items: candidates, winnerSlot: winnerIndex };
}

export const UFO_SEARCH_MS = 10000;
// Time comes from actual travel plus the distance needed to shrink the card.
// No fixed-duration jump: long paths take longer than short paths.
export function ufoLiftDuration(distance, cardSize) {
  return Math.max(1, (Math.max(0, distance) + Math.max(0, cardSize) * .5) / .22);
}

export function ufoLiftPose(progress, deltaX, deltaY, cardHeight) {
  const t = Math.max(0, Math.min(1, progress));
  if (t === 1) return { x: deltaX, y: deltaY, scale: 0, opacity: 0, beamHeight: 0 };
  const travel = t * t * (3 - 2 * t);
  const scale = (1 - travel) ** .8;
  return {
    x: deltaX * travel,
    y: deltaY * travel,
    scale,
    opacity: Math.min(1, (1 - travel) / .08),
    beamHeight: Math.max(0, -deltaY * (1 - travel) + cardHeight * scale / 2),
  };
}

// Integrated decreasing speed: rapid sweeps first, gently settle at the target.
export function ufoFlight(progress, center, amplitude, target, reducedMotion = false) {
  const t = Math.max(0, Math.min(1, progress));
  if (t === 1) return { x: target, y: 0, tilt: 0, scan: 0, blend: 1 };
  const travel = 1 - (1 - t) ** 3;
  const phase = travel * Math.PI * (reducedMotion ? 6 : 10);
  const settle = Math.max(0, (t - .75) / .25);
  const blend = settle * settle * (3 - 2 * settle);
  return {
    x: (center + Math.sin(phase) * amplitude * (reducedMotion ? .65 : 1)) * (1 - blend) + target * blend,
    y: Math.sin(phase * 2) * (reducedMotion ? 2 : 7) * (1 - blend),
    tilt: Math.cos(phase) * (reducedMotion ? 3 : 9) * (1 - blend),
    scan: (.5 - .5 * Math.cos(phase / 2)) * (1 - blend),
    blend,
  };
}
