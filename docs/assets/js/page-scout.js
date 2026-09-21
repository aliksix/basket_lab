/* Scouting rywala: profil gry, mocne i slabe strony, kluczowi zawodnicy, piatki.
   Domyslnie otwiera najblizszego przeciwnika z terminarza. */

import {
  avatar, dataTable, dateLabel, el, fail, initTooltips, load, mountChrome,
  num, ordinal, percentileRow, qs, restoreTheme, signed, statTile,
} from './core.js';
import { ZONES14, byDate, rankMap, teamSplit, zoneProfile } from './metrics.js';
import { shotDiet } from './charts.js';
import { shotChart, shotLegend } from './court.js';

restoreTheme();

/**
 * Cechy, po ktorych oceniamy styl rywala. `higher` mowi, czy wyzej znaczy
 * lepiej dla tej druzyny - to od tego zalezy, czy dana pozycja w tabeli
 * trafi do mocnych, czy do slabych stron.
 */
const TRAITS = [
  { key: 'ortg', label: 'Skuteczność ataku', get: (s) => s.ortg, higher: true,
    strong: 'bardzo skuteczny atak', weak: 'nieskuteczny atak' },
  { key: 'drtg', label: 'Szczelność obrony', get: (s) => s.drtg, higher: false,
    strong: 'szczelna obrona', weak: 'dziurawa obrona' },
  { key: 'efg', label: 'eFG% w ataku', get: (s) => s.efg, higher: true,
    strong: 'wysoka skuteczność rzutów', weak: 'niska skuteczność rzutów' },
  { key: 'opp_efg', label: 'eFG% rywali', get: (s) => s.opp_efg, higher: false,
    strong: 'zmusza rywali do słabych rzutów', weak: 'pozwala rywalom trafiać' },
  { key: 'tov_rate', label: 'Straty własne', get: (s) => s.tov_rate, higher: false,
    strong: 'pewne prowadzenie piłki', weak: 'dużo strat' },
  { key: 'opp_tov_rate', label: 'Wymuszone straty', get: (s) => s.opp_tov_rate, higher: true,
    strong: 'agresywna obrona wymuszająca straty', weak: 'nie wymusza strat' },
  { key: 'orb_rate', label: 'Zbiórki w ataku', get: (s) => s.orb_rate, higher: true,
    strong: 'groźny na deskach w ataku', weak: 'nie walczy o zbiórki w ataku' },
  { key: 'drb_rate', label: 'Zbiórki w obronie', get: (s) => s.drb_rate, higher: true,
    strong: 'kończy akcje obronne zbiórką', weak: 'oddaje zbiórki w obronie' },
  { key: 'ft_rate', label: 'Wymuszone faule', get: (s) => s.ft_rate, higher: true,
    strong: 'często atakuje kosz i wymusza faule', weak: 'rzadko chodzi na linię' },
  { key: 'morey', label: 'Dobór rzutów', get: (s) => s.morey, higher: true,
    strong: 'dobiera rzuty o wysokiej opłacalności', weak: 'dużo rzutów ze średniego dystansu' },
  { key: 'pace', label: 'Tempo', get: (s) => s.pace, higher: true, neutral: true,
    strong: 'gra szybko', weak: 'gra wolno' },
  { key: 'tpar', label: 'Udział trójek', get: (s) => s.tpar, higher: true, neutral: true,
    strong: 'opiera grę na rzutach za 3', weak: 'rzadko rzuca za 3' },
];

const state = { team: '' };
let meta;
let league;
let leagueGames;
let leaguePlayers;
let leagueLineups;
let schedule;
let teamRows;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('scout');
  [league, leagueGames, leaguePlayers, leagueLineups, schedule] = await Promise.all([
    load('league'), load('league_games'), load('league_players'),
    load('league_lineups'), load('schedule'),
  ]);

  teamRows = new Map();
  for (const row of byDate(leagueGames)) {
    if (!teamRows.has(row.team)) teamRows.set(row.team, []);
    teamRows.get(row.team).push(row);
  }

  state.team = qs('t') || schedule.next?.opponent_key
    || meta.teams.find((t) => t.key !== meta.club.key)?.key || '';
  renderFilters();
  render();
}

function teamInfo(key) {
  return league.teams.find((t) => t.key === key) || {};
}

function renderFilters() {
  const bar = document.getElementById('filters');
  const select = el('select', {
    onchange: (e) => { state.team = e.target.value; render(); },
  }, meta.teams.filter((t) => t.key !== meta.club.key)
    .map((t) => el('option', { value: t.key }, t.name)));
  select.value = state.team;

  const next = schedule.next;
  bar.replaceChildren(select,
    next ? el('button', {
      class: 'chip chip--brand',
      style: 'cursor:pointer;border:0;font-family:inherit',
      onclick: () => { state.team = next.opponent_key; renderFilters(); render(); },
    }, `Najbliższy rywal: ${next.opponent}`) : null,
    el('div', { class: 'filters__note' },
      'Profil liczony z wszystkich meczów rywala w bazie'));
}

/* --- mocne i slabe strony --------------------------------------------------- */
/** Miejsce rywala w lidze dla kazdej cechy, z podzialem na atuty i slabosci. */
function traitRanks(splits) {
  const total = Object.keys(splits).length;
  return TRAITS.map((trait) => {
    const values = Object.fromEntries(
      Object.entries(splits).map(([key, split]) => [key, trait.get(split)]),
    );
    const place = rankMap(values, trait.higher)[state.team];
    return { ...trait, place, total, value: values[state.team] };
  }).filter((t) => t.place);
}

function render() {
  const content = document.getElementById('content');
  const rows = teamRows.get(state.team) || [];
  const info = teamInfo(state.team);

  if (!rows.length) {
    document.getElementById('head').replaceChildren(
      el('h1', {}, info.name || state.team),
      el('p', {}, 'Ta drużyna nie ma jeszcze meczów w bazie.'));
    content.replaceChildren(el('div', { class: 'card empty' }, 'Brak danych.'));
    return;
  }

  const split = teamSplit(rows);
  const splits = {};
  for (const [key, list] of teamRows) if (list.length) splits[key] = teamSplit(list);
  const traits = traitRanks(splits);
  const total = Object.keys(splits).length;

  renderHead(info, split, rows);

  content.replaceChildren(
    ratingsSection(info, split, splits, total),
    traitsSection(traits),
    shootingSection(rows, split),
    playersSection(),
    lineupsSection(),
  );
}

function renderHead(info, split, rows) {
  const next = schedule.next;
  const isNext = next && next.opponent_key === state.team;
  document.getElementById('head').replaceChildren(
    el('div', { class: 'eyebrow' }, isNext ? 'Najbliższy rywal' : 'Scouting'),
    el('div', { style: 'display:flex;gap:14px;align-items:center;flex-wrap:wrap' },
      info.logo ? el('img', { src: info.logo, alt: '', style: 'width:46px;height:46px;object-fit:contain' }) : null,
      el('div', {},
        el('h1', {}, info.name || state.team),
        el('p', {}, `${split.w}-${split.l} · ${rows.length} ${rows.length === 1 ? 'mecz' : 'meczów'} w bazie`
          + (isNext
            ? ` · gramy ${next.home ? 'u siebie' : 'na wyjeździe'}`
              + `${next.date ? ' ' + dateLabel(next.date) : ''}`
              + `${next.round ? ', kolejka ' + next.round : ''}`
            : '')))));
}

function section(title, sub, ...nodes) {
  return el('div', { class: 'section' },
    el('div', { class: 'card__head' }, el('h2', {}, title),
      sub ? el('span', { class: 'card__sub' }, sub) : null),
    ...nodes);
}

function ratingsSection(info, split, splits, total) {
  const place = (getter, higher) => rankMap(
    Object.fromEntries(Object.entries(splits).map(([k, s]) => [k, getter(s)])), higher,
  )[state.team];

  return section('Profil zespołu', 'miejsca liczone wśród drużyn z meczami w bazie',
    el('div', { class: 'grid grid--4' },
      statTile({ metric: 'ortg', value: num(split.ortg, 1), rank: place((s) => s.ortg, true), total }),
      statTile({ metric: 'drtg', value: num(split.drtg, 1), rank: place((s) => s.drtg, false), total }),
      statTile({ metric: 'net', value: signed(split.net, 1), rank: place((s) => s.net, true), total }),
      statTile({ metric: 'pace', value: num(split.pace, 1), rank: place((s) => s.pace, true), total })),
    el('div', { style: 'height:14px' }),
    el('div', { class: 'grid grid--2' },
      factorsCard('W ataku', [
        ['efg', split.efg, true], ['tov_rate', split.tov_rate, false],
        ['orb_rate', split.orb_rate, true], ['ft_rate', split.ft_rate, true],
      ], splits, total),
      factorsCard('W obronie', [
        ['efg', split.opp_efg, false], ['tov_rate', split.opp_tov_rate, true],
        ['drb_rate', split.drb_rate, true], ['ft_rate', split.opp_ft_rate, false],
      ], splits, total, true)));
}

function factorsCard(title, items, splits, total, defence = false) {
  const card = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, title),
      el('span', { class: 'card__sub' }, 'wartość i miejsce w lidze')));
  const getters = {
    efg: defence ? (s) => s.opp_efg : (s) => s.efg,
    tov_rate: defence ? (s) => s.opp_tov_rate : (s) => s.tov_rate,
    orb_rate: (s) => s.orb_rate,
    drb_rate: (s) => s.drb_rate,
    ft_rate: defence ? (s) => s.opp_ft_rate : (s) => s.ft_rate,
  };
  for (const [metric, value, higher] of items) {
    const values = Object.fromEntries(
      Object.entries(splits).map(([k, s]) => [k, getters[metric](s)]));
    const place = rankMap(values, higher)[state.team];
    const row = percentileRow({
      metric, value,
      percentile: place ? 100 * (1 - (place - 1) / Math.max(total - 1, 1)) : null,
    });
    row.append(el('div', { class: 'prow__val muted', style: 'grid-column:1/-1;margin-top:-4px' },
      place ? `${ordinal(place)} w lidze` : ''));
    card.append(row);
  }
  return card;
}

function traitsSection(traits) {
  const ranked = traits.filter((t) => !t.neutral);
  const strengths = [...ranked].sort((a, b) => a.place - b.place).slice(0, 3);
  const weaknesses = [...ranked].sort((a, b) => b.place - a.place).slice(0, 3);
  const style = traits.filter((t) => t.neutral);

  const list = (items, kind) => el('div', { class: 'card' },
    el('div', { class: 'card__head' },
      el('h2', {}, kind === 'strong' ? 'Na co uważać' : 'Gdzie szukać przewagi'),
      el('span', { class: 'card__sub' }, kind === 'strong' ? 'atuty rywala' : 'słabe punkty')),
    items.map((trait) => el('div', { class: 'prow', style: 'grid-template-columns:1fr 92px' },
      el('div', { class: 'prow__name' },
        el('b', { style: `color:var(--${kind === 'strong' ? 'bad' : 'good'})` },
          kind === 'strong' ? trait.strong : trait.weak)),
      el('div', { class: 'prow__val muted' },
        `${trait.label}: ${num(trait.value, 1)} · ${ordinal(trait.place)}`))));

  return section('Analiza gry', 'wyliczona z miejsc rywala w tabelach ligowych',
    el('div', { class: 'grid grid--2' }, list(strengths, 'strong'), list(weaknesses, 'weak')),
    el('div', { style: 'height:14px' }),
    el('div', { class: 'card' },
      el('div', { class: 'card__head' }, el('h2', {}, 'Styl gry'),
        el('span', { class: 'card__sub' }, 'cechy neutralne - opisują, jak grają, nie jak dobrze')),
      style.map((trait) => el('div', { class: 'prow', style: 'grid-template-columns:1fr 130px' },
        el('div', { class: 'prow__name' }, trait.label),
        el('div', { class: 'prow__val' },
          `${num(trait.value, 1)} · ${ordinal(trait.place)} w lidze`)))));
}

function shootingSection(rows, split) {
  const detailed = {};
  for (const row of rows) {
    for (const [zone, values] of Object.entries(row.zones14 || {})) {
      const bucket = detailed[zone] || (detailed[zone] = { fga: 0, fgm: 0, pts: 0 });
      for (const [k, v] of Object.entries(values)) bucket[k] += v;
    }
  }
  return section('Skąd rzucają', 'kolor = PPS na tle ligi',
    el('div', { class: 'grid grid--2' },
      el('div', { class: 'card' },
        shotChart([], zoneProfile(detailed, ZONES14), league.league.zones14, { mode: 'zones' }),
        shotLegend('zones')),
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'Rozkład rzutów'),
          el('span', { class: 'card__sub' }, `MOREY ${num(split.morey, 1)}%`)),
        shotDiet(split.zone_profile),
        el('div', { class: 'legend' },
          ...Object.entries(split.zone_profile).map(([zone, v]) =>
            el('span', {}, `${zone.replace(/_/g, ' ')} ${num(v.freq, 0)}%`))))));
}

function playersSection() {
  const squad = leaguePlayers
    .filter((p) => p.team === state.team)
    .sort((a, b) => (b.min || 0) - (a.min || 0));
  if (!squad.length) return el('div');

  // przy malej probce Impact jest mocno sciagniety do zera i myli kolejnosc,
  // wiec kafle ustawiamy po produkcji punktowej - to ona mowi, kto niesie atak
  const top = [...squad]
    .sort((a, b) => (b.metrics?.per_game?.pts ?? 0) - (a.metrics?.per_game?.pts ?? 0))
    .slice(0, 4);

  const cards = el('div', { class: 'grid grid--4' }, top.map((player) => el('a', {
    class: 'card', href: `player.html?p=${encodeURIComponent(player.key)}`,
    style: 'display:flex;gap:11px;align-items:center',
  },
    avatar(player),
    el('div', {},
      el('div', { style: 'font-weight:650;font-size:.9rem' }, player.name),
      el('div', { class: 'card__sub' },
        `${num(player.metrics?.per_game?.pts, 1)} pkt · ${num(player.metrics?.ts, 1)} TS%`),
      el('div', { class: 'card__sub' },
        `${num(player.metrics?.usage, 1)} USG% · ${num((player.min || 0) / Math.max(player.gp, 1), 1)} min`)))));

  const columns = [
    { key: 'name', label: 'Zawodnik',
      render: (p) => el('a', { href: `player.html?p=${encodeURIComponent(p.key)}`, style: 'color:var(--brand)' }, p.name) },
    { key: 'pos', label: 'Poz', sortValue: (p) => p.position || '', render: (p) => p.position || '–' },
    { key: 'min', label: 'MIN', sortValue: (p) => p.min, render: (p) => num(p.min / Math.max(p.gp, 1), 1) },
    { key: 'pts', label: 'PKT', sortValue: (p) => p.metrics?.per_game?.pts, render: (p) => num(p.metrics?.per_game?.pts, 1) },
    { key: 'ts', label: 'TS%', metric: 'ts', sortValue: (p) => p.metrics?.ts, render: (p) => num(p.metrics?.ts, 1) },
    { key: 'usage', label: 'USG%', metric: 'usage', sortValue: (p) => p.metrics?.usage, render: (p) => num(p.metrics?.usage, 1) },
    { key: 'ast_rate', label: 'AST%', metric: 'ast_rate', sortValue: (p) => p.metrics?.ast_rate, render: (p) => num(p.metrics?.ast_rate, 1) },
    { key: 'trb_rate', label: 'TRB%', metric: 'trb_rate', sortValue: (p) => p.metrics?.trb_rate, render: (p) => num(p.metrics?.trb_rate, 1) },
    { key: 'impact', label: 'IMPACT', metric: 'impact', sortValue: (p) => p.impact?.total, render: (p) => signed(p.impact?.total, 1) },
  ];

  return section('Kluczowi zawodnicy', 'kafle: najwięcej punktów na mecz · tabela: cała kadra',
    cards,
    el('div', { style: 'height:14px' }),
    el('div', { class: 'card' }, dataTable(columns, squad, { sort: 'min', desc: true })));
}

function lineupsSection() {
  const rows = leagueLineups.filter((l) => l.team === state.team);
  if (!rows.length) {
    return section('Najczęstsze piątki', null,
      el('div', { class: 'card empty' }, 'Brak piątek z wystarczającą liczbą posiadań.'));
  }
  const byKey = new Map(leaguePlayers.map((p) => [p.key, p]));
  const short = (key) => {
    const name = byKey.get(key)?.name || key.split(':').pop().replace(/-/g, ' ');
    const parts = name.split(/\s+/);
    return parts.length > 1 ? `${parts[0][0]}. ${parts.slice(1).join(' ')}` : name;
  };
  const label = (keys) => keys.map(short).join(' · ');
  /** Miniatura z nazwiskiem - samo zdjecie nie mowi, kto gra w tej piatce. */
  const chips = (keys) => el('div', { class: 'lchips' }, keys.map((k) => el('span', { class: 'lchip' },
    avatar(byKey.get(k), 'avatar--tiny'),
    el('span', {}, short(k)))));

  const columns = [
    { key: 'players', label: 'Piątka', sortValue: (r) => label(r.players),
      render: (r) => chips(r.players) },
    { key: 'min', label: 'Min razem', metric: 'min_together' },
    { key: 'poss', label: 'POS', metric: 'poss',
      sortValue: (r) => (r.off_poss || 0) + (r.def_poss || 0),
      render: (r) => num((r.off_poss || 0) + (r.def_poss || 0), 0) },
    { key: 'ortg', label: 'OFF RTG', metric: 'ortg' },
    { key: 'drtg', label: 'DEF RTG', metric: 'drtg' },
    { key: 'net', label: 'NET', metric: 'net',
      render: (r) => el('span', { class: (r.net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(r.net, 1)) },
  ];
  return section('Najczęstsze piątki',
    'czas wspólnej gry oraz ratingi ataku i obrony przy tej piątce na parkiecie',
    el('div', { class: 'card' }, dataTable(columns, rows, { sort: 'poss', desc: true })));
}
