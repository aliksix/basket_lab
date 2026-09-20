/* Widok calej ligi - ratingi, Four Factors, rozklad rzutow, mapa stylu. */

import {
  dataTable, el, fail, initTooltips, load, mountChrome, num, restoreTheme, signed,
} from './core.js';
import { FILTERS, byDate, teamSplit } from './metrics.js';
import { netColor, shotDiet, styleMap } from './charts.js';

restoreTheme();

const state = { filter: 'all', tab: 'ratings' };
let meta;
let league;
let teamRows;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('league');
  const [leagueData, games] = await Promise.all([load('league'), load('league_games')]);
  league = leagueData;
  teamRows = new Map();
  for (const row of byDate(games)) {
    if (!teamRows.has(row.team)) teamRows.set(row.team, []);
    teamRows.get(row.team).push(row);
  }
  renderFilters();
  render();
}

function renderFilters() {
  const bar = document.getElementById('filters');
  const seg = el('div', { class: 'seg' });
  for (const [key, def] of Object.entries(FILTERS)) {
    seg.append(el('button', {
      class: state.filter === key ? 'is-on' : '',
      onclick: () => { state.filter = key; renderFilters(); render(); },
    }, def.label));
  }
  const tabs = el('div', { class: 'seg' },
    ...[['ratings', 'Ratingi'], ['factors', 'Four Factors'], ['shots', 'Rzuty']].map(([key, label]) =>
      el('button', { class: state.tab === key ? 'is-on' : '', onclick: () => { state.tab = key; renderFilters(); render(); } }, label)));
  bar.replaceChildren(seg, tabs,
    el('div', { class: 'filters__note' }, 'AdjORTG/AdjDRTG zawsze dotyczą całego sezonu.'));
}

function splits() {
  const out = [];
  for (const team of league.teams) {
    const rows = FILTERS[state.filter].apply(teamRows.get(team.key) || []);
    if (rows.length) out.push({ ...team, split: teamSplit(rows) });
  }
  return out;
}

function render() {
  const rows = splits();
  const content = document.getElementById('content');
  const tables = {
    ratings: ratingsTable(rows),
    factors: factorsTable(rows),
    shots: shotsTable(rows),
  };
  content.replaceChildren(
    el('div', { class: 'card' }, tables[state.tab]),
    el('div', { class: 'section' },
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'Mapa stylu'),
          el('span', { class: 'card__sub' }, 'kolor punktu = bilans na 100 posiadań · przerywane linie = średnia ligi')),
        styleMap(rows.map((r) => ({
          key: r.key, name: r.name, short: r.short,
          x: r.split.tpar, y: r.split.pace,
          value: r.split.net, color: netColor(r.split.net),
          tip: `${num(r.split.pace, 1)} posiadań na 40 min · ${num(r.split.tpar, 1)}% rzutów za 3`
            + `<em>bilans ${signed(r.split.net, 1)} na 100 posiadań</em>`,
        })), { highlight: meta.club.key }))),
  );
}

const nameCol = { key: 'name', label: 'Drużyna', render: (r) => el('span', {}, r.name) };
const highlight = (r) => r.key === meta.club.key;

function ratingsTable(rows) {
  return dataTable([
    nameCol,
    { key: 'record', label: 'Bilans', sortValue: (r) => r.split.w - r.split.l, render: (r) => `${r.split.w}-${r.split.l}` },
    { key: 'adj_net', label: 'AdjNET', metric: 'adj_net', render: (r) => signed(r.adj_net, 1) },
    { key: 'adj_ortg', label: 'AdjORTG', metric: 'adj_ortg' },
    { key: 'adj_drtg', label: 'AdjDRTG', metric: 'adj_drtg' },
    { key: 'sos', label: 'SOS', metric: 'sos', render: (r) => signed(r.sos, 1) },
    { key: 'ortg', label: 'OFF', metric: 'ortg', sortValue: (r) => r.split.ortg, render: (r) => num(r.split.ortg, 1) },
    { key: 'drtg', label: 'DEF', metric: 'drtg', sortValue: (r) => r.split.drtg, render: (r) => num(r.split.drtg, 1) },
    { key: 'net', label: 'NET', metric: 'net', sortValue: (r) => r.split.net, render: (r) => signed(r.split.net, 1) },
    { key: 'pace', label: 'TEMPO', metric: 'pace', sortValue: (r) => r.split.pace, render: (r) => num(r.split.pace, 1) },
    { key: 'kill', label: 'KILL', metric: 'kill_shots', sortValue: (r) => r.split.kill_shots, render: (r) => num(r.split.kill_shots, 2) },
  ], rows, { sort: 'adj_net', desc: true, highlight });
}

function factorsTable(rows) {
  return dataTable([
    nameCol,
    { key: 'efg', label: 'eFG%', metric: 'efg', sortValue: (r) => r.split.efg, render: (r) => num(r.split.efg, 1) },
    { key: 'tov', label: 'TOV%', metric: 'tov_rate', sortValue: (r) => r.split.tov_rate, render: (r) => num(r.split.tov_rate, 1) },
    { key: 'orb', label: 'ORB%', metric: 'orb_rate', sortValue: (r) => r.split.orb_rate, render: (r) => num(r.split.orb_rate, 1) },
    { key: 'ftr', label: 'FTr', metric: 'ft_rate', sortValue: (r) => r.split.ft_rate, render: (r) => num(r.split.ft_rate, 1) },
    { key: 'oefg', label: 'opp eFG%', metric: 'efg', sortValue: (r) => r.split.opp_efg, render: (r) => num(r.split.opp_efg, 1) },
    { key: 'otov', label: 'opp TOV%', metric: 'tov_rate', sortValue: (r) => r.split.opp_tov_rate, render: (r) => num(r.split.opp_tov_rate, 1) },
    { key: 'drb', label: 'DRB%', metric: 'drb_rate', sortValue: (r) => r.split.drb_rate, render: (r) => num(r.split.drb_rate, 1) },
    { key: 'oftr', label: 'opp FTr', metric: 'ft_rate', sortValue: (r) => r.split.opp_ft_rate, render: (r) => num(r.split.opp_ft_rate, 1) },
  ], rows, { sort: 'efg', desc: true, highlight });
}

function shotsTable(rows) {
  return dataTable([
    nameCol,
    { key: 'diet', label: 'Rozkład rzutów', sortValue: (r) => r.split.morey,
      render: (r) => el('div', { style: 'min-width:190px' }, shotDiet(r.split.zone_profile)) },
    { key: 'morey', label: 'MOREY', metric: 'morey', sortValue: (r) => r.split.morey, render: (r) => num(r.split.morey, 1) },
    { key: 'rim', label: 'RIM%', sortValue: (r) => r.split.zone_profile.RIM.freq, render: (r) => num(r.split.zone_profile.RIM.freq, 1) },
    { key: 'rimpps', label: 'RIM PPS', metric: 'pps', sortValue: (r) => r.split.zone_profile.RIM.pps, render: (r) => num(r.split.zone_profile.RIM.pps, 2) },
    { key: 'tpar', label: '3PAr', metric: 'tpar', sortValue: (r) => r.split.tpar, render: (r) => num(r.split.tpar, 1) },
    { key: 'c3', label: 'ROGI%', sortValue: (r) => r.split.zone_profile.CORNER_3.freq, render: (r) => num(r.split.zone_profile.CORNER_3.freq, 1) },
    { key: 'mid', label: 'MID%', sortValue: (r) => r.split.zone_profile.LONG_MID.freq, render: (r) => num(r.split.zone_profile.LONG_MID.freq, 1) },
    { key: 'ts', label: 'TS%', metric: 'ts', sortValue: (r) => r.split.ts, render: (r) => num(r.split.ts, 1) },
  ], rows, { sort: 'morey', desc: true, highlight });
}
