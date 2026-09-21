/* Strona glowna - panel druzyny: ratingi, Four Factors, profil rzutowy, forma. */

import {
  dataTable, dateLabel, el, fail, initTooltips, load, metricLabel, mountChrome,
  num, ordinal, percentileRow, pct, rankClass, restoreTheme, signed, statTile,
} from './core.js';
import {
  FILTERS, TEAM_AXES, ZONES14, axisOf, byDate, mergeZones, percentileOf,
  rankMap, teamSplit, zoneProfile,
} from './metrics.js';
import { divergingBars, formLine, netColor, shotDiet, styleMap } from './charts.js';
import { shotChart, shotLegend, shotModeSwitch } from './court.js';

restoreTheme();

const state = { filter: 'all', game: '', shots: 'zones', axisX: 'tpar', axisY: 'pace' };
let shots;
let meta;
let league;
let leagueGames;
let clubRows;
let teamRows;
let schedule;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('home');
  [league, leagueGames, shots, schedule] = await Promise.all([
    load('league'), load('league_games'), load('shots'), load('schedule'),
  ]);

  teamRows = new Map();
  for (const row of byDate(leagueGames)) {
    if (!teamRows.has(row.team)) teamRows.set(row.team, []);
    teamRows.get(row.team).push(row);
  }
  clubRows = teamRows.get(meta.club.key) || [];

  document.getElementById('eyebrow').textContent =
    `${meta.competition} · sezon ${meta.season}`;
  document.getElementById('title').textContent = meta.club.name;

  renderFilters();
  render();
}

/* --- filtry --------------------------------------------------------------- */
function renderFilters() {
  const bar = document.getElementById('filters');
  const seg = el('div', { class: 'seg' });
  for (const [key, def] of Object.entries(FILTERS)) {
    seg.append(el('button', {
      class: state.filter === key && !state.game ? 'is-on' : '',
      onclick: () => { state.filter = key; state.game = ''; renderFilters(); render(); },
    }, def.label));
  }

  const select = el('select', {
    onchange: (event) => { state.game = event.target.value; renderFilters(); render(); },
  }, el('option', { value: '' }, 'Pojedynczy mecz…'));
  for (const row of [...clubRows].reverse()) {
    select.append(el('option', { value: row.match_id, selected: state.game === row.match_id ? 'selected' : null },
      `${dateLabel(row.date)} ${row.home ? 'vs' : '@'} ${teamName(row.opp)} ${row.pts}:${row.opp_pts}`));
  }

  bar.replaceChildren(seg, select,
    el('div', { class: 'filters__note' }, describeSelection()));
}

function describeSelection() {
  const rows = selectedRows(clubRows);
  if (state.game) return 'jeden mecz · rangi liczone względem wszystkich meczów ligi';
  return `${rows.length} ${plural(rows.length, 'mecz', 'mecze', 'meczów')} · rangi względem tego samego wycinka u rywali`;
}

function plural(n, one, few, many) {
  if (n === 1) return one;
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return few;
  return many;
}

function selectedRows(rows) {
  if (state.game) return rows.filter((r) => r.match_id === state.game);
  return FILTERS[state.filter].apply(rows);
}

function teamName(key) {
  return meta.teams.find((t) => t.key === key)?.short || meta.teams.find((t) => t.key === key)?.name || key;
}

/* --- rankingi ------------------------------------------------------------- */
/** Dla kazdej druzyny liczy ten sam wycinek, zeby ranga byla porownywalna. */
function leagueSplits() {
  const out = {};
  for (const [key, rows] of teamRows) {
    const subset = state.game ? rows : FILTERS[state.filter].apply(rows);
    if (subset.length) out[key] = teamSplit(subset);
  }
  return out;
}

function gameLevelValues(getter) {
  const values = [];
  for (const rows of teamRows.values()) {
    for (const row of rows) values.push(getter(teamSplit([row])));
  }
  return values;
}

/* --- widok ---------------------------------------------------------------- */
function render() {
  const rows = selectedRows(clubRows);
  const content = document.getElementById('content');
  if (!rows.length) {
    content.replaceChildren(el('div', { class: 'card empty' }, 'Brak meczów w tym wycinku.'));
    return;
  }

  const split = teamSplit(rows);
  const splits = leagueSplits();
  const total = Object.keys(splits).length;
  const club = meta.club.key;
  const clubSeason = league.teams.find((t) => t.key === club) || {};

  document.getElementById('subtitle').textContent =
    `${split.w}-${split.l} · ${num(split.pts / split.gp, 1)} pkt na mecz · trener ${meta.club.coach || '—'}`;

  const rank = (getter, higher = true) => {
    if (state.game) return null;
    const values = Object.fromEntries(Object.entries(splits).map(([k, s]) => [k, getter(s)]));
    return rankMap(values, higher)[club];
  };
  const percentile = (getter, higher = true) => {
    if (!state.game) return null;
    return percentileOf(gameLevelValues(getter), getter(split), higher);
  };

  const tile = (metric, getter, { higher = true, digits = 1, suffix = '' } = {}) => statTile({
    metric,
    value: num(getter(split), digits),
    suffix,
    rank: rank(getter, higher),
    total,
    percentile: percentile(getter, higher),
  });

  content.replaceChildren(
    nextOpponentCard(),
    section('Efektywność', el('div', { class: 'grid grid--4' },
      tile('ortg', (s) => s.ortg),
      tile('drtg', (s) => s.drtg, { higher: false }),
      tile('net', (s) => s.net),
      tile('pace', (s) => s.pace))),

    adjustedSection(clubSeason),
    fourFactorsSection(split, splits, rank, percentile, total),
    shootingSection(split, rows),
    formSection(rows),
    gamesSection(rows),
    leagueSection(splits, total),
    styleSection(splits),
  );
}

/** Skrot do skautingu najblizszego rywala. */
function nextOpponentCard() {
  const next = schedule?.next;
  if (!next) return el('div');
  const team = league.teams.find((t) => t.key === next.opponent_key);
  return el('a', {
    class: 'card next-opp',
    href: next.opponent_key ? `scout.html?t=${encodeURIComponent(next.opponent_key)}` : 'scout.html',
  },
    team?.logo ? el('img', { src: team.logo, alt: '' }) : null,
    el('div', {},
      el('div', { class: 'eyebrow' }, 'Najbliższy mecz'),
      el('div', { class: 'next-opp__name' },
        `${next.home ? 'vs' : '@'} ${next.opponent}`),
      el('div', { class: 'card__sub' },
        [next.date ? dateLabel(next.date) : null,
          next.round ? `kolejka ${next.round}` : null,
          next.venue || null].filter(Boolean).join(' · '))),
    el('div', { class: 'next-opp__stats' },
      team ? el('span', {}, 'AdjNET ', el('b', {}, signed(team.adj_net, 1))) : null,
      el('span', { class: 'chip chip--brand' }, 'Zobacz skauting →')));
}

function section(title, ...nodes) {
  return el('div', { class: 'section' }, el('h2', {}, title), ...nodes);
}

/* --- ratingi skorygowane --------------------------------------------------- */
function adjustedSection(clubSeason) {
  const ranks = {
    adj_ortg: rankMap(Object.fromEntries(league.teams.map((t) => [t.key, t.adj_ortg])), true),
    adj_drtg: rankMap(Object.fromEntries(league.teams.map((t) => [t.key, t.adj_drtg])), false),
    adj_net: rankMap(Object.fromEntries(league.teams.map((t) => [t.key, t.adj_net])), true),
    sos: rankMap(Object.fromEntries(league.teams.map((t) => [t.key, t.sos])), true),
  };
  const total = league.teams.length;
  const club = clubSeason.key;
  const tile = (metric, value, digits = 1) => statTile({
    metric, value: metric === 'adj_net' || metric === 'sos' ? signed(value, digits) : num(value, digits),
    rank: ranks[metric][club], total,
  });

  return section('Ratingi skorygowane o siłę rywali',
    el('div', { class: 'card__sub', style: 'margin:-6px 0 12px' },
      'Liczone dla całego sezonu — korekta o przeciwnika wymaga pełnego terminarza, więc nie zmienia się z filtrem.'),
    el('div', { class: 'grid grid--4' },
      tile('adj_ortg', clubSeason.adj_ortg),
      tile('adj_drtg', clubSeason.adj_drtg),
      tile('adj_net', clubSeason.adj_net),
      tile('sos', clubSeason.sos)));
}

/* --- four factors ---------------------------------------------------------- */
const FOUR_FACTORS = [
  { metric: 'efg', off: (s) => s.efg, def: (s) => s.opp_efg, offHigher: true, defHigher: false, weight: '40%' },
  { metric: 'tov_rate', off: (s) => s.tov_rate, def: (s) => s.opp_tov_rate, offHigher: false, defHigher: true, weight: '25%' },
  { metric: 'orb_rate', off: (s) => s.orb_rate, def: (s) => s.drb_rate, offHigher: true, defHigher: true, weight: '20%' },
  { metric: 'ft_rate', off: (s) => s.ft_rate, def: (s) => s.opp_ft_rate, offHigher: true, defHigher: false, weight: '15%' },
];

function fourFactorsSection(split, splits, rank, percentile, total) {
  const build = (side) => {
    const card = el('div', { class: 'card' },
      el('div', { class: 'card__head' },
        el('h2', {}, side === 'off' ? 'Atak' : 'Obrona'),
        el('span', { class: 'card__sub' }, side === 'off' ? 'co robimy z piłką' : 'co wymuszamy na rywalu')));
    for (const factor of FOUR_FACTORS) {
      const getter = side === 'off' ? factor.off : factor.def;
      const higher = side === 'off' ? factor.offHigher : factor.defHigher;
      const place = rank(getter, higher);
      const pctile = percentile(getter, higher);
      const value = getter(split);
      const bar = pctile ?? (place ? 100 * (1 - (place - 1) / Math.max(total - 1, 1)) : null);
      const label = side === 'def' && factor.metric === 'orb_rate' ? 'drb_rate' : factor.metric;
      const row = percentileRow({
        metric: label,
        value,
        percentile: bar,
        format: (v) => num(v, 1),
      });
      row.append(el('div', { class: 'prow__val muted', style: 'grid-column:1/-1;margin-top:-4px' },
        place ? `${ordinal(place)} w lidze · waga ${factor.weight}` : `waga ${factor.weight}`));
      card.append(row);
    }
    return card;
  };
  return section('Four Factors', el('div', { class: 'grid grid--2' }, build('off'), build('def')));
}

/* --- rzuty ----------------------------------------------------------------- */
function shootingSection(split, rows) {
  const detailed = {};
  for (const row of rows) mergeZones(detailed, row.zones14);
  const ids = new Set(rows.map((r) => r.match_id));
  const own = shots.filter((s) => ids.has(s.match_id));
  const zones = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Mapa rzutów'),
      shotModeSwitch(state.shots, (mode) => { state.shots = mode; render(); })),
    shotChart(own, zoneProfile(detailed, ZONES14), league.league.zones14, { mode: state.shots, size: 0.16 }),
    shotLegend(state.shots),
    el('div', { class: 'card__sub', style: 'margin-top:8px;text-align:center' },
      `${own.length} rzutów z gry z zarejestrowaną pozycją`));

  const diet = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Rozkład rzutów'),
      el('span', { class: 'card__sub' }, `${metricLabel('morey')} ${num(split.morey, 1)}%`)),
    shotDiet(split.zone_profile),
    el('div', { class: 'legend' },
      ...Object.entries(split.zone_profile).map(([zone, v]) => el('span', {},
        `${zone.replace(/_/g, ' ')} ${num(v.freq, 0)}%`))),
    el('div', { style: 'margin-top:16px' },
      percentileRow({ metric: 'ts', value: split.ts, percentile: null, format: (v) => num(v, 1) }),
      percentileRow({ metric: 'efg', value: split.efg, percentile: null, format: (v) => num(v, 1) }),
      percentileRow({ metric: 'tpar', value: split.tpar, percentile: null, format: (v) => num(v, 1) })));

  return section('Profil rzutowy', el('div', { class: 'grid grid--2' }, zones, diet));
}

/* --- forma ----------------------------------------------------------------- */
function formSection(rows) {
  const points = rows.map((row) => {
    const s = teamSplit([row]);
    return {
      value: s.net, date: row.date,
      title: `${dateLabel(row.date)} ${row.home ? 'vs' : '@'} ${teamName(row.opp)}`,
      label: () => `${row.pts}:${row.opp_pts} · `,
    };
  });
  return section('Forma mecz po meczu',
    el('div', { class: 'grid grid--2' },
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'NET RTG w meczu'),
          el('span', { class: 'card__sub' }, 'słupek = jeden mecz')),
        divergingBars(points, { format: (v) => signed(v, 1), label: (p) => p.label() })),
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'Średnia krocząca'),
          el('span', { class: 'card__sub' }, 'niebieska linia = ostatnie 5 meczów')),
        formLine(points, { format: (v) => signed(v, 1) }))));
}

/* --- mecze ----------------------------------------------------------------- */
function gamesSection(rows) {
  const enriched = rows.map((row) => ({ ...row, split: teamSplit([row]) })).reverse();
  const columns = [
    { key: 'date', label: 'Mecz', render: (r) => el('span', {},
      `${dateLabel(r.date)} ${r.home ? 'vs' : '@'} ${teamName(r.opp)}`) },
    { key: 'result', label: 'Wynik', sortValue: (r) => r.pts - r.opp_pts,
      render: (r) => el('span', { class: r.pts > r.opp_pts ? 'delta--up' : 'delta--down' },
        `${r.pts}:${r.opp_pts}`) },
    { key: 'poss', label: 'POS', metric: 'poss', render: (r) => num(r.poss, 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg', sortValue: (r) => r.split.ortg, render: (r) => num(r.split.ortg, 1) },
    { key: 'drtg', label: 'DEF', metric: 'drtg', sortValue: (r) => r.split.drtg, render: (r) => num(r.split.drtg, 1) },
    { key: 'net', label: 'NET', metric: 'net', sortValue: (r) => r.split.net,
      render: (r) => el('span', { class: r.split.net >= 0 ? 'delta--up' : 'delta--down' }, signed(r.split.net, 1)) },
    { key: 'efg', label: 'eFG%', metric: 'efg', sortValue: (r) => r.split.efg, render: (r) => num(r.split.efg, 1) },
    { key: 'tov', label: 'TOV%', metric: 'tov_rate', sortValue: (r) => r.split.tov_rate, render: (r) => num(r.split.tov_rate, 1) },
    { key: 'orb', label: 'ORB%', metric: 'orb_rate', sortValue: (r) => r.split.orb_rate, render: (r) => num(r.split.orb_rate, 1) },
    { key: 'ftr', label: 'FTr', metric: 'ft_rate', sortValue: (r) => r.split.ft_rate, render: (r) => num(r.split.ft_rate, 1) },
  ];
  return section('Mecze w wybranym wycinku',
    el('div', { class: 'card' }, dataTable(columns, enriched, { sort: 'date', desc: true })));
}

/* --- tabela ligi ----------------------------------------------------------- */
function leagueSection(splits, total) {
  const rows = league.teams.map((team) => ({ ...team, split: splits[team.key] }))
    .filter((t) => t.split);
  const columns = [
    { key: 'name', label: 'Drużyna', render: (r) => el('span', {}, r.name) },
    { key: 'record', label: 'Bilans', sortValue: (r) => r.split.w - r.split.l,
      render: (r) => `${r.split.w}-${r.split.l}` },
    { key: 'adj_net', label: 'AdjNET', metric: 'adj_net', render: (r) => signed(r.adj_net, 1) },
    { key: 'adj_ortg', label: 'AdjORTG', metric: 'adj_ortg' },
    { key: 'adj_drtg', label: 'AdjDRTG', metric: 'adj_drtg' },
    { key: 'ortg', label: 'OFF', metric: 'ortg', sortValue: (r) => r.split.ortg, render: (r) => num(r.split.ortg, 1) },
    { key: 'drtg', label: 'DEF', metric: 'drtg', sortValue: (r) => r.split.drtg, render: (r) => num(r.split.drtg, 1) },
    { key: 'pace', label: 'TEMPO', metric: 'pace', sortValue: (r) => r.split.pace, render: (r) => num(r.split.pace, 1) },
    { key: 'efg', label: 'eFG%', metric: 'efg', sortValue: (r) => r.split.efg, render: (r) => num(r.split.efg, 1) },
    { key: 'sos', label: 'SOS', metric: 'sos', render: (r) => signed(r.sos, 1) },
  ];
  return section('Liga',
    el('div', { class: 'card' },
      dataTable(columns, rows, { sort: 'adj_net', desc: true, highlight: (r) => r.key === meta.club.key })));
}

/* --- mapa stylu ------------------------------------------------------------ */
function styleSection(splits) {
  const x = axisOf(state.axisX);
  const y = axisOf(state.axisY);
  const points = Object.entries(splits).map(([key, split]) => {
    const team = league.teams.find((t) => t.key === key) || {};
    return {
      key,
      name: team.name || key,
      short: team.short,
      x: x.get(split),
      y: y.get(split),
      value: split.net,
      color: netColor(split.net),
      tip: `${x.label}: ${num(x.get(split), 1)} · ${y.label}: ${num(y.get(split), 1)}`
        + `<em>bilans ${signed(split.net, 1)} na 100 posiadań</em>`,
    };
  });

  return section('Mapa stylu',
    el('div', { class: 'card' },
      el('div', { class: 'card__head' },
        el('h2', {}, 'Porównanie zespołów'),
        axisPicker((axis, value) => { state[axis] = value; render(); })),
      styleMap(points, { highlight: meta.club.key, xLabel: x.label, yLabel: y.label }),
      el('div', { class: 'legend' },
        el('span', { class: 'muted' }, 'kolor punktu = bilans na 100 posiadań · przerywane linie = średnia ligi'))));
}

/** Dwa selecty wybierajace wskazniki na osie mapy stylu. */
function axisPicker(onChange) {
  const make = (value, axis) => {
    const select = el('select', { onchange: (e) => onChange(axis, e.target.value) },
      TEAM_AXES.map((a) => el('option', { value: a.key }, a.label)));
    select.value = value;
    return select;
  };
  return el('div', { class: 'axis-picker' },
    el('span', {}, 'oś X'), make(state.axisX, 'axisX'),
    el('span', {}, 'oś Y'), make(state.axisY, 'axisY'));
}
