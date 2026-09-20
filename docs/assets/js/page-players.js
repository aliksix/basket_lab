/* Kafle zawodnikow - skrot profilu: wplyw, percentyle umiejetnosci, podstawy. */

import {
  avatar, dataTable, el, fail, initTooltips, load, mountChrome,
  num, percentileColor, restoreTheme, signed,
} from './core.js';
import { playerSkills, pppOnCourt } from './metrics.js';
import { pizza, ratingLine } from './charts.js';

restoreTheme();

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
  return el('a', { class: 'ptile', href: `player.html?p=${encodeURIComponent(player.key)}` },
    el('div', { class: 'ptile__top' },
      avatar(player),
      el('div', { class: 'ptile__id' },
        el('div', { class: 'ptile__name' }, player.name),
        el('div', { class: 'ptile__meta' },
          `#${player.shirt || '–'} · ${player.position || '–'} · `
          + `${num((player.min || 0) / Math.max(player.gp, 1), 1)} min`))),

    el('div', { class: 'ptile__epm', 'data-metric': 'impact' },
      el('small', {}, 'IMPACT'),
      el('div', { class: 'ptile__epm-row' },
        tinted(el('b', {}, signed(player.impact?.total, 1)), player.percentiles?.total),
        el('span', {}, placeLabel(player, 'total')))),

    el('div', { class: 'ptile__lines' },
      ratingLine({
        label: 'OFF', value: player.impact?.off,
        percentile: player.percentiles?.off, rank: player.ranks?.off,
        format: (v) => signed(v, 1),
      }),
      ratingLine({
        label: 'DEF', value: player.impact?.def,
        percentile: player.percentiles?.def, rank: player.ranks?.def,
        format: (v) => signed(v, 1),
      })),

    el('div', { class: 'ptile__line' },
      el('span', {}, el('b', {}, num(player.metrics?.per_game?.pts, 1)), ' PKT'),
      el('span', { 'data-metric': 'ppp_ind' }, el('b', {}, num(player.metrics?.ppp_ind, 2)), ' PPP'),
      el('span', { 'data-metric': 'ppp_on' }, el('b', {}, num(pppOnCourt(player), 2)), ' PPP ON')),

    el('div', { class: 'ptile__skills' }, pizza(playerSkills(player), { size: 210, compact: true })));
}

/** Miejsce w lidze w formacie "#12 z 82". */
function placeLabel(player, key) {
  const place = player.ranks?.[key];
  if (!place) return '–';
  return player.ranked_of ? `#${place} z ${player.ranked_of}` : `#${place}`;
}

function tinted(node, percentile) {
  node.style.color = percentileColor(percentile);
  return node;
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
