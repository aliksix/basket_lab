/* Lekkie wykresy inline (SVG, bez bibliotek) - slupki, linia formy, mapa stylu. */

import { el, num, dateLabel, percentileColor, zoneName } from './core.js';

const NS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs = {}) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) node.setAttribute(k, v);
  return node;
};

/** Slupki wokol zera - np. NET rating mecz po meczu. */
export function divergingBars(points, { height = 110, format = (v) => num(v, 1), label = () => '' } = {}) {
  const values = points.map((p) => p.value).filter((v) => v !== null && v !== undefined);
  const max = Math.max(1, ...values.map(Math.abs));
  const wrap = el('div', { class: 'bars', style: `height:${height}px` });
  for (const point of points) {
    const v = point.value ?? 0;
    const share = Math.abs(v) / max;
    const bar = el('div', {
      style: `height:${Math.max(2, share * 100)}%;`
        + `background:${v >= 0 ? 'var(--good)' : 'var(--bad)'};`
        + `align-self:${v >= 0 ? 'flex-end' : 'flex-start'};opacity:${0.45 + 0.55 * share}`,
      'data-tip': `<b>${point.title || ''}</b>${label(point)}${format(point.value)}`,
    });
    wrap.append(bar);
  }
  return wrap;
}

/** Linia formy z pasmem sredniej kroczacej. */
export function formLine(points, { width = 520, height = 150, rolling = 5, format = (v) => num(v, 1) } = {}) {
  const values = points.map((p) => p.value);
  const clean = values.filter((v) => v !== null && v !== undefined);
  if (!clean.length) return el('div', { class: 'empty' }, 'Za mało danych');
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const pad = { l: 34, r: 8, t: 10, b: 20 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const x = (i) => pad.l + (points.length < 2 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v) => pad.t + innerH - ((v - min) / span) * innerH;

  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, class: 'chart' });
  const zero = min <= 0 && max >= 0 ? y(0) : null;
  if (zero !== null) {
    svg.append(svgEl('line', { x1: pad.l, x2: width - pad.r, y1: zero, y2: zero, stroke: 'var(--border)', 'stroke-width': 1 }));
  }

  const avg = rollingMean(values, rolling);
  svg.append(path(avg.map((v, i) => [x(i), v === null ? null : y(v)]), 'var(--brand)', 2.4, 0.55));
  svg.append(path(points.map((p, i) => [x(i), p.value === null ? null : y(p.value)]), 'var(--ink-dim)', 1.2, 0.55));

  points.forEach((point, i) => {
    if (point.value === null || point.value === undefined) return;
    const dot = svgEl('circle', { cx: x(i), cy: y(point.value), r: 3.4, fill: 'var(--ink)' });
    dot.dataset.tip = `<b>${point.title || dateLabel(point.date)}</b>${format(point.value)}`;
    svg.append(dot);
  });

  for (const v of [max, min]) {
    const t = svgEl('text', { x: 4, y: y(v) + 4, fill: 'var(--ink-muted)', 'font-size': 10 });
    t.textContent = format(v);
    svg.append(t);
  }
  return svg;
}

function path(coords, stroke, width, opacity) {
  let d = '';
  let pen = false;
  for (const [px, py] of coords) {
    if (py === null) { pen = false; continue; }
    d += (pen ? ' L ' : ' M ') + px + ' ' + py;
    pen = true;
  }
  return svgEl('path', { d: d.trim(), fill: 'none', stroke, 'stroke-width': width, 'stroke-opacity': opacity, 'stroke-linejoin': 'round' });
}

export function rollingMean(values, window) {
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - window + 1), i + 1).filter((v) => v !== null && v !== undefined);
    if (!slice.length) return null;
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });
}


/* --- wykres radarowy umiejetnosci ------------------------------------------ */
/**
 * Radar percentyli. Kazda os ma wartosc 0-100, wiec siatka jest porownywalna
 * miedzy zawodnikami - punkt na obwodzie to najlepszy wynik w lidze.
 */
export function radar(axes, { size = 200, levels = 4, compact = false } = {}) {
  const usable = axes.filter((a) => a.value !== null && a.value !== undefined);
  if (usable.length < 3) return el('div', { class: 'empty' }, 'Za mało danych');

  // margines musi zmiescic podpis wychodzacy poziomo poza ostatni pierscien:
  // odstep od siatki (9) + szerokosc tekstu (ok. 5.6 px na znak)
  const caption = (a) => String((compact ? a.short : a.axis) ?? a.label ?? '');
  const longest = Math.max(...axes.map((a) => caption(a).length));
  const pad = Math.min(size * 0.3, 12 + 9 + longest * (compact ? 5.6 : 5.9));
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - pad;
  const n = axes.length;
  const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const point = (i, value) => [
    cx + r * (value / 100) * Math.cos(angle(i)),
    cy + r * (value / 100) * Math.sin(angle(i)),
  ];
  const ring = (value) => axes.map((_, i) => point(i, value).join(' ')).join(' L ');

  const svg = svgEl('svg', { viewBox: `0 0 ${size} ${size}`, class: 'radar' });

  for (let level = 1; level <= levels; level += 1) {
    svg.append(svgEl('path', {
      d: `M ${ring((100 * level) / levels)} Z`,
      class: 'radar__grid',
    }));
  }
  axes.forEach((_, i) => {
    const [x, y] = point(i, 100);
    svg.append(svgEl('line', { x1: cx, y1: cy, x2: x, y2: y, class: 'radar__spoke' }));
  });

  svg.append(svgEl('path', {
    d: `M ${axes.map((a, i) => point(i, Math.max(a.value ?? 0, 2)).join(' ')).join(' L ')} Z`,
    class: 'radar__area',
  }));

  axes.forEach((axis, i) => {
    const [x, y] = point(i, Math.max(axis.value ?? 0, 2));
    const dot = svgEl('circle', { cx: x, cy: y, r: compact ? 2.6 : 3.4, fill: percentileColor(axis.value) });
    dot.dataset.tip = `<b>${axis.label}</b>${axis.display ?? '–'}`
      + `<em>${axis.value === null || axis.value === undefined ? 'brak danych' : Math.round(axis.value) + '. percentyl w lidze'}</em>`;
    svg.append(dot);

    const [lx, ly] = point(i, 100);
    const dx = Math.cos(angle(i));
    const dy = Math.sin(angle(i));
    const anchor = dx > 0.25 ? 'start' : dx < -0.25 ? 'end' : 'middle';
    const node = svgEl('text', {
      x: lx + dx * 9,
      y: ly + dy * 9 + 3.5,
      class: 'radar__label',
      'text-anchor': anchor,
    });
    node.textContent = caption(axis);
    node.dataset.tip = `<b>${axis.label}</b>${axis.display ?? '–'}`;
    svg.append(node);
  });
  return svg;
}

/** Kolor punktu wedlug bilansu na 100 posiadan (+/- 15 to skrajnosci skali). */
export function netColor(net) {
  if (net === null || net === undefined) return 'var(--ink-muted)';
  const t = Math.max(-1, Math.min(1, net / 15));
  const stop = t >= 0 ? '--good' : '--bad';
  const alpha = 35 + Math.round(55 * Math.abs(t));
  return `color-mix(in srgb, var(${stop}) ${alpha}%, var(--surface-3))`;
}

/* --- mapa stylu ------------------------------------------------------------ */
//: kandydaci na pozycje podpisu wokol punktu: [dx, dy, wyrownanie]
const LABEL_SLOTS = [
  [10, 3.5, 'start'], [-10, 3.5, 'end'],
  [0, -10, 'middle'], [0, 17, 'middle'],
  [9, -7, 'start'], [-9, -7, 'end'],
  [9, 14, 'start'], [-9, 14, 'end'],
];

function overlaps(a, b) {
  return !(a.x2 < b.x1 || b.x2 < a.x1 || a.y2 < b.y1 || b.y2 < a.y1);
}

/** Trzyliterowy skrot nazwy druzyny, gdy zrodlo nie poda wlasnego. */
function teamCode(team) {
  if (team.short) return team.short;
  const words = String(team.name || team.key || '').split(/\s+/).filter((w) => w.length > 2);
  const main = words[words.length - 1] || team.name || '';
  return main.slice(0, 3).toUpperCase();
}

/**
 * Mapa stylu: tempo w pionie, rozklad rzutow w poziomie, kolor = bilans.
 * Podpisy szukaja wolnego miejsca wokol punktu; jesli zadne nie jest wolne,
 * zostaje sam punkt z dymkiem - lepiej pominac etykiete niz zlepic dwie.
 */
export function styleMap(teams, { highlight = null, width = 660, height = 460 } = {}) {
  const pad = { l: 54, r: 26, t: 30, b: 46 };
  const points = teams.filter((t) => Number.isFinite(t.x) && Number.isFinite(t.y));
  if (!points.length) return el('div', { class: 'empty' }, 'Brak danych');

  const xr = niceRange(points.map((t) => t.x));
  const yr = niceRange(points.map((t) => t.y));
  const sx = (v) => pad.l + ((v - xr.min) / (xr.max - xr.min)) * (width - pad.l - pad.r);
  const sy = (v) => height - pad.b - ((v - yr.min) / (yr.max - yr.min)) * (height - pad.t - pad.b);

  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, class: 'chart' });

  // siatka i osie liczbowe
  for (const value of xr.ticks) {
    svg.append(svgEl('line', {
      x1: sx(value), x2: sx(value), y1: pad.t, y2: height - pad.b,
      stroke: 'var(--border-soft)', 'stroke-width': 1,
    }));
    svg.append(text(sx(value), height - pad.b + 16, num(value, 0), 'middle', 'var(--ink-muted)', 10));
  }
  for (const value of yr.ticks) {
    svg.append(svgEl('line', {
      x1: pad.l, x2: width - pad.r, y1: sy(value), y2: sy(value),
      stroke: 'var(--border-soft)', 'stroke-width': 1,
    }));
    svg.append(text(pad.l - 9, sy(value) + 3.5, num(value, 0), 'end', 'var(--ink-muted)', 10));
  }

  // srednie ligi jako osie odniesienia
  const meanX = points.reduce((sum, t) => sum + t.x, 0) / points.length;
  const meanY = points.reduce((sum, t) => sum + t.y, 0) / points.length;
  for (const [x1, y1, x2, y2] of [
    [sx(meanX), pad.t, sx(meanX), height - pad.b],
    [pad.l, sy(meanY), width - pad.r, sy(meanY)],
  ]) {
    svg.append(svgEl('line', { x1, y1, x2, y2, stroke: 'var(--border)', 'stroke-dasharray': '4 4' }));
  }

  // opisy cwiartek i osi
  svg.append(text(width / 2, height - 6, 'udział rzutów za 3 (%)', 'middle', 'var(--ink-dim)', 11));
  const axisY = svgEl('text', {
    x: 14, y: height / 2, 'font-size': 11, fill: 'var(--ink-dim)', 'text-anchor': 'middle',
    transform: `rotate(-90 14 ${height / 2})`,
  });
  axisY.textContent = 'tempo (posiadania na 40 min)';
  svg.append(axisY);
  for (const [label, x, y, anchor] of [
    ['szybko + gra pod koszem', pad.l + 4, pad.t + 13, 'start'],
    ['szybko + gra za 3', width - pad.r - 4, pad.t + 13, 'end'],
    ['wolno + gra pod koszem', pad.l + 4, height - pad.b - 7, 'start'],
    ['wolno + gra za 3', width - pad.r - 4, height - pad.b - 7, 'end'],
  ]) {
    svg.append(text(x, y, label, anchor, 'var(--ink-muted)', 9.5, .75));
  }

  // punkty: najpierw klub, potem druzyny o najwiekszym bilansie - one dostaja
  // podpis w pierwszej kolejnosci, gdy miejsca zabraknie
  const order = [...points].sort((a, b) => {
    if (a.key === highlight) return -1;
    if (b.key === highlight) return 1;
    return Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0);
  });

  const dots = order.map((team) => ({
    team,
    cx: sx(team.x),
    cy: sy(team.y),
    r: team.key === highlight ? 7.5 : 5.5,
  }));
  const blocked = dots.map((d) => ({ x1: d.cx - d.r - 2, x2: d.cx + d.r + 2, y1: d.cy - d.r - 2, y2: d.cy + d.r + 2 }));

  const dotLayer = svgEl('g');
  const labelLayer = svgEl('g');
  for (const dot of dots) {
    const isClub = dot.team.key === highlight;
    const node = svgEl('circle', {
      cx: dot.cx, cy: dot.cy, r: dot.r,
      fill: dot.team.color || 'var(--ink-muted)',
      stroke: isClub ? 'var(--brand)' : 'var(--surface)',
      'stroke-width': isClub ? 3 : 1.5,
    });
    node.dataset.tip = `<b>${dot.team.name}</b>${dot.team.tip || ''}`;
    dotLayer.append(node);

    const code = teamCode(dot.team);
    const w = code.length * 6.2 + 4;
    const slot = LABEL_SLOTS.map(([dx, dy, anchor]) => {
      const x = dot.cx + dx;
      const y = dot.cy + dy;
      const x1 = anchor === 'start' ? x : anchor === 'end' ? x - w : x - w / 2;
      return { x, y, anchor, box: { x1, x2: x1 + w, y1: y - 9, y2: y + 3 } };
    }).find((candidate) => (
      candidate.box.x1 > pad.l - 6 && candidate.box.x2 < width - pad.r + 6
      && candidate.box.y1 > pad.t - 6 && candidate.box.y2 < height - pad.b + 6
      && !blocked.some((box) => overlaps(box, candidate.box))
    ));
    if (!slot) continue;
    blocked.push(slot.box);
    labelLayer.append(text(slot.x, slot.y, code, slot.anchor,
      isClub ? 'var(--brand)' : 'var(--ink-dim)', 10.5, 1, isClub ? 700 : 600));
  }
  svg.append(dotLayer, labelLayer);
  return svg;
}

function text(x, y, value, anchor, fill, size, opacity = 1, weight = 400) {
  const node = svgEl('text', {
    x, y, 'font-size': size, fill, 'text-anchor': anchor,
    'fill-opacity': opacity, 'font-weight': weight,
  });
  node.textContent = value;
  return node;
}

/** Zakres osi rozszerzony o margines, z czytelnymi podzialkami. */
function niceRange(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = (max - min) || 1;
  const lo = min - span * 0.12;
  const hi = max + span * 0.12;
  const step = niceStep((hi - lo) / 4);
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(Math.round(v * 100) / 100);
  return { min: lo, max: hi, ticks };
}

function niceStep(raw) {
  const mag = 10 ** Math.floor(Math.log10(Math.abs(raw) || 1));
  const norm = raw / mag;
  const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return step * mag;
}

/** Poziomy pasek z podzialem na strefy - rozklad rzutow. */
export function shotDiet(profile) {
  const order = ['RIM', 'PAINT', 'SHORT_MID', 'LONG_MID', 'CORNER_3', 'ABOVE_BREAK_3'];
  const colors = {
    RIM: 'var(--good)', PAINT: 'var(--ok)', SHORT_MID: 'var(--mid)',
    LONG_MID: 'var(--bad)', CORNER_3: 'var(--brand)', ABOVE_BREAK_3: 'var(--brand-dim)',
  };
  const row = el('div', { style: 'display:flex;height:22px;border-radius:7px;overflow:hidden;gap:1px' });
  for (const zone of order) {
    const freq = profile?.[zone]?.freq || 0;
    if (freq <= 0) continue;
    row.append(el('div', {
      style: `width:${freq}%;background:${colors[zone]}`,
      'data-tip': `<b>${zoneName(zone)}</b>${num(freq, 1)}% prób · ${num(profile[zone].pps, 2)} PPS`,
    }));
  }
  return row;
}
