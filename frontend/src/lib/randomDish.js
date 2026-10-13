// Pure helpers for "Random món": text matching, filtering, picking, and the
// one-dish-per-line format admins use to enter a dish list.

// Lowercase, strip Vietnamese diacritics (đ → d), collapse whitespace
export function normalize(text) {
  return (text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'd')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

const lower = (text) => (text || '').normalize('NFC').toLowerCase().replace(/\s+/g, ' ').trim();

// "cơm" / "*cơm*" → contains, "cơm*" → starts with, "*cơm" → ends with.
// Typed without accents ("com") ignores accents; typed with accents ("cơm")
// matches them exactly, so "cơm" doesn't hit "cốm". Case never matters.
export function matchesPattern(name, pattern) {
  const raw = (pattern || '').trim();
  const text = raw.replace(/\*/g, '');
  const accented = normalize(text) !== lower(text);
  const fold = accented ? lower : normalize;
  const needle = fold(text);
  if (!needle) return true;
  const hay = fold(name);
  const lead = raw.startsWith('*');
  const trail = raw.endsWith('*');
  if (trail && !lead) return hay.startsWith(needle);
  if (lead && !trail) return hay.endsWith(needle);
  return hay.includes(needle);
}

// mode: 'all' | 'price' | 'text'; prices are in k (nghìn đồng)
export function filterDishes(dishes, mode, { min = '', max = '', pattern = '' } = {}) {
  if (mode === 'price') {
    const lo = min === '' || min === null ? null : Number(min);
    const hi = max === '' || max === null ? null : Number(max);
    return dishes.filter(d => d.price !== null && d.price !== undefined
      && (lo === null || d.price >= lo) && (hi === null || d.price <= hi));
  }
  if (mode === 'text') return dishes.filter(d => matchesPattern(d.name, pattern));
  return dishes;
}

// Uniform pick; avoids repeating `current` when there is another option
export function pickRandom(candidates, current = null, rand = Math.random) {
  if (!candidates.length) return null;
  const pool = candidates.length > 1 && current
    ? candidates.filter(d => d.name !== current.name || d.price !== current.price)
    : candidates;
  const list = pool.length ? pool : candidates;
  return list[Math.floor(rand() * list.length)];
}

// "Cơm gà xối mỡ 35" | "Canh chua - 15.5k" | "Trà đá: 5.000đ" | "Cơm thêm" (no price)
const LINE = /^(.*?)[\s\-–|:,]*?\s([\d.,]+)\s*(k|nghìn|nghin|đ|d|vnd)?\s*$/i;

export function parsePrice(numText, unit) {
  const u = (unit || '').toLowerCase();
  let s = numText;
  // "35.000" / "35,000" are thousands separators; "15.5" / "15,5" is a decimal
  if (/^\d{1,3}([.,]\d{3})+$/.test(s)) s = s.replace(/[.,]/g, '');
  else s = s.replace(',', '.');
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  if (u === 'k' || u === 'nghìn' || u === 'nghin') return n;
  if (u === 'đ' || u === 'd' || u === 'vnd') return n / 1000;
  return n >= 1000 ? n / 1000 : n; // bare number: ≥1000 must be đồng
}

export function parseDishLines(text) {
  const dishes = [];
  const errors = [];
  (text || '').split(/\r?\n/).forEach((line, idx) => {
    const t = line.trim();
    if (!t) return;
    const m = t.match(LINE);
    if (m && m[1].trim()) {
      const price = parsePrice(m[2], m[3]);
      if (price === null || price < 0 || price > 10000) errors.push(`Dòng ${idx + 1}: giá không hợp lệ`);
      else dishes.push({ name: m[1].trim().slice(0, 100), price });
    } else {
      dishes.push({ name: t.slice(0, 100), price: null });
    }
  });
  return { dishes, errors };
}

export function formatDishLines(dishes) {
  return (dishes || []).map(d => (d.price === null || d.price === undefined ? d.name : `${d.name} ${d.price}`)).join('\n');
}
