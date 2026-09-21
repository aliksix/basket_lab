/* Wspolne narzedzia portalu: ladowanie danych, formatowanie, dymki, nawigacja. */

export const DATA = 'data/';

const cache = new Map();

export async function load(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(DATA + name + '.json').then((r) => {
      if (!r.ok) throw new Error('Nie udało się wczytać ' + name);
      return r.json();
    }));
  }
  return cache.get(name);
}

export function qs(key, fallback = '') {
  return new URLSearchParams(location.search).get(key) ?? fallback;
}

/* --- formatowanie --------------------------------------------------------- */
export const NBSP = ' ';

export function num(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '–';
  return Number(value).toFixed(digits);
}

export function signed(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '–';
  const v = Number(value);
  return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(digits);
}

export function pct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '–';
  return Number(value).toFixed(digits) + '%';
}

export function ordinal(place) {
  return place ? place + '.' : '–';
}

export function dateLabel(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y.slice(2)}`;
}

/* --- kolory --------------------------------------------------------------- */
const SCALE = ['--bad', '--warn', '--mid', '--ok', '--good'];

export function percentileColor(p) {
  if (p === null || p === undefined) return 'var(--ink-muted)';
  const idx = Math.min(SCALE.length - 1, Math.max(0, Math.floor((p / 100) * SCALE.length)));
  return `var(${SCALE[idx]})`;
}

export function rankClass(place, total) {
  if (!place || !total) return '';
  const share = place / total;
  if (share <= 0.3) return 'rank--top';
  if (share >= 0.7) return 'rank--low';
  return 'rank--mid';
}

export function deltaClass(value) {
  if (value === null || value === undefined) return '';
  return value > 0 ? 'delta--up' : value < 0 ? 'delta--down' : '';
}

/* --- dymki ---------------------------------------------------------------- */
let glossary = { metrics: {}, zones: {} };

export async function initTooltips() {
  glossary = await load('glossary');
  const tip = document.createElement('div');
  tip.id = 'tip';
  document.body.appendChild(tip);

  document.addEventListener('pointerover', (event) => {
    const target = event.target.closest('[data-tip],[data-metric]');
    if (!target) return;
    const html = target.dataset.tip || metricTip(target.dataset.metric);
    if (!html) return;
    tip.innerHTML = html;
    tip.classList.add('on');
    place(tip, target);
  });
  document.addEventListener('pointerout', (event) => {
    if (event.target.closest('[data-tip],[data-metric]')) tip.classList.remove('on');
  });
  document.addEventListener('scroll', () => tip.classList.remove('on'), true);
}

function place(tip, target) {
  const box = target.getBoundingClientRect();
  const size = tip.getBoundingClientRect();
  let left = box.left + box.width / 2 - size.width / 2;
  left = Math.max(10, Math.min(left, window.innerWidth - size.width - 10));
  let top = box.bottom + 9;
  if (top + size.height > window.innerHeight - 10) top = box.top - size.height - 9;
  tip.style.left = left + 'px';
  tip.style.top = top + 'px';
}

export function metricTip(key) {
  const entry = glossary.metrics?.[key];
  if (!entry) return '';
  return `<b>${entry.full || entry.label}</b>${entry.desc}${entry.how ? `<em>${entry.how}</em>` : ''}`;
}

export function metricLabel(key, fallback) {
  return glossary.metrics?.[key]?.label || fallback || key;
}

export function zoneTip(zone) {
  const text = glossary.zones?.[zone];
  return text ? `<b>${zoneName(zone)}</b>${text}` : '';
}

const ZONE_NAMES = {
  RIM: 'Spod kosza',
  PAINT: 'Pomalowane',
  SHORT_MID: 'Bliski dystans',
  LONG_MID: 'Daleki średni',
  CORNER_3: 'Trójka z rogu',
  ABOVE_BREAK_3: 'Trójka czołowa',
  // siatka szczegółowa mapy rzutów
  RA: 'Podkoszowe',
  SM_L: 'Bliski dystans, lewa',
  SM_R: 'Bliski dystans, prawa',
  LM_L: 'Średni, lewa',
  LM_LC: 'Średni, lewe skrzydło',
  LM_C: 'Średni, czoło',
  LM_RC: 'Średni, prawe skrzydło',
  LM_R: 'Średni, prawa',
  C3_L: 'Trójka, lewy narożnik',
  C3_R: 'Trójka, prawy narożnik',
  AB3_L: 'Trójka, lewe skrzydło',
  AB3_C: 'Trójka z czoła',
  AB3_R: 'Trójka, prawe skrzydło',
};

export function zoneName(zone) {
  return ZONE_NAMES[zone] || zone;
}

/* --- elementy interfejsu -------------------------------------------------- */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'html') node.innerHTML = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

/** Kafel ze statystyka: duza liczba, miejsce w lidze i dymek z definicja. */
export function statTile({ metric, label, value, rank, total, percentile, hint, suffix = '' }) {
  const head = el('div', { class: 'stat__label' }, metricLabel(metric, label));
  head.append(el('span', { class: 'q', 'data-metric': metric }, '?'));
  const tile = el('div', { class: 'card stat' }, head,
    el('div', { class: 'stat__value' }, value, suffix ? el('small', {}, suffix) : null));
  const foot = el('div', { class: 'stat__foot' });
  if (rank) {
    foot.append(el('span', { class: 'rank ' + rankClass(rank, total) }, `${rank}. w lidze`));
  }
  if (percentile !== undefined && percentile !== null) {
    foot.append(el('span', { class: 'muted' }, `${Math.round(percentile)} pct`));
  }
  if (hint) foot.append(el('span', { class: 'muted' }, hint));
  if (foot.childElementCount) tile.append(foot);
  return tile;
}

/** Wiersz z paskiem percentyla - uzywany w profilach zawodnikow i piatek. */
export function percentileRow({ metric, label, value, percentile, format = (v) => num(v, 1) }) {
  const name = el('div', { class: 'prow__name' }, metricLabel(metric, label));
  if (metric) name.append(el('span', { class: 'q', 'data-metric': metric }, '?'));
  const bar = el('div', { class: 'pbar' });
  const fill = el('i');
  fill.style.width = Math.max(2, percentile ?? 0) + '%';
  fill.style.background = percentileColor(percentile);
  bar.append(fill);
  return el('div', { class: 'prow' }, name, bar,
    el('div', { class: 'prow__val' }, format(value)));
}

/** Prosta tabela z sortowaniem po kliknieciu w naglowek. */
export function dataTable(columns, rows, { sort = null, desc = true, highlight = () => false } = {}) {
  const wrap = el('div', { class: 'table-wrap' });
  const table = el('table', { class: 'data' });
  const thead = el('thead');
  const tbody = el('tbody');
  let sortKey = sort ?? columns[0].key;
  let sortDesc = desc;

  function render() {
    const sorted = [...rows].sort((a, b) => {
      const col = columns.find((c) => c.key === sortKey);
      const av = col.sortValue ? col.sortValue(a) : a[sortKey];
      const bv = col.sortValue ? col.sortValue(b) : b[sortKey];
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const cmp = typeof av === 'string' ? av.localeCompare(bv, 'pl') : av - bv;
      return sortDesc ? -cmp : cmp;
    });
    tbody.replaceChildren(...sorted.map((row) => {
      const tr = el('tr', { class: highlight(row) ? 'is-club' : null });
      for (const col of columns) {
        const cell = col.render ? col.render(row) : num(row[col.key], col.digits ?? 1);
        tr.append(el('td', {}, cell));
      }
      return tr;
    }));
    thead.querySelectorAll('th').forEach((th) => {
      th.classList.toggle('sort-dir', th.dataset.key === sortKey);
      th.classList.toggle('asc', th.dataset.key === sortKey && !sortDesc);
    });
  }

  thead.append(el('tr', {}, columns.map((col) => el('th', {
    'data-key': col.key,
    'data-metric': col.metric || null,
    onclick: () => {
      if (sortKey === col.key) sortDesc = !sortDesc;
      else { sortKey = col.key; sortDesc = col.asc !== true; }
      render();
    },
  }, col.label))));

  table.append(thead, tbody);
  wrap.append(table);
  render();
  return wrap;
}

/* --- szkielet strony ------------------------------------------------------ */
const NAV = [
  ['index.html', 'home', 'Zespół', 'M3 10.5 12 3l9 7.5M5 9.5V20h14V9.5'],
  ['players.html', 'players', 'Zawodnicy', 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 20a8 8 0 0 1 16 0'],
  ['lineups.html', 'lineups', 'Piątki', 'M4 6h7v5H4zM13 6h7v5h-7zM4 13h7v5H4zM13 13h7v5h-7z'],
  ['games.html', 'games', 'Mecze', 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM3 12h18M12 3c3 4 3 14 0 18M12 3c-3 4-3 14 0 18'],
  ['scout.html', 'scout', 'Skauting', 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM16 16l5 5'],
  ['league.html', 'league', 'Liga', 'M4 19V9m5 10V5m5 14v-7m5 7V8'],
];

export async function mountChrome(active) {
  const meta = await load('meta');
  const bar = document.querySelector('[data-nav]');
  if (bar) {
    bar.innerHTML = `
      <div class="topbar__inner">
        <a class="brand" href="index.html">
          ${meta.club.logo ? `<img src="${meta.club.logo}" alt="">` : ''}
          <span><b>${meta.club.name}</b><small>PERFORMANCE LAB</small></span>
        </a>
        <nav class="nav">
          ${NAV.map(([href, key, label, path]) => `
            <a href="${href}" ${active === key ? 'aria-current="page"' : ''}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
                   stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>
              ${label}
            </a>`).join('')}
        </nav>
        <div class="topbar__right">
          <span class="topbar__chip">${meta.competition} · ${meta.season}</span>
          <span class="topbar__chip">${meta.league_games} meczów w bazie</span>
          <button class="icon-btn" id="theme" title="Zmień motyw">◐</button>
        </div>
      </div>`;
    bar.querySelector('#theme').addEventListener('click', toggleTheme);
  }

  const foot = document.querySelector('[data-footer]');
  if (foot) {
    foot.innerHTML = `<div class="wrap" style="padding:0">
      ${meta.competition} · sezon ${meta.season} ·
      dane wygenerowane ${meta.generated_at.replace('T', ' ').replace('+00:00', ' UTC')}<br>
      Źródła: ${meta.sources.join(' · ')}</div>`;
  }
  return meta;
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('bl-theme', next);
}

export function restoreTheme() {
  const saved = localStorage.getItem('bl-theme');
  if (saved) document.documentElement.dataset.theme = saved;
}

/** Sciezka nawigacyjna nad naglowkiem strony. */
export function crumbs(...parts) {
  const node = el('div', { class: 'crumbs' });
  parts.forEach((part, i) => {
    if (i) node.append(el('span', {}, '/'));
    node.append(Array.isArray(part) ? el('a', { href: part[1] }, part[0]) : el('b', {}, part));
  });
  return node;
}

/**
 * Okragla ikona zawodnika - ciasny kadr na glowe.
 *
 * Uzywana tam, gdzie zdjecie jest tylko znacznikiem: w tabelach, przy piatkach
 * i duetach. Kadr jest wypalony w pliku przez `basketlab photos`, wiec kolo
 * nie wymaga zadnego skalowania w CSS.
 */
export function avatar(player, extra = '') {
  const frame = el('span', { class: ('avatar ' + extra).trim(), title: player?.name || '' });
  const src = player?.icon || player?.photo;
  if (src) frame.append(el('img', { src, alt: player.name || '', loading: 'lazy' }));
  else frame.append(el('i', { class: 'avatar__initials' }, initials(player?.name)));
  return frame;
}

/** Inicjaly zamiast zdjecia - zawodnicy rywali nie maja wycietych portretow. */
export function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

/** Prostokatny portret zawodnika - na kartach i w naglowku profilu. */
export function portrait(player, extra = '') {
  const frame = el('span', { class: ('portrait ' + extra).trim(), title: player?.name || '' });
  if (player?.photo) {
    frame.append(el('img', { src: player.photo, alt: player.name || '', loading: 'lazy' }));
  }
  return frame;
}

export function fail(node, error) {
  console.error(error);
  node.replaceChildren(el('div', { class: 'empty' },
    'Nie udało się wczytać danych. ' + (error?.message || '')));
}
