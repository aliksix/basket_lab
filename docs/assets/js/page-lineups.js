/* Lista piatek i duetow - odtworzone ze zmian w play-by-play. */

import {
  avatar, dataTable, el, fail, initTooltips, load, mountChrome, num, restoreTheme, signed,
} from './core.js';
import { clutchRatings, fgaLongRate, pppLong } from './metrics.js';

restoreTheme();

const state = { minPoss: 0, sort: 'poss', view: 'cards', clutch: false };
let players;
let lineups;
let pairs;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  await mountChrome('lineups');
  [players, lineups, pairs] = await Promise.all([load('players'), load('lineups'), load('pairs')]);
  renderFilters();
  render();
}

export function playerOf(key) {
  return players.find((p) => p.key === key) || { name: key.split(':').pop().replace(/-/g, ' '), photo: '' };
}

export function avatars(keys) {
  return el('div', { class: 'avatars' }, keys.map((key) => avatar(playerOf(key), 'avatar--tiny')));
}

export function nameList(keys) {
  return keys.map((k) => shortName(playerOf(k).name)).join(' · ');
}

export function shortName(name) {
  const parts = String(name).trim().split(/\s+/);
  if (parts.length < 2) return name;
  return parts[0][0] + '. ' + parts.slice(1).join(' ');
}

function poss(lineup) {
  return (lineup.off_poss || 0) + (lineup.def_poss || 0);
}

/** Piatka sprowadzona do wybranego trybu: caly mecz albo same koncowki. */
function view(lineup) {
  if (!state.clutch) return lineup;
  const c = clutchRatings(lineup.clutch || {});
  return {
    ...lineup,
    min: c.min,
    off_poss: c.off_poss,
    def_poss: c.def_poss,
    pts: c.pts,
    opp_pts: c.opp_pts,
    ortg: c.ortg,
    drtg: c.drtg,
    net: c.net,
    ff: {}, opp_ff: {},
  };
}

function renderFilters() {
  const bar = document.getElementById('filters');
  const seg = el('div', { class: 'seg' },
    el('button', { class: state.view === 'cards' ? 'is-on' : '', onclick: () => { state.view = 'cards'; renderFilters(); render(); } }, 'Karty'),
    el('button', { class: state.view === 'table' ? 'is-on' : '', onclick: () => { state.view = 'table'; renderFilters(); render(); } }, 'Tabela'),
    el('button', { class: state.view === 'pairs' ? 'is-on' : '', onclick: () => { state.view = 'pairs'; renderFilters(); render(); } }, 'Duety'));

  const clutch = el('div', { class: 'seg' },
    el('button', { class: !state.clutch ? 'is-on' : '', onclick: () => { state.clutch = false; renderFilters(); render(); } }, 'Cały mecz'),
    el('button', { class: state.clutch ? 'is-on' : '', onclick: () => { state.clutch = true; renderFilters(); render(); } }, 'Clutch'));

  const min = el('select', { onchange: (e) => { state.minPoss = Number(e.target.value); render(); } },
    el('option', { value: 0 }, 'wszystkie piątki'),
    ...[10, 15, 25, 40, 60, 100].map((v) => el('option', { value: v }, `min. ${v} posiadań`)));
  min.value = String(state.minPoss);

  const sort = el('select', { onchange: (e) => { state.sort = e.target.value; render(); } },
    el('option', { value: 'net' }, 'Sortuj: NET'),
    el('option', { value: 'poss' }, 'Sortuj: posiadania'),
    el('option', { value: 'ortg' }, 'Sortuj: atak'),
    el('option', { value: 'drtg' }, 'Sortuj: obrona'));
  sort.value = state.sort;

  bar.replaceChildren(seg, clutch, min, sort,
    el('div', { class: 'filters__note' },
      state.clutch
        ? 'Końcówki: ostatnie 5 minut IV kwarty i dogrywki przy różnicy do 5 punktów'
        : `${lineups.length} piątek w bazie · ratingi są bardzo wrażliwe na próbę, patrz na liczbę posiadań`));
}

function sorted(list) {
  const key = state.sort;
  return [...list].sort((a, b) => {
    if (key === 'poss') return poss(b) - poss(a);
    if (key === 'drtg') return (a.drtg ?? 999) - (b.drtg ?? 999);
    return (b[key] ?? -999) - (a[key] ?? -999);
  });
}

function render() {
  const content = document.getElementById('content');
  if (state.view === 'pairs') {
    content.replaceChildren(pairsView());
    return;
  }
  const list = sorted(lineups.map(view).filter((l) => poss(l) >= Math.max(state.minPoss, state.clutch ? 1 : 0)));
  if (!list.length) {
    content.replaceChildren(el('div', { class: 'card empty' },
      state.clutch
        ? 'Żadna piątka nie zagrała jeszcze w końcówce przy wyrównanym wyniku.'
        : 'Żadna piątka nie zagrała tylu posiadań.'));
    return;
  }
  content.replaceChildren(state.view === 'cards' ? cards(list) : table(list));
}

function cards(list) {
  return el('div', { class: 'grid grid--3' }, list.map((lineup) => el('a', {
    class: 'card ptile', href: `lineup.html?l=${encodeURIComponent(lineup.id)}`,
    style: 'padding:16px 18px',
  },
    el('div', { style: 'display:flex;align-items:center;gap:12px' },
      avatars(lineup.players),
      el('div', { style: 'margin-left:auto;text-align:right' },
        el('div', { class: 'stat__value', style: 'font-size:1.55rem' },
          el('span', { class: (lineup.net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(lineup.net, 1))),
        el('div', { class: 'card__sub' }, 'NET / 100'))),
    el('div', { style: 'margin-top:10px;font-size:.84rem;line-height:1.35' }, nameList(lineup.players)),
    el('div', { class: 'chips', style: 'margin-top:10px' },
      el('span', { class: 'chip' }, `${num(lineup.min, 1)} min`),
      el('span', { class: 'chip' }, `${num(poss(lineup), 0)} pos`),
      el('span', { class: 'chip chip--brand' }, `OFF ${num(lineup.ortg, 1)}`),
      el('span', { class: 'chip' }, `DEF ${num(lineup.drtg, 1)}`),
      state.clutch ? null : el('span', { class: 'chip', 'data-metric': 'ppp_long' },
        `PPP +15 ${num(pppLong(lineup.long15 || {}), 2)}`)))));
}

function table(list) {
  const columns = [
    { key: 'players', label: 'Piątka', sortValue: (r) => nameList(r.players),
      render: (r) => el('a', { href: `lineup.html?l=${encodeURIComponent(r.id)}`, style: 'color:var(--brand)' }, nameList(r.players)) },
    { key: 'min', label: 'MIN' },
    { key: 'poss', label: 'POS', metric: 'poss', sortValue: poss, render: (r) => num(poss(r), 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg' },
    { key: 'drtg', label: 'DEF', metric: 'drtg' },
    { key: 'net', label: 'NET', metric: 'net', render: (r) => el('span', { class: (r.net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(r.net, 1)) },
    { key: 'efg', label: 'eFG%', metric: 'efg', sortValue: (r) => r.ff?.efg, render: (r) => num(r.ff?.efg, 1) },
    { key: 'tov', label: 'TOV%', metric: 'tov_rate', sortValue: (r) => r.ff?.tov_rate, render: (r) => num(r.ff?.tov_rate, 1) },
    { key: 'oefg', label: 'opp eFG%', metric: 'efg', sortValue: (r) => r.opp_ff?.efg, render: (r) => num(r.opp_ff?.efg, 1) },
    { key: 'otov', label: 'opp TOV%', metric: 'tov_rate', sortValue: (r) => r.opp_ff?.tov_rate, render: (r) => num(r.opp_ff?.tov_rate, 1) },
    { key: 'fga15', label: '%FGA +15', metric: 'fga_long_rate',
      sortValue: (r) => fgaLongRate(r.long15 || {}), render: (r) => num(fgaLongRate(r.long15 || {}), 1) },
    { key: 'ppp15', label: 'PPP +15', metric: 'ppp_long',
      sortValue: (r) => pppLong(r.long15 || {}), render: (r) => num(pppLong(r.long15 || {}), 2) },
  ];
  return el('div', { class: 'card' }, dataTable(columns, list, { sort: 'net', desc: true }));
}

/* --- duety ----------------------------------------------------------------- */
function pairsView() {
  const byPlayer = new Map();
  for (const player of players) byPlayer.set(player.key, player);

  const rows = pairs.filter((p) => poss(p) >= state.minPoss).map((pair) => {
    const [a, b] = pair.players;
    const soloA = soloNet(a, b);
    const soloB = soloNet(b, a);
    const apart = soloA === null && soloB === null ? null
      : ((soloA ?? 0) + (soloB ?? 0)) / ((soloA === null ? 0 : 1) + (soloB === null ? 0 : 1));
    return {
      ...pair,
      a, b,
      apart,
      synergy: pair.net === null || apart === null ? null : pair.net - apart,
    };
  });

  const columns = [
    { key: 'pair', label: 'Duet', sortValue: (r) => nameList(r.players), render: (r) => el('span', {}, nameList(r.players)) },
    { key: 'min', label: 'MIN' },
    { key: 'poss', label: 'POS', sortValue: poss, render: (r) => num(poss(r), 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg' },
    { key: 'drtg', label: 'DEF', metric: 'drtg' },
    { key: 'net', label: 'RAZEM', metric: 'net', render: (r) => signed(r.net, 1) },
    { key: 'apart', label: 'OSOBNO', render: (r) => signed(r.apart, 1) },
    { key: 'synergy', label: 'SYNERGIA', metric: 'synergy',
      render: (r) => el('span', { class: (r.synergy ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(r.synergy, 1)) },
  ];

  return el('div', {},
    el('div', { class: 'card', style: 'margin-bottom:14px' },
      el('div', { class: 'card__head' }, el('h2', {}, 'Kto komu pomaga'),
        el('span', { class: 'card__sub' }, 'SYNERGIA = bilans razem minus średni bilans każdego z osobna')),
      dataTable(columns, rows, { sort: 'synergy', desc: true })));

  function soloNet(key, without) {
    const player = byPlayer.get(key);
    if (!player) return null;
    const together = pairs.find((p) => p.players.includes(key) && p.players.includes(without));
    const onNet = player.on_off?.on_net;
    if (onNet === null || onNet === undefined || !together) return null;
    const onPoss = (player.on_off?.on_poss || 0) + (player.on_off?.on_def_poss || 0);
    const pairPoss = poss(together);
    const rest = onPoss - pairPoss;
    if (rest <= 20) return null;
    // bilans "bez partnera" = reszta posiadan zawodnika poza wspolnym czasem
    return (onNet * onPoss - (together.net ?? 0) * pairPoss) / rest;
  }
}
