/* Centrum meczu - pelne play-by-play z protokolu FIBA LiveStats.

   Kazde zdarzenie ma juz rozwiazany klucz zawodnika, wiec filtr "tylko ten
   zawodnik" nie wymaga dopasowywania po nazwisku. Obok listy pokazujemy
   posiadania odtworzone z protokolu razem ze skladami na parkiecie. */

import {
  dateLabel, el, fail, initTooltips, load, mountChrome, num, qs, restoreTheme, signed,
} from './core.js';

restoreTheme();

const SHOT_TYPES = {
  jumpshot: 'z wyskoku',
  layup: 'lay-up',
  dunk: 'wsad',
  hookshot: 'hakiem',
  fadeaway: 'z odchylenia',
  stepbackjumpshot: 'z odskoku',
  floatingjumpshot: 'floater',
  eurostep: 'eurostep',
  tipinlayup: 'dobitka',
  turnaround: 'z obrotu',
  alleyoop: 'alley-oop',
};

const TURNOVERS = {
  badpass: 'złe podanie',
  ballhandling: 'błąd kozłowania',
  travel: 'kroki',
  outofbounds: 'poza boiskiem',
  offensive: 'faul w ataku',
  doubledribble: 'podwójne kozłowanie',
  '3sec': '3 sekundy',
  '5sec': '5 sekund',
  '8sec': '8 sekund',
  '24sec': '24 sekundy',
  backcourt: 'powrót na własną połowę',
  other: 'strata',
};

const FOULS = {
  personal: 'faul osobisty',
  offensive: 'faul w ataku',
  technical: 'faul techniczny',
  unsportsmanlike: 'faul niesportowy',
  disqualifying: 'faul dyskwalifikujący',
  coachTechnical: 'techniczny trenera',
  benchTechnical: 'techniczny ławki',
};

/** Zamienia zdarzenie protokolu na polski opis. */
function describe(ev) {
  const shot = SHOT_TYPES[ev.sub] || ev.sub || '';
  switch (ev.action) {
    case '2pt':
    case '3pt':
      return `${ev.made ? 'celny' : 'niecelny'} rzut za ${ev.action === '3pt' ? '3' : '2'}${shot ? ' ' + shot : ''}`;
    case 'freethrow':
      return `${ev.made ? 'celny' : 'niecelny'} rzut wolny ${(ev.sub || '').replace('of', ' z ')}`;
    case 'rebound':
      return ev.sub === 'offensive' ? 'zbiórka w ataku' : 'zbiórka w obronie';
    case 'assist': return 'asysta';
    case 'steal': return 'przechwyt';
    case 'block': return 'blok';
    case 'turnover': return 'strata — ' + (TURNOVERS[ev.sub] || ev.sub || '');
    case 'foul': return FOULS[ev.sub] || 'faul';
    case 'foulon': return 'wymuszony faul';
    case 'substitution': return ev.sub === 'in' ? 'wchodzi na boisko' : 'schodzi z boiska';
    case 'timeout': return 'przerwa na żądanie';
    case 'jumpball':
      if (ev.sub === 'won') return 'wygrany rzut sędziowski';
      if (ev.sub === 'lost') return 'przegrany rzut sędziowski';
      return 'rzut sędziowski';
    case 'period': return ev.sub === 'start' ? 'początek kwarty' : 'koniec kwarty';
    case 'game': return ev.sub === 'start' ? 'początek meczu' : 'koniec meczu';
    default: return [ev.action, ev.sub].filter(Boolean).join(' ');
  }
}

const state = { match: '', player: '', period: 0, onlyPlayer: false };
let meta;
let club;
let players;
let pbp;

init().catch((error) => fail(document.getElementById('content'), error));

async function init() {
  await initTooltips();
  meta = await mountChrome('games');
  [club, players] = await Promise.all([load('club'), load('players')]);
  const games = sortedGames();
  state.match = qs('m') || (games.length ? games[games.length - 1].match_id : '');
  state.player = qs('p') || '';
  state.onlyPlayer = Boolean(state.player);
  if (!state.match) {
    document.getElementById('content').replaceChildren(
      el('div', { class: 'card empty' }, 'Brak meczów w bazie.'));
    return;
  }
  await loadMatch();
}

function sortedGames() {
  return [...(club.games || [])].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
}

function teamName(key) {
  const team = meta.teams.find((t) => t.key === key);
  return team?.short || team?.name || key;
}

function playerOf(key) {
  return players.find((p) => p.key === key);
}

async function loadMatch() {
  pbp = await load('pbp/' + state.match);
  renderFilters();
  render();
}

function renderFilters() {
  const bar = document.getElementById('filters');
  const games = sortedGames();

  const matchSelect = el('select', {
    onchange: async (e) => { state.match = e.target.value; await loadMatch(); },
  }, games.map((g) => el('option', { value: g.match_id },
    `${dateLabel(g.date)} · ${teamName(g.home)} ${g.home_score}:${g.away_score} ${teamName(g.away)}`)));
  matchSelect.value = state.match;

  const playerSelect = el('select', {
    onchange: (e) => { state.player = e.target.value; render(); },
  }, el('option', { value: '' }, 'Wszyscy zawodnicy'),
    ...players.map((p) => el('option', { value: p.key }, p.name)));
  playerSelect.value = state.player;

  const periods = el('div', { class: 'seg' },
    el('button', { class: state.period === 0 ? 'is-on' : '', onclick: () => { state.period = 0; renderFilters(); render(); } }, 'Cały mecz'),
    ...[1, 2, 3, 4].map((p) => el('button', {
      class: state.period === p ? 'is-on' : '',
      onclick: () => { state.period = p; renderFilters(); render(); },
    }, 'Q' + p)));

  const only = el('div', { class: 'seg' },
    el('button', { class: !state.onlyPlayer ? 'is-on' : '', onclick: () => { state.onlyPlayer = false; renderFilters(); render(); } }, 'Wszystko'),
    el('button', { class: state.onlyPlayer ? 'is-on' : '', onclick: () => { state.onlyPlayer = true; renderFilters(); render(); } }, 'Tylko wybrany'));

  bar.replaceChildren(matchSelect, playerSelect, periods, only);
}

function visibleEvents() {
  let events = pbp.events.filter((e) => e.action !== 'game');
  if (state.period) events = events.filter((e) => e.period === state.period);
  if (state.player && state.onlyPlayer) events = events.filter((e) => e.player === state.player);
  return events;
}

function render() {
  const content = document.getElementById('content');
  const game = sortedGames().find((g) => g.match_id === state.match);
  const events = visibleEvents();
  const profile = state.player ? playerOf(state.player) : null;

  document.getElementById('head').replaceChildren(
    el('div', { class: 'eyebrow' }, 'Centrum meczu'),
    el('h1', {}, game
      ? `${teamName(game.home)} ${game.home_score} : ${game.away_score} ${teamName(game.away)}`
      : 'Przebieg meczu'),
    el('p', {}, game
      ? `${dateLabel(game.date)}${game.venue ? ' · ' + game.venue : ''} · pełne play-by-play z protokołu FIBA LiveStats`
      : 'Pełne play-by-play z protokołu FIBA LiveStats.'));

  content.replaceChildren(
    el('div', { class: 'grid grid--2' },
      feedCard(events, profile),
      el('div', {}, summaryCard(), possessionCard())),
  );
}

function feedCard(events, profile) {
  const list = el('div', { class: 'pbp' });
  let period = 0;
  for (const ev of events) {
    if (ev.period !== period) {
      period = ev.period;
      list.append(el('div', { class: 'card__sub', style: 'padding:10px 4px 6px;font-weight:650' },
        period <= 4 ? `Kwarta ${period}` : `Dogrywka ${period - 4}`));
    }
    const mine = state.player && ev.player === state.player;
    const made = ev.made === true;
    const miss = ev.made === false;
    list.append(el('div', { class: 'pbp__row' + (mine ? ' is-player' : '') },
      el('div', { class: 'pbp__clock' }, ev.gt),
      el('div', { class: 'pbp__score' }, `${ev.s1}:${ev.s2}`),
      el('div', { class: 'pbp__what' + (made ? ' is-made' : miss ? ' is-miss' : '') },
        ev.name ? el('b', {}, `${ev.shirt ? '#' + ev.shirt + ' ' : ''}${ev.name}`) : null,
        ev.name ? ' — ' : '',
        describe(ev),
        ev.team ? el('span', { class: 'muted' }, ` · ${teamName(ev.team)}`) : null)));
  }
  if (!events.length) list.append(el('div', { class: 'empty' }, 'Brak zdarzeń dla tego filtru.'));

  return el('div', { class: 'card' },
    el('div', { class: 'card__head' },
      el('h2', {}, 'Przebieg meczu'),
      el('span', { class: 'card__sub' },
        `${events.length} zdarzeń${profile ? ' · podświetlony: ' + profile.name : ''}`)),
    list);
}

function summaryCard() {
  const own = {};
  for (const ev of pbp.events) {
    if (!state.player || ev.player !== state.player) continue;
    const key = ev.action === '2pt' || ev.action === '3pt'
      ? `${ev.action} ${ev.made ? 'celne' : 'niecelne'}`
      : ev.action;
    own[key] = (own[key] || 0) + 1;
  }
  const rows = Object.entries(own).sort((a, b) => b[1] - a[1]);
  return el('div', { class: 'card', style: 'margin-bottom:14px' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Udział zawodnika'),
      el('span', { class: 'card__sub' }, state.player ? 'liczba zdarzeń w protokole' : 'wybierz zawodnika')),
    rows.length
      ? el('div', {}, rows.map(([key, count]) => el('div', { class: 'prow', style: 'grid-template-columns:1fr 50px' },
        el('div', { class: 'prow__name' }, key),
        el('div', { class: 'prow__val' }, count))))
      : el('div', { class: 'empty' }, 'Wybierz zawodnika z listy powyżej.'));
}

function possessionCard() {
  const list = state.period
    ? pbp.possessions.filter((p) => p.period === state.period)
    : pbp.possessions;
  const club = meta.club.key;
  const own = list.filter((p) => p.offense === club);
  const points = own.reduce((sum, p) => sum + p.points, 0);
  const against = list.filter((p) => p.defense === club);
  const conceded = against.reduce((sum, p) => sum + p.points, 0);

  return el('div', { class: 'card' },
    el('div', { class: 'card__head' }, el('h2', {}, 'Posiadania'),
      el('span', { class: 'card__sub' }, 'odtworzone z play-by-play')),
    el('div', { class: 'prow', style: 'grid-template-columns:1fr 70px 70px' },
      el('div', { class: 'prow__name muted' }, ''),
      el('div', { class: 'prow__val muted' }, 'POS'),
      el('div', { class: 'prow__val muted' }, 'PKT/100')),
    el('div', { class: 'prow', style: 'grid-template-columns:1fr 70px 70px' },
      el('div', { class: 'prow__name' }, 'Atak'),
      el('div', { class: 'prow__val' }, own.length),
      el('div', { class: 'prow__val' }, num(own.length ? (100 * points) / own.length : null, 1))),
    el('div', { class: 'prow', style: 'grid-template-columns:1fr 70px 70px' },
      el('div', { class: 'prow__name' }, 'Obrona'),
      el('div', { class: 'prow__val' }, against.length),
      el('div', { class: 'prow__val' }, num(against.length ? (100 * conceded) / against.length : null, 1))),
    el('div', { class: 'prow', style: 'grid-template-columns:1fr 140px' },
      el('div', { class: 'prow__name' }, 'Bilans na 100 posiadań'),
      el('div', { class: 'prow__val' },
        signed(own.length && against.length
          ? (100 * points) / own.length - (100 * conceded) / against.length : null, 1))));
}
