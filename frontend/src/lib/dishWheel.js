// Every eligible entry has one fixed sector; picking never rearranges the wheel.
export function prepareWheel(candidates, rand = Math.random) {
  if (!candidates.length) return null;
  const winnerIndex = Math.floor(rand() * candidates.length);
  return {
    winner: candidates[winnerIndex],
    items: candidates,
    winnerSlot: winnerIndex,
  };
}

// Segment zero starts at twelve o'clock; land its midpoint under the pointer.
export function wheelLanding(previousRotation, winnerSlot, count, turns = 12) {
  const target = (360 - (winnerSlot + 0.5) * (360 / count)) % 360;
  return previousRotation + 360 * turns + (target - previousRotation % 360 + 360) % 360;
}
