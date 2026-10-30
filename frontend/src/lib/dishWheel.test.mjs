import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareWheel, wheelLanding } from './dishWheel.js';

test('empty and single-dish menus', () => {
  assert.equal(prepareWheel([]), null);
  const dish = { name: 'Cơm gà' };
  const spin = prepareWheel([dish], () => 0);
  assert.equal(spin.winner, dish);
  assert.deepEqual(spin.items, [dish]);
});

test('every menu entry can win and all sectors keep their original order', () => {
  const menu = Array.from({ length: 100 }, (_, id) => ({ name: `Món ${id}` }));
  for (let winner = 0; winner < menu.length; winner++) {
    const spin = prepareWheel(menu, () => (winner + 0.5) / menu.length);
    assert.equal(spin.winner, menu[winner]);
    assert.deepEqual(spin.items, menu);
    assert.equal(new Set(spin.items).size, 100);
    assert.equal(spin.items[spin.winnerSlot], spin.winner);
  }
});

test('pointer lands on the winning segment across consecutive spins', () => {
  let rotation = 0;
  for (const turns of [4, 12]) {
  for (const count of [1, 2, 3, 7, 14, 25, 50, 100]) {
    for (let slot = 0; slot < count; slot++) {
      const next = wheelLanding(rotation, slot, count, turns);
      assert.ok(next >= rotation + turns * 360);
      const pointerAngle = (next + (slot + 0.5) * 360 / count) % 360;
      assert.ok(Math.min(pointerAngle, 360 - pointerAngle) < 0.000001);
      rotation = next;
    }
  }
  }
});

test('14, 25, 50 and 100 eligible dishes always produce exactly that many sectors', () => {
  for (const count of [14, 25, 50, 100]) {
    const menu = Array.from({ length: count }, (_, i) => ({ name: `Món ${i}` }));
    assert.equal(prepareWheel(menu).items.length, count);
    assert.equal(prepareWheel(menu.slice(0, 14)).items.length, 14);
  }
});

test('successive spins may repeat a result', () => {
  const menu = [{ name: 'A' }, { name: 'B' }];
  assert.equal(prepareWheel(menu, () => 0).winner, prepareWheel(menu, () => 0).winner);
});
