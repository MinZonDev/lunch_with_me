import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareUfo, ufoFlight, UFO_SEARCH_MS, ufoLiftDuration, ufoLiftPose } from './ufoDishes.js';

test('empty and single-dish UFO menus', () => {
  assert.equal(prepareUfo([]), null);
  const dish = {name:'Cơm gà'};
  assert.deepEqual(prepareUfo([dish],()=>0),{winner:dish,items:[dish],winnerSlot:0});
});
test('all 100 dishes remain visible in order and every entry can win', () => {
  const menu = Array.from({length:100},(_,i)=>({name:`Món ${i}`}));
  for(let i=0;i<100;i++) {
    const run=prepareUfo(menu,()=>(i+.5)/100);
    assert.equal(run.winner,menu[i]);
    assert.equal(run.items[run.winnerSlot],menu[i]);
    assert.deepEqual(run.items,menu);
    assert.equal(new Set(run.items).size,100);
  }
  assert.deepEqual(menu.map(d=>d.name),Array.from({length:100},(_,i)=>`Món ${i}`));
});
test('flight searches for ten seconds and settles exactly over the winning card',()=>{
  assert.equal(UFO_SEARCH_MS,10000);
  for(const gentle of [false,true]){
    const end=ufoFlight(1,300,290,75,gentle);
    assert.deepEqual(end,{x:75,y:0,tilt:0,scan:0,blend:1});
    const poses=Array.from({length:101},(_,i)=>ufoFlight(i/100,300,290,75,gentle));
    assert.ok(poses.every(p=>Number.isFinite(p.x)&&p.x>=0&&p.x<=600));
    assert.ok(poses.some(p=>p.x>400));
    assert.ok(poses.some(p=>p.x<150));
    assert.ok(poses.some(p=>Math.abs(p.tilt)>1));
  }
});
test('small menus retain every entry and repeated outcomes are allowed',()=>{
  const menu=Array.from({length:5},(_,i)=>({name:`Món ${i}`}));
  const first=prepareUfo(menu,()=>.2),second=prepareUfo(menu,()=>.2);
  assert.deepEqual(new Set(first.items),new Set(menu));
  assert.equal(first.winner,second.winner);
});

test('absorption duration scales with distance instead of a fixed time',()=>{
  assert.ok(ufoLiftDuration(600,100)>ufoLiftDuration(300,100));
  assert.ok(ufoLiftDuration(300,200)>ufoLiftDuration(300,100));
  assert.ok(Number.isFinite(ufoLiftDuration(0,0)));
});

test('card reaches the mouth, fully shrinks, and beam follows the remaining distance',()=>{
  for(const distance of [0,50,300,1000]){
    const poses=Array.from({length:101},(_,i)=>ufoLiftPose(i/100,12,-distance,100));
    assert.equal(poses[0].scale,1);
    assert.equal(poses[0].beamHeight,distance+50);
    for(let i=1;i<poses.length;i++){
      assert.ok(poses[i].scale<=poses[i-1].scale);
      assert.ok(poses[i].beamHeight<=poses[i-1].beamHeight);
      assert.ok(poses[i].y<=poses[i-1].y);
    }
    assert.deepEqual(poses.at(-1),{x:12,y:-distance,scale:0,opacity:0,beamHeight:0});
  }
});
