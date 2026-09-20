/* Szczegoly jednej piatki: mecz po meczu, pojedynki z piatkami rywali, duety. */

import {
  avatar, crumbs, dataTable, dateLabel, el, fail, initTooltips, load, mountChrome,
  num, qs, restoreTheme, signed, statTile,
} from './core.js';
import { divergingBars } from './charts.js';
import { clutchRatings, fgaLongRate, pppLong } from './metrics.js';

restoreTheme();

let meta;
let players;
let lineup;
let pairs;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('lineups');
  const id = qs('l');
  if (!id) throw new Error('Nie podano piątki.');
  [players, lineup, pairs] = await Promise.all([load('players'), load('lineup/' + id), load('pairs')]);
  renderHead();
  render();
}

function playerOf(key) {
  return players.find((p) => p.key === key)
    || { key, name: key.split(':').pop().replace(/-/g, ' '), photo: '' };
}

function shortName(name) {
  const parts = String(name).trim().split(/\s+/);
  return parts.length < 2 ? name : parts[0][0] + '. ' + parts.slice(1).join(' ');
}

function nameList(keys) {
  return keys.map((k) => shortName(playerOf(k).name)).join(' · ');
}

function teamName(key) {
  const team = meta.teams.find((t) => t.key === key);
  return team?.short || team?.name || key;
}

function poss(row) {
  return (row.off_poss || 0) + (row.def_poss || 0);
}

function renderHead() {
  const head = document.getElementById('head');
  const roster = el('div', { style: 'display:flex;gap:14px;flex-wrap:wrap;margin-top:12px' });
  for (const key of lineup.players) {
    const player = playerOf(key);
    roster.append(el('a', {
      href: `player.html?p=${encodeURIComponent(key)}`,
      style: 'display:flex;gap:9px;align-items:center;background:var(--surface);'
        + 'border:1px solid var(--border-soft);border-radius:12px;padding:8px 13px 8px 8px',
    },
      avatar(player, 'avatar--tiny'),
      el('div', {},
        el('div', { style: 'font-weight:600;font-size:.88rem' }, player.name),
        el('div', { class: 'card__sub' }, `#${player.shirt || '–'} · ${player.position || '–'}`))));
  }

  head.replaceChildren(
    crumbs(['Piątki', 'lineups.html'], nameList(lineup.players)),
    el('h1', {}, nameList(lineup.players)),
    el('p', {}, `${num(lineup.min, 1)} minut · ${num(poss(lineup), 0)} posiadań · `
      + `${lineup.games.length} ${lineup.games.length === 1 ? 'mecz' : 'meczów'}`),
    roster);
}

function render() {
  document.getElementById('content').replaceChildren(
    ratingsSection(),
    contextSection(),
    gamesSection(),
    matchupSection(),
    pairsSection(),
  );
}

function section(title, sub, ...nodes) {
  return el('div', { class: 'section' },
    el('div', { class: 'card__head' }, el('h2', {}, title), sub ? el('span', { class: 'card__sub' }, sub) : null),
    ...nodes);
}

function ratingsSection() {
  const factors = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Four Factors piątki'),
      el('span', { class: 'card__sub' }, 'atak / obrona')),
    row('eFG%', lineup.ff?.efg, lineup.opp_ff?.efg),
    row('TOV%', lineup.ff?.tov_rate, lineup.opp_ff?.tov_rate),
    row('FTr', lineup.ff?.ft_rate, lineup.opp_ff?.ft_rate));

  return section('Efektywność', `${num(lineup.pts, 0)} zdobytych · ${num(lineup.opp_pts, 0)} straconych punktów`,
    el('div', { class: 'grid grid--2' },
      el('div', { class: 'grid grid--3' },
        statTile({ metric: 'ortg', value: num(lineup.ortg, 1), hint: `${num(lineup.off_poss, 0)} pos` }),
        statTile({ metric: 'drtg', value: num(lineup.drtg, 1), hint: `${num(lineup.def_poss, 0)} pos` }),
        statTile({ metric: 'net', value: signed(lineup.net, 1) })),
      factors));
}

/** Koncowki meczow i gra w ustawionej obronie. */
function contextSection() {
  const c = clutchRatings(lineup.clutch || {});
  const long = lineup.long15 || {};
  const played = (c.off_poss || 0) + (c.def_poss || 0) > 0;

  const clutchCard = el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Końcówki meczów'),
      el('span', { class: 'q', 'data-metric': 'clutch' }, '?')),
    played
      ? el('div', {},
        row('Posiadania (atak / obrona)', c.off_poss, c.def_poss),
        row('Punkty (zdobyte / stracone)', c.pts, c.opp_pts),
        row('ORTG / DRTG', c.ortg, c.drtg),
        el('div', { class: 'prow', style: 'grid-template-columns:1fr 80px 80px' },
          el('div', { class: 'prow__name' }, 'NET / minuty'),
          el('div', { class: 'prow__val ' + ((c.net ?? 0) >= 0 ? 'delta--up' : 'delta--down') }, signed(c.net, 1)),
          el('div', { class: 'prow__val muted' }, num(c.min, 1))))
      : el('div', { class: 'empty' },
        'Ta piątka nie grała jeszcze w końcówce przy różnicy do pięciu punktów.'));

  return section('Kontekst gry', 'clutch time oraz akcje trwające 15 sekund i dłużej',
    el('div', { class: 'grid grid--2' },
      clutchCard,
      el('div', { class: 'grid grid--2' },
        statTile({
          metric: 'fga_long_rate',
          value: num(fgaLongRate(long), 1),
          suffix: '%',
          hint: `${num(long.fga_long, 0)} z ${num(long.fga, 0)} rzutów`,
        }),
        statTile({
          metric: 'ppp_long',
          value: num(pppLong(long), 2),
          hint: `${num(long.off_poss_long, 0)} długich akcji`,
        }))));
}

function row(label, own, opp) {
  return el('div', { class: 'prow', style: 'grid-template-columns:1fr 80px 80px' },
    el('div', { class: 'prow__name' }, label),
    el('div', { class: 'prow__val' }, num(own, 1)),
    el('div', { class: 'prow__val muted' }, num(opp, 1)));
}

function gamesSection() {
  const rows = [...lineup.games].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  const points = rows.map((r) => ({
    value: r.net, date: r.date,
    title: `${dateLabel(r.date)} ${teamName(r.opp)}`,
    label: () => `${num(poss(r), 0)} pos · `,
  }));
  const columns = [
    { key: 'date', label: 'Mecz', render: (r) => `${dateLabel(r.date)} · ${teamName(r.opp)}` },
    { key: 'min', label: 'MIN' },
    { key: 'off_poss', label: 'POS ATAK', render: (r) => num(r.off_poss, 0) },
    { key: 'def_poss', label: 'POS OBRONA', render: (r) => num(r.def_poss, 0) },
    { key: 'pts', label: 'PKT', render: (r) => num(r.pts, 0) },
    { key: 'opp_pts', label: 'STRACONE', render: (r) => num(r.opp_pts, 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg' },
    { key: 'drtg', label: 'DEF', metric: 'drtg' },
    { key: 'net', label: 'NET', metric: 'net', render: (r) => el('span', { class: (r.net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(r.net, 1)) },
  ];
  return section('Mecz po meczu', 'słupek = NET rating piątki w danym meczu',
    el('div', { class: 'card', style: 'margin-bottom:14px' }, divergingBars(points, { format: (v) => signed(v, 1), label: (p) => p.label() })),
    el('div', { class: 'card' }, dataTable(columns, rows, { sort: 'date', desc: true })));
}

function matchupSection() {
  const rows = (lineup.matchups || []).filter((r) => poss(r) >= 4);
  if (!rows.length) {
    return section('Przeciwko piątkom rywali', null,
      el('div', { class: 'card empty' }, 'Za mało wspólnych posiadań, żeby pokazać pojedynki piątek.'));
  }
  const columns = [
    { key: 'opp', label: 'Piątka rywala', sortValue: (r) => r.opp_players.join(),
      render: (r) => r.opp_players.map((k) => k.split(':').pop().split('-').slice(-1)[0]).join(' · ') },
    { key: 'min', label: 'MIN' },
    { key: 'off_poss', label: 'POS ATAK', render: (r) => num(r.off_poss, 0) },
    { key: 'def_poss', label: 'POS OBRONA', render: (r) => num(r.def_poss, 0) },
    { key: 'pts', label: 'PKT', render: (r) => num(r.pts, 0) },
    { key: 'opp_pts', label: 'STRACONE', render: (r) => num(r.opp_pts, 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg' },
    { key: 'drtg', label: 'DEF', metric: 'drtg' },
    { key: 'net', label: 'NET', metric: 'net', render: (r) => el('span', { class: (r.net ?? 0) >= 0 ? 'delta--up' : 'delta--down' }, signed(r.net, 1)) },
  ];
  return section('Przeciwko piątkom rywali', 'tylko pojedynki z co najmniej 4 posiadaniami',
    el('div', { class: 'card' }, dataTable(columns, rows, { sort: 'off_poss', desc: true })));
}

function pairsSection() {
  const inside = pairs.filter((p) => p.players.every((k) => lineup.players.includes(k)));
  if (!inside.length) return el('div');
  const columns = [
    { key: 'pair', label: 'Duet', sortValue: (r) => nameList(r.players), render: (r) => nameList(r.players) },
    { key: 'min', label: 'MIN' },
    { key: 'poss', label: 'POS', sortValue: poss, render: (r) => num(poss(r), 0) },
    { key: 'ortg', label: 'OFF', metric: 'ortg' },
    { key: 'drtg', label: 'DEF', metric: 'drtg' },
    { key: 'net', label: 'NET', metric: 'net', render: (r) => signed(r.net, 1) },
  ];
  return section('Duety wewnątrz piątki', 'jak wypadają te same pary w całym sezonie, nie tylko w tej piątce',
    el('div', { class: 'card' }, dataTable(columns, inside, { sort: 'net', desc: true })));
}
