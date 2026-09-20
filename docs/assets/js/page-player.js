/* Profil zawodnika: wplyw i jego rozbicie, percentyle, mapa rzutow, mecz po meczu. */

import {
  avatar, crumbs, dataTable, dateLabel, el, fail, initTooltips, load, metricLabel,
  mountChrome, num, percentileRow, qs, restoreTheme, signed, statTile, zoneName,
} from './core.js';
import {
  FILTERS, ZONES14, addStats, clutchRatings, efg, emptyStats, expectedPps, fgaLongRate,
  playerSkills, pppLong, pppOnCourt, sumBuckets, ts, zoneProfile, zonesFromShots,
} from './metrics.js';
import { divergingBars, formLine, pizza, ratingLine, shotDiet } from './charts.js';
import { shotChart, shotLegend, shotModeSwitch } from './court.js';

restoreTheme();

const IMPACT_GROUPS = {
  shooting: 'Rzuty', creation: 'Kreowanie', turnovers: 'Strata piłki',
  rebounding: 'Zbiórki', disruption: 'Przechwyty', rim_protection: 'Obrona obręczy', fouls: 'Faule',
};

const PERCENTILE_ROWS = [
  ['ts', 'TS%', (m) => m.ts], ['rts', 'rTS%', (m) => m.rts], ['efg', 'eFG%', (m) => m.efg],
  ['three_pct', '3P%', (m) => m.three_pct], ['ft_pct', 'FT%', (m) => m.ft_pct],
  ['usage', 'USG%', (m) => m.usage], ['ast_rate', 'AST%', (m) => m.ast_rate],
  ['tov_rate', 'TOV%', (m) => m.tov_rate], ['orb_rate', 'ORB%', (m) => m.orb_rate],
  ['drb_rate', 'DRB%', (m) => m.drb_rate], ['stl_rate', 'STL%', (m) => m.stl_rate],
  ['blk_rate', 'BLK%', (m) => m.blk_rate], ['ftr', 'FTr', (m) => m.ftr], ['tpar', '3PAr', (m) => m.tpar],
];

const state = { filter: 'all', scope: 'league', shots: 'both', clutch: false };
let games;
let meta;
let league;
let player;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('players');
  league = await load('league');
  const key = qs('p');
  if (!key) throw new Error('Nie podano zawodnika.');
  player = await load('player/' + key.replace(':', '__'));
  games = await load('club');
  renderHead();
  renderFilters();
  render();
}

function teamName(key) {
  const team = meta.teams.find((t) => t.key === key);
  return team?.short || team?.name || key;
}

function renderHead() {
  const head = document.getElementById('head');
  head.replaceChildren(
    crumbs(['Zawodnicy', 'players.html'], player.name),
    el('div', { style: 'display:flex;gap:18px;align-items:center;flex-wrap:wrap' },
      avatar(player, 'avatar--lg'),
      el('div', {},
        el('h1', {}, player.name),
        el('p', {}, `#${player.shirt || '–'} · ${player.position || '–'} · `
          + `${player.gp} ${player.gp === 1 ? 'mecz' : 'meczów'} (${player.gs} w pierwszej piątce) · `
          + `${num((player.min || 0) / Math.max(player.gp, 1), 1)} min na mecz`))));
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
  const scope = el('div', { class: 'seg' },
    el('button', { class: state.scope === 'league' ? 'is-on' : '', onclick: () => { state.scope = 'league'; renderFilters(); render(); } }, 'Percentyl: liga'),
    el('button', { class: state.scope === 'pos' ? 'is-on' : '', onclick: () => { state.scope = 'pos'; renderFilters(); render(); } }, 'Percentyl: pozycja'));
  const clutch = el('div', { class: 'seg' },
    el('button', { class: !state.clutch ? 'is-on' : '', onclick: () => { state.clutch = false; renderFilters(); render(); } }, 'Cały mecz'),
    el('button', { class: state.clutch ? 'is-on' : '', onclick: () => { state.clutch = true; renderFilters(); render(); } }, 'Clutch'));
  const note = el('div', { class: 'filters__note' },
    state.clutch
      ? 'Końcówki: ostatnie 5 minut IV kwarty i dogrywki przy różnicy do 5 punktów'
      : 'Percentyle dotyczą całego sezonu; filtry zmieniają wartości surowe.');
  bar.replaceChildren(...[seg, clutch, state.clutch ? null : scope, note].filter(Boolean));
}

/* --- wycinki --------------------------------------------------------------- */
function selectedGames() {
  const rows = [...player.games].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  const mapped = rows.map((r) => ({ ...r, pts: r.stats.pts, opp_pts: 0, home: r.home }));
  if (state.filter === 'wins') return rows.filter((r) => r.win);
  if (state.filter === 'losses') return rows.filter((r) => !r.win);
  if (state.filter === 'home') return rows.filter((r) => r.home);
  if (state.filter === 'away') return rows.filter((r) => !r.home);
  if (state.filter === 'last5') return rows.slice(-5);
  return mapped.length ? rows : rows;
}

function totalsOf(rows) {
  const totals = emptyStats();
  const on = { off_poss: 0, def_poss: 0, pts: 0, opp_pts: 0 };
  const off = { off_poss: 0, def_poss: 0, pts: 0, opp_pts: 0 };
  for (const row of rows) {
    addStats(totals, row.stats);
    for (const key of Object.keys(on)) on[key] += row.on?.[key] || 0;
    for (const key of Object.keys(off)) off[key] += row.off?.[key] || 0;
  }
  return { totals, on, off, gp: rows.length };
}

function shotsOf(rows) {
  const ids = new Set(rows.map((r) => r.match_id));
  return (player.shots || []).filter((s) => ids.has(s.match_id));
}

/* --- widok ----------------------------------------------------------------- */
function render() {
  const content = document.getElementById('content');
  const rows = selectedGames();
  if (!rows.length) {
    content.replaceChildren(el('div', { class: 'card empty' }, 'Brak meczów w tym wycinku.'));
    return;
  }
  if (state.clutch) {
    renderClutch(content, rows);
    return;
  }
  const { totals, on, off, gp } = totalsOf(rows);
  content.replaceChildren(
    impactSection(),
    productionSection(totals, gp),
    longSection(rows),
    percentilesSection(),
    onOffSection(on, off),
    shootingSection(rows, totals),
    gamelogSection(rows),
  );
}

/* --- koncowki meczow -------------------------------------------------------- */
function renderClutch(content, rows) {
  const played = rows.filter((r) => (r.clutch?.off_poss || 0) + (r.clutch?.def_poss || 0) > 0);
  const bucket = sumBuckets(rows, 'clutch');
  const ratings = clutchRatings(bucket);

  if (!played.length) {
    content.replaceChildren(el('div', { class: 'note' },
      el('div', {}, el('b', {}, 'Brak minut w końcówkach'),
        'W wybranych meczach nie było ani jednego posiadania w clutch time — żaden z nich nie był '
        + 'rozstrzygany w ostatnich pięciu minutach przy różnicy do pięciu punktów.')));
    return;
  }

  const box = {
    pts: bucket.pts, fga: bucket.fga, fgm: bucket.fgm,
    tpa: bucket.tpa, tpm: bucket.tpm, fta: bucket.fta, ftm: bucket.ftm,
    trb: bucket.trb, ast: bucket.ast, tov: bucket.tov, stl: bucket.stl, blk: bucket.blk,
  };
  const share = (made, att) => (att ? num((100 * made) / att, 1) + '%' : '–');

  content.replaceChildren(
    el('div', { class: 'note' },
      el('div', {}, el('b', {}, 'Clutch time'),
        'Ostatnie 5 minut IV kwarty i cała dogrywka, gdy różnica punktowa nie przekracza pięciu. '
        + `Zawodnik rozegrał tu ${num(ratings.min, 1)} min w ${played.length} `
        + `${played.length === 1 ? 'meczu' : 'meczach'}.`)),

    section('Zespół przy nim na parkiecie', 'wynik drużyny w końcówkach, gdy zawodnik grał',
      el('div', { class: 'grid grid--4' },
        statTile({ metric: 'clutch_ortg', value: num(ratings.ortg, 1), hint: `${num(ratings.off_poss, 0)} pos` }),
        statTile({ metric: 'clutch_drtg', value: num(ratings.drtg, 1), hint: `${num(ratings.def_poss, 0)} pos` }),
        statTile({ metric: 'net', value: signed(ratings.net, 1) }),
        statTile({ metric: 'clutch', label: 'MINUTY', value: num(ratings.min, 1) }))),

    section('Jego statystyki w końcówkach', 'suma z wybranych meczów',
      el('div', { class: 'grid grid--4' },
        statTile({ metric: 'pts', label: 'PUNKTY', value: num(box.pts, 0) }),
        statTile({ metric: 'ts', value: num(ts(box), 1), suffix: '%' }),
        statTile({ metric: 'trb', label: 'ZBIÓRKI', value: num(box.trb, 0) }),
        statTile({ metric: 'ast', label: 'ASYSTY', value: num(box.ast, 0) })),
      el('div', { style: 'height:14px' }),
      el('div', { class: 'card' },
        el('div', { class: 'grid grid--2' },
          column([
            ['Rzuty z gry', `${num(box.fgm, 0)}/${num(box.fga, 0)}`, share(box.fgm, box.fga)],
            ['Za 3 punkty', `${num(box.tpm, 0)}/${num(box.tpa, 0)}`, share(box.tpm, box.tpa)],
            ['Rzuty wolne', `${num(box.ftm, 0)}/${num(box.fta, 0)}`, share(box.ftm, box.fta)],
          ]),
          column([
            ['Straty', num(box.tov, 0), ''],
            ['Przechwyty', num(box.stl, 0), ''],
            ['Bloki', num(box.blk, 0), ''],
          ])))),

    clutchGamelog(played),
  );
}

function clutchGamelog(rows) {
  const columns = [
    { key: 'date', label: 'Mecz', sortValue: (r) => r.date,
      render: (r) => `${dateLabel(r.date)} ${r.home ? 'vs' : '@'} ${teamName(r.opp)}` },
    { key: 'min', label: 'MIN', sortValue: (r) => r.clutch.secs, render: (r) => num((r.clutch.secs || 0) / 60, 1) },
    { key: 'poss', label: 'POS', sortValue: (r) => r.clutch.off_poss, render: (r) => num(r.clutch.off_poss, 0) },
    { key: 'pts', label: 'PKT', sortValue: (r) => r.clutch.pts, render: (r) => num(r.clutch.pts, 0) },
    { key: 'fg', label: 'FG', sortValue: (r) => r.clutch.fgm, render: (r) => `${num(r.clutch.fgm, 0)}/${num(r.clutch.fga, 0)}` },
    { key: 'trb', label: 'ZB', sortValue: (r) => r.clutch.trb, render: (r) => num(r.clutch.trb, 0) },
    { key: 'ast', label: 'AS', sortValue: (r) => r.clutch.ast, render: (r) => num(r.clutch.ast, 0) },
    { key: 'tov', label: 'STR', sortValue: (r) => r.clutch.tov, render: (r) => num(r.clutch.tov, 0) },
    { key: 'net', label: 'NET', sortValue: (r) => clutchRatings(r.clutch).net,
      render: (r) => {
        const net = clutchRatings(r.clutch).net;
        return el('span', { class: (net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(net, 1));
      } },
  ];
  return section('Końcówka po końcówce', null,
    el('div', { class: 'card' }, dataTable(columns, rows, { sort: 'date', desc: true })));
}

/* --- dlugie akcje ----------------------------------------------------------- */
function longSection(rows) {
  const bucket = sumBuckets(rows, 'long15');
  return section('Gra w ustawionej obronie',
    'akcje trwające co najmniej 15 sekund, bez dogrywania po własnej zbiórce w ataku',
    el('div', { class: 'grid grid--4' },
      statTile({
        metric: 'fga_long_rate',
        value: num(fgaLongRate(bucket), 1),
        suffix: '%',
        hint: `${num(bucket.fga_long, 0)} z ${num(bucket.fga, 0)} jego rzutów`,
      }),
      statTile({
        metric: 'ppp_long',
        value: num(pppLong(bucket), 2),
        hint: `${num(bucket.off_poss_long, 0)} długich akcji przy nim`,
      }),
      statTile({
        metric: 'long_share',
        value: num((100 * (bucket.off_poss_long || 0)) / (bucket.off_poss || 1), 1),
        suffix: '%',
        hint: 'gdy był na parkiecie',
      })));
}

function section(title, sub, ...nodes) {
  return el('div', { class: 'section' },
    el('div', { class: 'card__head' }, el('h2', {}, title), sub ? el('span', { class: 'card__sub' }, sub) : null),
    ...nodes);
}

/* --- wplyw ----------------------------------------------------------------- */
function impactSection() {
  const impact = player.impact || {};
  const pc = state.scope === 'pos' ? player.percentiles_pos : player.percentiles;
  const breakdown = Object.entries(impact.breakdown || {})
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const max = Math.max(0.5, ...breakdown.map(([, v]) => Math.abs(v)));

  const parts = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Skąd bierze się wpływ'),
      el('span', { class: 'card__sub' }, 'wkład każdego składnika w punktach na 100 posiadań')));
  if (!breakdown.length) {
    parts.append(el('div', { class: 'empty' },
      'Rozbicie wpływu pojawi się, gdy liga rozegra dość meczów, żeby dopasować model box-score.'));
  }
  for (const [group, value] of breakdown) {
    const bar = el('div', { class: 'pbar', style: 'position:relative' });
    const fill = el('i');
    fill.style.width = (Math.abs(value) / max) * 50 + '%';
    fill.style.left = value >= 0 ? '50%' : 'auto';
    fill.style.right = value >= 0 ? 'auto' : '50%';
    fill.style.background = value >= 0 ? 'var(--good)' : 'var(--bad)';
    bar.append(fill);
    parts.append(el('div', { class: 'prow' },
      el('div', { class: 'prow__name' }, IMPACT_GROUPS[group] || group),
      bar,
      el('div', { class: 'prow__val' }, signed(value, 2))));
  }

  const place = (key) => {
    const rank = player.ranks?.[key];
    return rank ? `#${rank}${player.ranked_of ? ' z ' + player.ranked_of : ''}` : null;
  };
  const lines = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Na tle ligi'),
      el('span', { class: 'card__sub' }, `pozycja wśród ${player.ranked_of || '–'} zawodników`)),
    ratingLine({ label: 'IMPACT', value: impact.total, percentile: pc?.total, rank: player.ranks?.total, format: (v) => signed(v, 1) }),
    ratingLine({ label: 'OFF', value: impact.off, percentile: pc?.off, rank: player.ranks?.off, format: (v) => signed(v, 1) }),
    ratingLine({ label: 'DEF', value: impact.def, percentile: pc?.def, rank: player.ranks?.def, format: (v) => signed(v, 1) }));

  return section('Wpływ na grę', 'BasketLab Impact = skorygowane on/off + model box-score dopasowany do 1 LM',
    el('div', { class: 'grid grid--impact' },
      statTile({ metric: 'impact', value: signed(impact.total, 1), percentile: pc?.total, hint: place('total') }),
      statTile({ metric: 'impact_off', value: signed(impact.off, 1), percentile: pc?.off, hint: place('off') }),
      statTile({ metric: 'impact_def', value: signed(impact.def, 1), percentile: pc?.def, hint: place('def') }),
      lines),
    el('div', { style: 'height:14px' }),
    parts);
}

/* --- produkcja ------------------------------------------------------------- */
function productionSection(totals, gp) {
  const per = (key) => num((totals[key] || 0) / Math.max(gp, 1), 1);
  const per40 = (key) => num(((totals[key] || 0) * 40) / Math.max(totals.min || 1, 1), 1);
  const cards = el('div', { class: 'grid grid--4' },
    statTile({ metric: 'pts', label: 'PKT / MECZ', value: per('pts') }),
    statTile({ metric: 'trb', label: 'ZB / MECZ', value: per('trb') }),
    statTile({ metric: 'ast', label: 'AS / MECZ', value: per('ast') }),
    statTile({ metric: 'ts', value: num(ts(totals), 1), suffix: '%' }));

  const table = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Produkcja'),
      el('span', { class: 'card__sub' }, `${gp} ${gp === 1 ? 'mecz' : 'meczów'} · ${num(totals.min, 0)} minut`)),
    el('div', { class: 'grid grid--2' },
      column([
        ['Punkty', per('pts'), per40('pts')],
        ['Zbiórki', per('trb'), per40('trb')],
        ['Asysty', per('ast'), per40('ast')],
        ['Straty', per('tov'), per40('tov')],
      ]),
      column([
        ['Przechwyty', per('stl'), per40('stl')],
        ['Bloki', per('blk'), per40('blk')],
        ['Faule', per('pf'), per40('pf')],
        ['Wymuszone faule', per('fd'), per40('fd')],
      ])));

  return section('Statystyki podstawowe', 'kolumny: na mecz · na 40 minut', cards, el('div', { style: 'height:14px' }), table);
}

function column(rows) {
  return el('div', {}, rows.map(([label, a, b]) => el('div', { class: 'prow', style: 'grid-template-columns:1fr 60px 60px' },
    el('div', { class: 'prow__name' }, label),
    el('div', { class: 'prow__val' }, a),
    el('div', { class: 'prow__val muted' }, b))));
}

/* --- percentyle ------------------------------------------------------------ */
function percentilesSection() {
  const scope = state.scope === 'pos' ? 'percentiles_pos' : 'percentiles';
  const pc = player[scope] || player.percentiles;
  const m = player.metrics || {};
  const card = el('div', { class: 'card' });
  for (const [key, label, pick] of PERCENTILE_ROWS) {
    card.append(percentileRow({ metric: key, label, value: pick(m), percentile: pc?.[key] }));
  }

  const profile = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Profil umiejętności'),
      el('span', { class: 'card__sub' }, 'percentyl w lidze')),
    pizza(playerSkills(player, scope), { size: 320 }),
    el('div', { class: 'grid grid--3', style: 'margin-top:12px' },
      statTile({ metric: 'ppp_ind', value: num(player.metrics?.ppp_ind, 2) }),
      statTile({ metric: 'ppp_on', value: num(pppOnCourt(player), 2) }),
      statTile({ metric: 'usage', value: num(player.metrics?.usage, 1), suffix: '%',
        percentile: pc?.usage })));

  return section('Percentyle sezonowe',
    state.scope === 'pos' ? 'porównanie wewnątrz grupy pozycyjnej' : 'porównanie z całą ligą',
    el('div', { class: 'grid grid--2' }, card, profile));
}

/* --- on/off ---------------------------------------------------------------- */
function onOffSection(on, off) {
  const rate = (pts, poss) => (poss ? (100 * pts) / poss : null);
  const onO = rate(on.pts, on.off_poss);
  const onD = rate(on.opp_pts, on.def_poss);
  const offO = rate(off.pts, off.off_poss);
  const offD = rate(off.opp_pts, off.def_poss);
  const onNet = onO === null || onD === null ? null : onO - onD;
  const offNet = offO === null || offD === null ? null : offO - offD;

  const table = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Na parkiecie i poza nim'),
      el('span', { class: 'card__sub' }, `${num(on.off_poss, 0)} posiadań w ataku · ${num(on.def_poss, 0)} w obronie`)),
    el('div', { class: 'prow', style: 'grid-template-columns:1fr 70px 70px 70px' },
      el('div', { class: 'prow__name muted' }, ''),
      el('div', { class: 'prow__val muted' }, 'OFF'),
      el('div', { class: 'prow__val muted' }, 'DEF'),
      el('div', { class: 'prow__val muted' }, 'NET')),
    onOffRow('Na parkiecie', onO, onD, onNet),
    onOffRow('Na ławce', offO, offD, offNet),
    onOffRow('Różnica', onO === null || offO === null ? null : onO - offO,
      onD === null || offD === null ? null : onD - offD,
      onNet === null || offNet === null ? null : onNet - offNet, true));

  const adjusted = el('div', { class: 'grid grid--3' },
    statTile({ metric: 'adj_net_player', value: signed(player.on_off?.adj_net, 1) }),
    statTile({ metric: 'on_net', value: signed(player.on_off?.on_net, 1) }),
    statTile({ metric: 'diff', value: signed(player.on_off?.diff, 1) }));

  return section('On / Off', 'ile drużyna zyskuje, gdy zawodnik jest na boisku',
    el('div', { class: 'grid grid--2' }, table, adjusted));
}

function onOffRow(label, o, d, net, emphasise = false) {
  return el('div', { class: 'prow', style: 'grid-template-columns:1fr 70px 70px 70px' },
    el('div', { class: 'prow__name' }, label),
    el('div', { class: 'prow__val' }, emphasise ? signed(o, 1) : num(o, 1)),
    el('div', { class: 'prow__val' }, emphasise ? signed(d, 1) : num(d, 1)),
    el('div', { class: 'prow__val ' + (net >= 0 ? 'delta--up' : 'delta--down') }, signed(net, 1)));
}

/* --- rzuty ----------------------------------------------------------------- */
function shootingSection(rows, totals) {
  const shots = shotsOf(rows);
  const detailed = zoneProfile(zonesFromShots(shots, 'zone14'), ZONES14);
  const simple = zoneProfile(zonesFromShots(shots, 'zone'));
  const leagueDetailed = league.league.zones14;
  const leagueSimple = league.league.zones;
  const expected = expectedPps(zonesFromShots(shots, 'zone14'), leagueDetailed, ZONES14);
  const actual = shots.length
    ? shots.reduce((sum, s) => sum + (s.made ? (s.three ? 3 : 2) : 0), 0) / shots.length : null;

  const map = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Mapa rzutów'),
      shotModeSwitch(state.shots, (mode) => { state.shots = mode; render(); })),
    shotChart(shots, detailed, leagueDetailed, { mode: state.shots }),
    shotLegend(state.shots),
    el('div', { class: 'card__sub', style: 'margin-top:8px;text-align:center' },
      `${shots.length} rzutów z gry z zarejestrowaną pozycją`));

  const table = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Strefy'),
      el('span', { class: 'card__sub' }, 'PPS na tle ligi')),
    dataTable([
      { key: 'zone', label: 'Strefa', render: (r) => zoneName(r.zone) },
      { key: 'fga', label: 'PRÓBY', render: (r) => `${r.fgm}/${r.fga}` },
      { key: 'freq', label: 'UDZIAŁ', render: (r) => num(r.freq, 1) },
      { key: 'fg_pct', label: 'SK%', render: (r) => num(r.fg_pct, 1) },
      { key: 'pps', label: 'PPS', metric: 'pps', render: (r) => num(r.pps, 2) },
      { key: 'lg', label: 'LIGA', render: (r) => num(r.lg, 2) },
      { key: 'diff', label: '+/-', render: (r) => el('span', { class: r.diff >= 0 ? 'delta--up' : 'delta--down' }, signed(r.diff, 2)) },
    ], Object.entries(simple).filter(([, v]) => v.fga).map(([zone, v]) => ({
      zone, ...v, lg: leagueSimple?.[zone]?.pps,
      diff: v.pps === null || leagueSimple?.[zone]?.pps === undefined ? null : v.pps - leagueSimple[zone].pps,
    })), { sort: 'fga', desc: true }),
    el('div', { style: 'margin-top:14px' }, shotDiet(simple)),
    el('div', { class: 'grid grid--3', style: 'margin-top:14px' },
      statTile({ metric: 'xpts', value: num(expected, 2), hint: 'oczekiwane PPS' }),
      statTile({ metric: 'pps', value: num(actual, 2), hint: 'rzeczywiste PPS' }),
      statTile({ metric: 'shot_making', value: signed(actual === null || expected === null ? null : actual - expected, 2) })));

  return section('Shooting Lab', `eFG% ${num(efg(totals), 1)} · TS% ${num(ts(totals), 1)}`,
    el('div', { class: 'grid grid--2' }, map, table));
}

/* --- mecz po meczu --------------------------------------------------------- */
function gamelogSection(rows) {
  const points = rows.map((row) => ({
    value: row.stats.pts,
    date: row.date,
    title: `${dateLabel(row.date)} ${row.home ? 'vs' : '@'} ${teamName(row.opp)}`,
  }));
  const netPoints = rows.map((row) => {
    const o = row.on?.off_poss ? (100 * row.on.pts) / row.on.off_poss : null;
    const d = row.on?.def_poss ? (100 * row.on.opp_pts) / row.on.def_poss : null;
    return {
      value: o === null || d === null ? null : o - d,
      date: row.date,
      title: `${dateLabel(row.date)} ${row.home ? 'vs' : '@'} ${teamName(row.opp)}`,
    };
  });

  const columns = [
    { key: 'date', label: 'Mecz', sortValue: (r) => r.date,
      render: (r) => el('a', { class: 'link', href: `games.html?m=${r.match_id}&p=${encodeURIComponent(player.key)}`, style: 'color:var(--brand)' },
        `${dateLabel(r.date)} ${r.home ? 'vs' : '@'} ${teamName(r.opp)}`) },
    { key: 'win', label: 'W/P', sortValue: (r) => (r.win ? 1 : 0), render: (r) => el('span', { class: r.win ? 'delta--up' : 'delta--down' }, r.win ? 'W' : 'P') },
    { key: 'min', label: 'MIN', sortValue: (r) => r.stats.min, render: (r) => num(r.stats.min, 1) },
    { key: 'pts', label: 'PKT', sortValue: (r) => r.stats.pts, render: (r) => r.stats.pts },
    { key: 'fg', label: 'FG', sortValue: (r) => r.stats.fgm, render: (r) => `${r.stats.fgm}/${r.stats.fga}` },
    { key: 'tp', label: '3PT', sortValue: (r) => r.stats.tpm, render: (r) => `${r.stats.tpm}/${r.stats.tpa}` },
    { key: 'ft', label: 'FT', sortValue: (r) => r.stats.ftm, render: (r) => `${r.stats.ftm}/${r.stats.fta}` },
    { key: 'trb', label: 'ZB', sortValue: (r) => r.stats.trb, render: (r) => r.stats.trb },
    { key: 'ast', label: 'AS', sortValue: (r) => r.stats.ast, render: (r) => r.stats.ast },
    { key: 'tov', label: 'STR', sortValue: (r) => r.stats.tov, render: (r) => r.stats.tov },
    { key: 'pm', label: '+/-', metric: 'plus_minus', sortValue: (r) => r.stats.plus_minus, render: (r) => signed(r.stats.plus_minus, 0) },
    { key: 'onposs', label: 'POS (on)', sortValue: (r) => r.on?.off_poss, render: (r) => num(r.on?.off_poss, 0) },
  ];

  return section('Mecz po meczu', 'słupki: punkty · linia: NET rating przy zawodniku na parkiecie · kliknij mecz, żeby zobaczyć jego przebieg',
    el('div', { class: 'grid grid--2' },
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'Punkty')),
        divergingBars(points, { format: (v) => num(v, 0) })),
      el('div', { class: 'card' },
        el('div', { class: 'card__head' }, el('h2', {}, 'NET on-court')),
        formLine(netPoints, { format: (v) => signed(v, 1) }))),
    el('div', { style: 'height:14px' }),
    el('div', { class: 'card' }, dataTable(columns, rows, { sort: 'date', desc: true })));
}
