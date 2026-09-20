/* Polowa boiska FIBA, mapa rzutow, mapa stref i siatka heksagonalna.

   Uklad SVG jest w metrach: 15 m szerokosci na 14 m dlugosci polowy boiska,
   kosz 1.575 m od linii koncowej (na dole rysunku). Kat 0 prowadzi od kosza
   prosto w strone srodka boiska, +90 to prawa linia boczna - dokladnie tak samo
   jak w klasyfikatorze stref w ekstraktorze, wiec rysunek i liczby opisuja te
   same obszary.

   Wymiary sa zgodne z przepisami FIBA (nie NBA): boisko 28 x 15 m, pole
   trzech sekund 4.9 m szerokosci i 5.8 m dlugosci, luk za 3 punkty o promieniu
   6.75 m, naroznik 6.60 m w odleglosci 0.90 m od linii bocznej. */

import { el, num, zoneName } from './core.js';

export const W = 15;
export const L = 14;
export const HOOP = { x: 7.5, y: L - 1.575 };

const KEY_HALF = 2.45;
const FT_LINE = 5.80;
const FT_CIRCLE = 1.80;
const ARC = 6.75;
const CORNER_X = 0.90;
const CORNER_BREAK_Y = L - (Math.sqrt(ARC * ARC - 6.6 * 6.6) + 1.575);
const RA_R = 1.25;
const LONG_MID_R = 4.50;

const NS = 'http://www.w3.org/2000/svg';
let uid = 0;

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  return node;
}

function polar(r, a) {
  const rad = (a * Math.PI) / 180;
  return { x: HOOP.x + r * Math.sin(rad), y: HOOP.y - r * Math.cos(rad) };
}

/** Wycinek pierscienia miedzy promieniami r1-r2 i katami a1-a2 (stopnie). */
function sector(r1, r2, a1, a2) {
  const large = Math.abs(a2 - a1) > 180 ? 1 : 0;
  const i1 = polar(r1, a1);
  const o1 = polar(r2, a1);
  const o2 = polar(r2, a2);
  const i2 = polar(r1, a2);
  return `M ${i1.x} ${i1.y} L ${o1.x} ${o1.y}`
    + ` A ${r2} ${r2} 0 ${large} 1 ${o2.x} ${o2.y}`
    + ` L ${i2.x} ${i2.y}`
    + ` A ${r1} ${r1} 0 ${large} 0 ${i1.x} ${i1.y} Z`;
}

const disc = (cx, cy, r) =>
  `M ${cx - r} ${cy} a ${r} ${r} 0 1 0 ${2 * r} 0 a ${r} ${r} 0 1 0 ${-2 * r} 0`;
const box = (x, y, w, h) => `M ${x} ${y} h ${w} v ${h} h ${-w} Z`;

const COURT = box(0, 0, W, L);
const KEY = box(HOOP.x - KEY_HALF, L - FT_LINE, KEY_HALF * 2, FT_LINE);
const THREE_REGION = `M ${CORNER_X} ${L} L ${CORNER_X} ${CORNER_BREAK_Y}`
  + ` A ${ARC} ${ARC} 0 0 1 ${W - CORNER_X} ${CORNER_BREAK_Y} L ${W - CORNER_X} ${L} Z`;

/** Strefy szczegolowe - odpowiadaja `court.classify_detailed` w ekstraktorze. */
const ZONE_SHAPES = {
  RA: { d: disc(HOOP.x, HOOP.y, RA_R), label: [HOOP.x, HOOP.y - 0.1], clip: null },
  PAINT: { d: `${KEY} ${disc(HOOP.x, HOOP.y, RA_R)}`, label: [HOOP.x, 10.05], clip: null },

  SM_L: { d: sector(RA_R, LONG_MID_R, -179.9, 0), label: [3.95, 12.4], clip: 'key' },
  SM_R: { d: sector(RA_R, LONG_MID_R, 0, 179.9), label: [11.05, 12.4], clip: 'key' },

  LM_L: { d: sector(LONG_MID_R, 9.5, -179.9, -54), label: [2.55, 10.8], clip: 'in3key' },
  LM_LC: { d: sector(LONG_MID_R, 9.5, -54, -18), label: [4.05, 8.15], clip: 'in3key' },
  LM_C: { d: sector(LONG_MID_R, 9.5, -18, 18), label: [HOOP.x, 6.85], clip: 'in3key' },
  LM_RC: { d: sector(LONG_MID_R, 9.5, 18, 54), label: [10.95, 8.15], clip: 'in3key' },
  LM_R: { d: sector(LONG_MID_R, 9.5, 54, 179.9), label: [12.45, 10.8], clip: 'in3key' },

  C3_L: { d: box(0, CORNER_BREAK_Y, CORNER_X, L - CORNER_BREAK_Y), label: [1.15, 12.85], clip: null },
  C3_R: { d: box(W - CORNER_X, CORNER_BREAK_Y, CORNER_X, L - CORNER_BREAK_Y), label: [13.85, 12.85], clip: null },

  AB3_L: { d: sector(6.0, 22, -179.9, -22), label: [1.75, 8.1], clip: 'out3' },
  AB3_C: { d: sector(6.0, 22, -22, 22), label: [HOOP.x, 4.6], clip: 'out3' },
  AB3_R: { d: sector(6.0, 22, 22, 179.9), label: [13.25, 8.1], clip: 'out3' },
};

export const DETAILED_ZONES = Object.keys(ZONE_SHAPES);

/* --- kolory --------------------------------------------------------------- */
//: przy ilu probach ufamy roznicy wzgledem ligi w polowie
const TRUST = 8;

/**
 * Skala czerwony - bursztyn - zielony wedlug PPS wzgledem ligi (+/- 0.3 pkt).
 * ``attempts`` sciaga kolor do neutralnego przy malej probie - jedna trafiona
 * trojka nie powinna zabarwiac calej strefy na intensywna zielen.
 */
export function efficiencyColor(diff, { strength = 1, attempts = null } = {}) {
  if (diff === null || diff === undefined) return 'var(--zone-empty)';
  const trust = attempts === null ? 1 : attempts / (attempts + TRUST);
  const t = Math.max(-1, Math.min(1, (diff / 0.3) * trust));
  const a = Math.abs(t);
  if (a < 0.04) return 'var(--zone-empty)';
  const stop = t >= 0
    ? (a < 0.5 ? '--zone-ok' : '--zone-good')
    : (a < 0.5 ? '--zone-warn' : '--zone-bad');
  const alpha = (0.18 + 0.62 * a) * strength;
  return `color-mix(in srgb, var(${stop}) ${Math.round(alpha * 100)}%, var(--zone-empty))`;
}

/* --- boisko ---------------------------------------------------------------- */
function courtLines() {
  const group = svgEl('g', { class: 'lines' });
  const add = (tag, attrs) => group.append(svgEl(tag, { class: 'line', ...attrs }));

  add('rect', { x: 0.05, y: 0.05, width: W - 0.1, height: L - 0.1, rx: 0.1 });
  // pole trzech sekund, kolo rzutow wolnych (dolna polowa przerywana)
  add('rect', { x: HOOP.x - KEY_HALF, y: L - FT_LINE, width: KEY_HALF * 2, height: FT_LINE });
  add('path', {
    d: `M ${HOOP.x - FT_CIRCLE} ${L - FT_LINE} A ${FT_CIRCLE} ${FT_CIRCLE} 0 0 1 ${HOOP.x + FT_CIRCLE} ${L - FT_LINE}`,
  });
  add('path', {
    d: `M ${HOOP.x - FT_CIRCLE} ${L - FT_LINE} A ${FT_CIRCLE} ${FT_CIRCLE} 0 0 0 ${HOOP.x + FT_CIRCLE} ${L - FT_LINE}`,
    'stroke-dasharray': '0.34 0.28',
  });
  // znaczniki miejsc do zbiorki przy rzutach wolnych
  for (const offset of [1.75, 2.65, 3.55]) {
    add('line', { x1: HOOP.x - KEY_HALF, y1: L - offset, x2: HOOP.x - KEY_HALF - 0.28, y2: L - offset });
    add('line', { x1: HOOP.x + KEY_HALF, y1: L - offset, x2: HOOP.x + KEY_HALF + 0.28, y2: L - offset });
  }
  // obrecz, tablica i polkole bez szarzy
  add('path', { d: `M ${HOOP.x - RA_R} ${HOOP.y} A ${RA_R} ${RA_R} 0 0 1 ${HOOP.x + RA_R} ${HOOP.y}` });
  add('line', { x1: HOOP.x - 0.9, y1: L - 1.2, x2: HOOP.x + 0.9, y2: L - 1.2 });
  add('line', { x1: HOOP.x, y1: L - 1.2, x2: HOOP.x, y2: HOOP.y - 0.2 });
  add('circle', { cx: HOOP.x, cy: HOOP.y, r: 0.225 });
  // linia za 3 punkty i srodek boiska
  add('path', {
    d: `M ${CORNER_X} ${L} L ${CORNER_X} ${CORNER_BREAK_Y}`
      + ` A ${ARC} ${ARC} 0 0 1 ${W - CORNER_X} ${CORNER_BREAK_Y} L ${W - CORNER_X} ${L}`,
  });
  add('circle', { cx: HOOP.x, cy: 0, r: 1.8 });
  return group;
}

function clipDefs(id) {
  const defs = svgEl('defs');
  const paths = {
    court: COURT,
    key: `${COURT} ${KEY}`,
    in3: THREE_REGION,
    out3: `${COURT} ${THREE_REGION}`,
    band: box(CORNER_X, 0, W - 2 * CORNER_X, L),
  };
  for (const [name, d] of Object.entries(paths)) {
    const clip = svgEl('clipPath', { id: `${id}-${name}`, clipPathUnits: 'userSpaceOnUse' });
    clip.append(svgEl('path', { d, 'clip-rule': 'evenodd' }));
    defs.append(clip);
  }
  return defs;
}

/* --- warstwa stref --------------------------------------------------------- */
function zoneLayer(id, profile, league, { strength = 1, labels = true } = {}) {
  const root = svgEl('g', { class: 'zones', 'clip-path': `url(#${id}-court)` });
  const outsideKey = svgEl('g', { 'clip-path': `url(#${id}-key)` });
  const inArc = svgEl('g', { 'clip-path': `url(#${id}-in3)` });
  const inArcOutsideKey = svgEl('g', { 'clip-path': `url(#${id}-key)` });
  inArc.append(inArcOutsideKey);
  const outArc = svgEl('g', { 'clip-path': `url(#${id}-out3)` });
  const outArcBand = svgEl('g', { 'clip-path': `url(#${id}-band)` });
  outArc.append(outArcBand);
  root.append(outsideKey, inArc, outArc);

  const buckets = { key: outsideKey, in3key: inArcOutsideKey, out3: outArcBand };
  const labelLayer = svgEl('g', { class: 'zone-labels' });

  for (const [zone, shape] of Object.entries(ZONE_SHAPES)) {
    const values = profile?.[zone] || {};
    const base = league?.[zone]?.pps;
    const pps = values.pps;
    const diff = pps === null || pps === undefined || base === null || base === undefined
      ? null : pps - base;

    const path = svgEl('path', {
      class: 'zone',
      d: shape.d,
      'fill-rule': 'evenodd',
      fill: efficiencyColor(values.fga ? diff : null, { strength, attempts: values.fga }),
    });
    path.dataset.tip = `<b>${zoneName(zone)}</b>`
      + `${values.fgm ?? 0}/${values.fga ?? 0} · ${num(values.fg_pct, 1)}% · ${num(pps, 2)} PPS`
      + `<em>${num(values.freq, 1)}% prób · liga ${num(base, 2)} PPS`
      + `${diff === null ? '' : ` · ${diff >= 0 ? '+' : '−'}${Math.abs(diff).toFixed(2)}`}</em>`;
    (shape.clip ? buckets[shape.clip] : root).append(path);

    if (labels && values.fga) {
      labelLayer.append(zoneTag(shape.label[0], shape.label[1], values));
    }
  }

  const wrap = svgEl('g');
  wrap.append(root, labelLayer);
  return wrap;
}

function zoneTag(x, y, values) {
  const group = svgEl('g', { class: 'zone-tag' });
  const w = 1.9;
  const h = 1.12;
  group.append(svgEl('rect', { class: 'zone-tag__bg', x: x - w / 2, y: y - h / 2, width: w, height: h, rx: 0.2 }));
  const top = svgEl('text', { class: 'zone-tag__a', x, y: y - 0.05 });
  top.textContent = `${values.fgm ?? 0}/${values.fga ?? 0}`;
  const bottom = svgEl('text', { class: 'zone-tag__b', x, y: y + 0.43 });
  bottom.textContent = `${num(values.fg_pct, 0)}%`;
  group.append(top, bottom);
  return group;
}

/* --- znaczniki rzutow ------------------------------------------------------ */
export function toCourt(shot) {
  return { x: (shot.y / 100) * W, y: L - (shot.x / 100) * L };
}

function markerLayers(shots, size) {
  const missed = svgEl('g', { class: 'marks' });
  const made = svgEl('g', { class: 'marks' });
  for (const shot of shots) {
    const p = toCourt(shot);
    const tip = `<b>${shot.made ? 'Trafiony' : 'Niecelny'}</b>`
      + `${zoneName(shot.zone14 || shot.zone)} · ${num(shot.dist, 1)} m`
      + (shot.type ? `<em>${shot.type}</em>` : '');
    if (shot.made) {
      const node = svgEl('circle', { class: 'shot-made', cx: p.x, cy: p.y, r: size });
      node.dataset.tip = tip;
      made.append(node);
    } else {
      const d = size * 0.8;
      const node = svgEl('path', {
        class: 'shot-miss',
        d: `M ${p.x - d} ${p.y - d} L ${p.x + d} ${p.y + d} M ${p.x - d} ${p.y + d} L ${p.x + d} ${p.y - d}`,
      });
      node.dataset.tip = tip;
      missed.append(node);
    }
  }
  return [missed, made];
}

/* --- siatka heksagonalna (inspiracja: kafelki Hudl) ------------------------ */
const HEX_SIZE = 0.95;

function hexKey(px, py) {
  const q = (2 / 3) * (px / HEX_SIZE);
  const r = (-1 / 3) * (px / HEX_SIZE) + (Math.sqrt(3) / 3) * (py / HEX_SIZE);
  return roundHex(q, r);
}

function roundHex(q, r) {
  const s = -q - r;
  let rq = Math.round(q);
  let rr = Math.round(r);
  const rs = Math.round(s);
  const dq = Math.abs(rq - q);
  const dr = Math.abs(rr - r);
  const ds = Math.abs(rs - s);
  if (dq > dr && dq > ds) rq = -rr - rs;
  else if (dr > ds) rr = -rq - rs;
  return [rq, rr];
}

function hexCenter(q, r) {
  return {
    x: HEX_SIZE * 1.5 * q,
    y: HEX_SIZE * Math.sqrt(3) * (r + q / 2),
  };
}

function hexPath(cx, cy, radius) {
  const points = [];
  for (let i = 0; i < 6; i += 1) {
    const a = (Math.PI / 180) * (60 * i);
    points.push(`${(cx + radius * Math.cos(a)).toFixed(3)} ${(cy + radius * Math.sin(a)).toFixed(3)}`);
  }
  return 'M ' + points.join(' L ') + ' Z';
}

/**
 * Kafelki heksagonalne: wielkosc = liczba prob, kolor = punkty na rzut
 * wzgledem tego, czego liga oczekuje po takich pozycjach.
 */
function hexLayer(id, shots, league) {
  const bins = new Map();
  for (const shot of shots) {
    const p = toCourt(shot);
    const [q, r] = hexKey(p.x, p.y);
    const key = q + ':' + r;
    const bin = bins.get(key) || { q, r, fga: 0, fgm: 0, pts: 0, expected: 0 };
    bin.fga += 1;
    if (shot.made) {
      bin.fgm += 1;
      bin.pts += shot.three ? 3 : 2;
    }
    const base = league?.[shot.zone14]?.pps;
    if (base !== null && base !== undefined) bin.expected += base;
    bins.set(key, bin);
  }

  const group = svgEl('g', { class: 'hexes', 'clip-path': `url(#${id}-court)` });
  const max = Math.max(1, ...[...bins.values()].map((b) => b.fga));
  for (const bin of bins.values()) {
    const center = hexCenter(bin.q, bin.r);
    const share = Math.sqrt(bin.fga / max);
    const radius = HEX_SIZE * (0.34 + 0.62 * share);
    const pps = bin.pts / bin.fga;
    const expected = bin.expected ? bin.expected / bin.fga : null;
    const diff = expected === null ? null : pps - expected;
    const node = svgEl('path', {
      class: 'hex',
      d: hexPath(center.x, center.y, radius),
      fill: efficiencyColor(diff, { attempts: bin.fga }),
    });
    node.dataset.tip = `<b>${bin.fgm}/${bin.fga} z tego miejsca</b>`
      + `${num(100 * bin.fgm / bin.fga, 1)}% · ${num(pps, 2)} PPS`
      + `<em>oczekiwane ${num(expected, 2)} PPS`
      + `${diff === null ? '' : ` · ${diff >= 0 ? '+' : '−'}${Math.abs(diff).toFixed(2)}`}</em>`;
    group.append(node);
  }
  return group;
}

/* --- publiczne API --------------------------------------------------------- */
export const SHOT_MODES = [
  ['shots', 'Rzuty'],
  ['zones', 'Strefy'],
  ['hex', 'Hex'],
  ['both', 'Oba'],
];

/**
 * Mapa rzutow. ``mode``:
 *   'shots' - same znaczniki, 'zones' - strefy z podpisami,
 *   'hex'   - kafelki heksagonalne, 'both' - strefy pod znacznikami.
 */
export function shotChart(shots, profile, league, { mode = 'both', size = 0.2 } = {}) {
  const id = 'c' + (uid += 1);
  const svg = svgEl('svg', {
    class: 'court',
    viewBox: `0 0 ${W} ${L}`,
    preserveAspectRatio: 'xMidYMid meet',
  });
  svg.append(clipDefs(id));
  svg.append(svgEl('rect', { class: 'floor', x: 0, y: 0, width: W, height: L, rx: 0.1 }));

  if (mode === 'zones' || mode === 'both') {
    svg.append(zoneLayer(id, profile, league, {
      strength: mode === 'both' ? 0.5 : 1,
      labels: mode === 'zones',
    }));
  }
  if (mode === 'hex') svg.append(hexLayer(id, shots, league));
  svg.append(courtLines());
  if (mode === 'shots' || mode === 'both') svg.append(...markerLayers(shots, size));
  return svg;
}

export function shotModeSwitch(current, onChange) {
  const seg = el('div', { class: 'seg seg--sm' });
  for (const [key, label] of SHOT_MODES) {
    seg.append(el('button', {
      class: current === key ? 'is-on' : '',
      onclick: () => onChange(key),
    }, label));
  }
  return seg;
}

export function shotLegend(mode = 'both') {
  const items = [];
  if (mode === 'shots' || mode === 'both') {
    items.push(el('span', { class: 'legend__item' }, el('i', { class: 'legend__made' }), 'trafiony'));
    items.push(el('span', { class: 'legend__item' }, el('i', { class: 'legend__miss' }), 'niecelny'));
  }
  if (mode === 'hex') {
    items.push(el('span', { class: 'legend__item' }, 'wielkość = liczba prób'));
  }
  if (mode !== 'shots') {
    items.push(el('span', { class: 'legend__item legend__scale' },
      el('span', { class: 'muted' }, 'poniżej ligi'),
      el('i', { class: 'legend__ramp' }),
      el('span', { class: 'muted' }, 'powyżej')));
  }
  return el('div', { class: 'legend' }, items);
}
