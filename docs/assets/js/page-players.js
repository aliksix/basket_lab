/* Kafle zawodnikow - skrot profilu: wplyw, percentyle umiejetnosci, podstawy. */

import {
  avatar, dataTable, el, fail, initTooltips, load, metricLabel, mountChrome,
  num, percentileColor, restoreTheme, signed,
} from './core.js';

restoreTheme();

const SKILLS = [
  { key: 'scoring', label: 'Punkty', metric: 'ts', pick: (p) => p.percentiles?.ts },
  { key: 'creation', label: 'Kreowanie', metric: 'ast_rate', pick: (p) => p.percentiles?.ast_rate },
  { key: 'rebounding', label: 'Zbiórki', metric: 'trb_rate', pick: (p) => p.percentiles?.trb_rate },
  { key: 'defense', label: 'Obrona', metric: 'impact_def', pick: (p) => p.percentiles?.def },
  { key: 'usage', label: 'Udział', metric: 'usage', pick: (p) => p.percentiles?.usage },
];

const state = { sort: 'impact', view: 'tiles', search: '' };
let meta;
let players;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('players');
  players = await load('players');
  renderFilters();
  render();
}

function renderFilters() {
  const bar = document.getElementById('filters');
  const sortSelect = el('select', {
    onchange: (e) => { state.sort = e.target.value; render(); },
  },
    el('option', { value: 'impact' }, 'Sortuj: Impact'),
    el('option', { value: 'min' }, 'Sortuj: minuty'),
    el('option', { value: 'pts' }, 'Sortuj: punkty na mecz'),
    el('option', { value: 'usage' }, 'Sortuj: USG%'),
    el('option', { value: 'ts' }, 'Sortuj: TS%'),
    el('option', { value: 'net' }, 'Sortuj: NET on/off'));
  sortSelect.value = state.sort;

  const seg = el('div', { class: 'seg' },
    el('button', { class: state.view === 'tiles' ? 'is-on' : '', onclick: () => { state.view = 'tiles'; renderFilters(); render(); } }, 'Kafle'),
    el('button', { class: state.view === 'table' ? 'is-on' : '', onclick: () => { state.view = 'table'; renderFilters(); render(); } }, 'Tabela'));

  bar.replaceChildren(seg, sortSelect,
    el('input', {
      type: 'search', placeholder: 'Szukaj zawodnika…', value: state.search,
      oninput: (e) => { state.search = e.target.value; render(); },
    }),
    el('div', { class: 'filters__note' },
      'Percentyle liczone wśród zawodników ligi z min. 120 minutami'));
}

function sortValue(player) {
  switch (state.sort) {
    case 'min': return player.min || 0;
    case 'pts': return player.metrics?.per_game?.pts || 0;
    case 'usage': return player.metrics?.usage || 0;
    case 'ts': return player.metrics?.ts || 0;
    case 'net': return player.on_off?.diff ?? -999;
    default: return player.impact?.total ?? -999;
  }
}

function visible() {
  const needle = state.search.trim().toLowerCase();
  return players
    .filter((p) => !needle || (p.name || '').toLowerCase().includes(needle))
    .sort((a, b) => sortValue(b) - sortValue(a));
}

function render() {
  const content = document.getElementById('content');
  const list = visible();
  if (!list.length) {
    content.replaceChildren(el('div', { class: 'card empty' }, 'Brak zawodników.'));
    return;
  }
  content.replaceChildren(state.view === 'tiles' ? tiles(list) : table(list));
}

function tiles(list) {
  return el('div', { class: 'grid grid--tiles' }, list.map(tile));
}

function tile(player) {
  const impact = player.impact?.total;
  const photo = avatar(player);

  const bars = el('div', { class: 'ptile__bars' });
  for (const skill of SKILLS) {
    const value = skill.pick(player);
    const bar = el('div', { class: 'pbar' });
    const fill = el('i');
    fill.style.width = Math.max(2, value ?? 0) + '%';
    fill.style.background = percentileColor(value);
    bar.append(fill);
    bars.append(el('div', { class: 'ptile__row', 'data-metric': skill.metric },
      el('span', {}, skill.label), bar, el('span', {}, value === null || value === undefined ? '–' : Math.round(value))));
  }

  return el('a', { class: 'ptile', href: `player.html?p=${encodeURIComponent(player.key)}` },
    el('div', { class: 'ptile__top' }, photo,
      el('div', { class: 'ptile__id' },
        el('div', { class: 'ptile__name' }, player.name),
        el('div', { class: 'ptile__meta' },
          `#${player.shirt || '–'} · ${player.position || '–'} · ${player.gp} ${player.gp === 1 ? 'mecz' : 'meczów'} · ${num((player.min || 0) / Math.max(player.gp, 1), 1)} min`))),
    el('div', { class: 'ptile__impact' },
      el('b', { class: impact >= 0 ? 'delta--up' : 'delta--down' }, signed(impact, 1)),
      el('span', { class: 'muted', style: 'font-size:.74rem' },
        `${metricLabel('impact')} · ${player.percentiles?.total === undefined || player.percentiles?.total === null ? '–' : Math.round(player.percentiles.total) + ' pct'}`),
      el('span', { class: 'q', 'data-metric': 'impact', style: 'margin-left:auto' }, '?')),
    el('div', { class: 'ptile__line' },
      el('span', {}, el('b', {}, num(player.metrics?.per_game?.pts, 1)), ' PKT'),
      el('span', {}, el('b', {}, num(player.metrics?.per_game?.trb, 1)), ' ZB'),
      el('span', {}, el('b', {}, num(player.metrics?.per_game?.ast, 1)), ' AS'),
      el('span', {}, el('b', {}, num(player.metrics?.ts, 1)), ' TS%')),
    bars);
}

function table(list) {
  const columns = [
    { key: 'name', label: 'Zawodnik', render: (p) => el('a', { href: `player.html?p=${encodeURIComponent(p.key)}`, style: 'color:var(--brand)' }, p.name) },
    { key: 'pos', label: 'Poz', sortValue: (p) => p.position || '', render: (p) => p.position || '–' },
    { key: 'gp', label: 'M', render: (p) => p.gp },
    { key: 'min', label: 'MIN', sortValue: (p) => p.min, render: (p) => num(p.min / Math.max(p.gp, 1), 1) },
    { key: 'pts', label: 'PKT', sortValue: (p) => p.metrics?.per_game?.pts, render: (p) => num(p.metrics?.per_game?.pts, 1) },
    { key: 'trb', label: 'ZB', sortValue: (p) => p.metrics?.per_game?.trb, render: (p) => num(p.metrics?.per_game?.trb, 1) },
    { key: 'ast', label: 'AS', sortValue: (p) => p.metrics?.per_game?.ast, render: (p) => num(p.metrics?.per_game?.ast, 1) },
    { key: 'ts', label: 'TS%', metric: 'ts', sortValue: (p) => p.metrics?.ts, render: (p) => num(p.metrics?.ts, 1) },
    { key: 'usage', label: 'USG%', metric: 'usage', sortValue: (p) => p.metrics?.usage, render: (p) => num(p.metrics?.usage, 1) },
    { key: 'ast_rate', label: 'AST%', metric: 'ast_rate', sortValue: (p) => p.metrics?.ast_rate, render: (p) => num(p.metrics?.ast_rate, 1) },
    { key: 'tov_rate', label: 'TOV%', metric: 'tov_rate', sortValue: (p) => p.metrics?.tov_rate, render: (p) => num(p.metrics?.tov_rate, 1) },
    { key: 'on_net', label: 'NET (on)', metric: 'on_net', sortValue: (p) => p.on_off?.on_net, render: (p) => signed(p.on_off?.on_net, 1) },
    { key: 'diff', label: 'ON/OFF', metric: 'diff', sortValue: (p) => p.on_off?.diff, render: (p) => signed(p.on_off?.diff, 1) },
    { key: 'impact', label: 'IMPACT', metric: 'impact', sortValue: (p) => p.impact?.total, render: (p) => signed(p.impact?.total, 1) },
  ];
  return el('div', { class: 'card' }, dataTable(columns, list, { sort: 'impact', desc: true }));
}
