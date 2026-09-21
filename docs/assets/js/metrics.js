/* Metryki liczone w przegladarce.
   Te same wzory co w ekstraktorze (extractor/basketlab/metrics.py) - dzieki temu
   filtry "ostatnie 5", "dom", "wyjazd" czy pojedynczy mecz daja spojne liczby
   razem z miejscem w lidze, bez odpytywania serwera. */

const FT = 0.44;
export const ZONES = ['RIM', 'PAINT', 'SHORT_MID', 'LONG_MID', 'CORNER_3', 'ABOVE_BREAK_3'];

/** Siatka szczegolowa mapy rzutow - kolejnosc jak w ekstraktorze. */
export const ZONES14 = [
  'RA', 'PAINT', 'SM_L', 'SM_R',
  'LM_L', 'LM_LC', 'LM_C', 'LM_RC', 'LM_R',
  'C3_L', 'C3_R', 'AB3_L', 'AB3_C', 'AB3_R',
];

const COUNTING = ['min', 'pts', 'fga', 'fgm', 'tpa', 'tpm', 'fta', 'ftm', 'orb', 'drb',
  'trb', 'ast', 'tov', 'stl', 'blk', 'pf', 'fd', 'pts_paint', 'pts_fb', 'pts_2nd'];

export function emptyStats() {
  return Object.fromEntries(COUNTING.map((k) => [k, 0]));
}

export function addStats(target, source) {
  for (const [key, value] of Object.entries(source || {})) {
    if (typeof value === 'number') target[key] = (target[key] || 0) + value;
  }
  return target;
}

function div(a, b) { return b ? a / b : null; }
function pct(a, b) { const v = div(a, b); return v === null ? null : v * 100; }
const g = (s, k) => Number(s?.[k] || 0);

/* --- wskazniki podstawowe -------------------------------------------------- */
export const efg = (s) => pct(g(s, 'fgm') + 0.5 * g(s, 'tpm'), g(s, 'fga'));
export const ts = (s) => pct(g(s, 'pts'), 2 * (g(s, 'fga') + FT * g(s, 'fta')));
export const fgPct = (s) => pct(g(s, 'fgm'), g(s, 'fga'));
export const threePct = (s) => pct(g(s, 'tpm'), g(s, 'tpa'));
export const twoPct = (s) => pct(g(s, 'fgm') - g(s, 'tpm'), g(s, 'fga') - g(s, 'tpa'));
export const ftPct = (s) => pct(g(s, 'ftm'), g(s, 'fta'));
export const threeRate = (s) => pct(g(s, 'tpa'), g(s, 'fga'));
export const ftRate = (s) => pct(g(s, 'fta'), g(s, 'fga'));
export const boxPoss = (s) => g(s, 'fga') - g(s, 'orb') + g(s, 'tov') + FT * g(s, 'fta');
export const ortg = (points, poss) => div(100 * points, poss);

/* --- agregat druzyny ------------------------------------------------------- */
/** Sumuje wiersze meczowe druzyny i liczy komplet wskaznikow. */
export function teamSplit(rows) {
  const stats = emptyStats();
  const opp = emptyStats();
  const zones = {};
  const oppZones = {};
  let pts = 0, oppPts = 0, poss = 0, oppPoss = 0, w = 0, l = 0, kill = 0, killAgainst = 0;

  for (const row of rows) {
    addStats(stats, row.stats);
    addStats(opp, row.opp_stats);
    mergeZones(zones, row.zones);
    mergeZones(oppZones, row.opp_zones);
    pts += row.pts;
    oppPts += row.opp_pts;
    poss += row.poss || 0;
    oppPoss += row.opp_poss || 0;
    kill += row.kill_shots || 0;
    killAgainst += row.kill_allowed || 0;
    if (row.pts > row.opp_pts) w += 1; else l += 1;
  }

  const gp = rows.length;
  const usedPoss = poss || boxPoss(stats);
  const usedOppPoss = oppPoss || boxPoss(opp);
  const o = ortg(pts, usedPoss);
  const d = ortg(oppPts, usedOppPoss);
  const minutes = stats.min || gp * 200;

  return {
    gp, w, l, pts, opp_pts: oppPts, stats, opp_stats: opp, zones, opp_zones: oppZones,
    poss: usedPoss, opp_poss: usedOppPoss,
    pace: div((usedPoss + usedOppPoss) / 2 * 40, minutes / 5),
    ortg: o, drtg: d, net: o === null || d === null ? null : o - d,
    efg: efg(stats), opp_efg: efg(opp),
    ts: ts(stats), opp_ts: ts(opp),
    tov_rate: pct(g(stats, 'tov'), usedPoss),
    opp_tov_rate: pct(g(opp, 'tov'), usedOppPoss),
    orb_rate: pct(g(stats, 'orb'), g(stats, 'orb') + g(opp, 'drb')),
    drb_rate: pct(g(stats, 'drb'), g(stats, 'drb') + g(opp, 'orb')),
    ft_rate: ftRate(stats), opp_ft_rate: ftRate(opp),
    tpar: threeRate(stats), opp_tpar: threeRate(opp),
    three_pct: threePct(stats), two_pct: twoPct(stats), ft_pct: ftPct(stats),
    ast_rate: pct(g(stats, 'ast'), g(stats, 'fgm')),
    ast_to: div(g(stats, 'ast'), g(stats, 'tov')),
    stl_100: div(100 * g(stats, 'stl'), usedOppPoss),
    blk_100: div(100 * g(stats, 'blk'), usedOppPoss),
    pts_paint: div(g(stats, 'pts_paint'), gp),
    pts_fb: div(g(stats, 'pts_fb'), gp),
    pts_2nd: div(g(stats, 'pts_2nd'), gp),
    kill_shots: div(kill, gp), kill_allowed: div(killAgainst, gp),
    morey: moreyScore(zones),
    zone_profile: zoneProfile(zones),
    opp_zone_profile: zoneProfile(oppZones),
  };
}

export function mergeZones(target, source) {
  for (const [zone, values] of Object.entries(source || {})) {
    const bucket = target[zone] || (target[zone] = { fga: 0, fgm: 0, pts: 0 });
    for (const [key, value] of Object.entries(values)) bucket[key] += value;
  }
  return target;
}

export function zoneProfile(zones, names = ZONES) {
  const total = Object.values(zones || {}).reduce((sum, z) => sum + (z.fga || 0), 0);
  const out = {};
  for (const zone of names) {
    const v = zones?.[zone] || {};
    out[zone] = {
      fga: v.fga || 0,
      fgm: v.fgm || 0,
      freq: pct(v.fga || 0, total),
      fg_pct: pct(v.fgm || 0, v.fga || 0),
      pps: div(v.pts || 0, v.fga || 0),
    };
  }
  return out;
}

/** Sumuje rzuty w kubelki wybranej siatki stref (`zone` albo `zone14`). */
export function zonesFromShots(shots, key = 'zone14') {
  const out = {};
  for (const shot of shots) {
    const zone = shot[key];
    if (!zone) continue;
    const bucket = out[zone] || (out[zone] = { fga: 0, fgm: 0, pts: 0 });
    bucket.fga += 1;
    if (shot.made) {
      bucket.fgm += 1;
      bucket.pts += shot.three ? 3 : 2;
    }
  }
  return out;
}

export function moreyScore(zones) {
  const total = Object.values(zones || {}).reduce((sum, z) => sum + (z.fga || 0), 0);
  const good = ['RIM', 'CORNER_3', 'ABOVE_BREAK_3']
    .reduce((sum, z) => sum + (zones?.[z]?.fga || 0), 0);
  return pct(good, total);
}

/* --- oczekiwane punkty ----------------------------------------------------- */
/** xPTS lite: ile punktow na rzut dawalby ten rozklad stref przy ligowej skutecznosci. */
export function expectedPps(zones, leagueProfile, names = ZONES) {
  let shots = 0, expected = 0;
  for (const zone of names) {
    const fga = zones?.[zone]?.fga || 0;
    const base = leagueProfile?.[zone]?.pps;
    if (!fga || base === null || base === undefined) continue;
    shots += fga;
    expected += fga * base;
  }
  return div(expected, shots);
}

/* --- wycinki posiadan ------------------------------------------------------ */
/** Sumuje kubelki clutch albo +15 z wybranych meczow. */
export function sumBuckets(rows, key) {
  const out = {};
  for (const row of rows) {
    for (const [k, v] of Object.entries(row[key] || {})) {
      if (typeof v === 'number') out[k] = (out[k] || 0) + v;
    }
  }
  return out;
}

/** Odsetek rzutow oddanych w akcjach trwajacych 15 sekund i dluzej. */
export const fgaLongRate = (b) => pct(g(b, 'fga_long'), g(b, 'fga'));

/** Punkty na jedno dlugie posiadanie. */
export const pppLong = (b) => div(g(b, 'pts_long'), g(b, 'off_poss_long'));

/** Ratingi z koncowek meczu. */
export function clutchRatings(b) {
  const o = ortg(g(b, 'pts'), g(b, 'off_poss'));
  const d = ortg(g(b, 'opp_pts'), g(b, 'def_poss'));
  return {
    off_poss: g(b, 'off_poss'),
    def_poss: g(b, 'def_poss'),
    min: g(b, 'secs') / 60,
    pts: g(b, 'pts'),
    opp_pts: g(b, 'opp_pts'),
    ortg: o,
    drtg: d,
    net: o === null || d === null ? null : o - d,
  };
}

/* --- profil umiejetnosci --------------------------------------------------- */
const fmt = (v, digits = 1, suffix = '') =>
  (v === null || v === undefined ? '–' : Number(v).toFixed(digits) + suffix);

/**
 * Zestaw umiejetnosci pokazywany na kaflu i w profilu - te same szesc kategorii
 * co na Dunks & Threes (PTS, TS%, AST, TOV, STL, BLK), liczone jako percentyl
 * w lidze. TOV jest odwrocone przy liczeniu percentyla, wiec wysoki slupek
 * zawsze znaczy "dobrze".
 */
export function playerSkills(player, scope = 'percentiles') {
  const pc = player[scope] || player.percentiles || {};
  const rank = player.ranks || {};
  const m = player.metrics || {};
  const f = player.features || {};
  const make = (key, short, axis, label, display) => ({
    key, short, axis, label, display, value: pc[key] ?? null, rank: rank[key] ?? null,
  });
  return [
    make('scoring_100', 'PTS', 'Punkty', 'Punkty na 100 posiadań', fmt(f.scoring_100)),
    make('ts', 'TS%', 'Rzuty', 'True Shooting %', fmt(m.ts, 1, '%')),
    make('ast_rate', 'AST', 'Kreowanie', 'Assist Rate (AST%)', fmt(m.ast_rate, 1, '%')),
    make('tov_rate', 'TOV', 'Ochrona', 'Turnover Rate (TOV%)', fmt(m.tov_rate, 1, '%')),
    make('stl_rate', 'STL', 'Przechwyty', 'Steal Rate (STL%)', fmt(m.stl_rate, 2, '%')),
    make('blk_rate', 'BLK', 'Bloki', 'Block Rate (BLK%)', fmt(m.blk_rate, 2, '%')),
  ];
}

/** PPP zespolu, gdy zawodnik jest na parkiecie. */
export function pppOnCourt(player) {
  const rating = player.on_off?.on_ortg;
  return rating === null || rating === undefined ? null : rating / 100;
}

/* --- osie wykresu porownawczego ------------------------------------------- */
/**
 * Wskazniki, ktore mozna wybrac na osie mapy stylu. `higher` decyduje tylko
 * o kolorze i kierunku rankingu; wykres i tak rysuje wartosci wprost.
 */
export const TEAM_AXES = [
  { key: 'ortg', label: 'OFF RTG', get: (s) => s.ortg, higher: true },
  { key: 'drtg', label: 'DEF RTG', get: (s) => s.drtg, higher: false },
  { key: 'net', label: 'NET RTG', get: (s) => s.net, higher: true },
  { key: 'pace', label: 'Tempo', get: (s) => s.pace, higher: true },
  { key: 'efg', label: 'eFG%', get: (s) => s.efg, higher: true },
  { key: 'opp_efg', label: 'eFG% rywali', get: (s) => s.opp_efg, higher: false },
  { key: 'ts', label: 'TS%', get: (s) => s.ts, higher: true },
  { key: 'tov_rate', label: 'TOV%', get: (s) => s.tov_rate, higher: false },
  { key: 'opp_tov_rate', label: 'Wymuszone straty', get: (s) => s.opp_tov_rate, higher: true },
  { key: 'orb_rate', label: 'ORB%', get: (s) => s.orb_rate, higher: true },
  { key: 'drb_rate', label: 'DRB%', get: (s) => s.drb_rate, higher: true },
  { key: 'ft_rate', label: 'FTr', get: (s) => s.ft_rate, higher: true },
  { key: 'opp_ft_rate', label: 'FTr rywali', get: (s) => s.opp_ft_rate, higher: false },
  { key: 'tpar', label: 'Udział rzutów za 3', get: (s) => s.tpar, higher: true },
  { key: 'morey', label: 'Morey Score', get: (s) => s.morey, higher: true },
  { key: 'ast_rate', label: 'AST%', get: (s) => s.ast_rate, higher: true },
  { key: 'kill_shots', label: 'Kill shots', get: (s) => s.kill_shots, higher: true },
];

export const axisOf = (key) => TEAM_AXES.find((a) => a.key === key) || TEAM_AXES[0];

/* --- rankingi -------------------------------------------------------------- */
/** Miejsce kazdej druzyny wedlug wskaznika (1 = najlepsze). */
export function rankMap(values, higherIsBetter = true) {
  const entries = Object.entries(values).filter(([, v]) => v !== null && v !== undefined);
  entries.sort((a, b) => (higherIsBetter ? b[1] - a[1] : a[1] - b[1]));
  const out = {};
  let place = 0;
  let last = null;
  entries.forEach(([key, value], index) => {
    if (last === null || value !== last) { place = index + 1; last = value; }
    out[key] = place;
  });
  return out;
}

export function percentileOf(values, value, higherIsBetter = true) {
  const list = values.filter((v) => v !== null && v !== undefined);
  if (!list.length || value === null || value === undefined) return null;
  const better = list.filter((v) => (higherIsBetter ? v < value : v > value)).length;
  const equal = list.filter((v) => v === value).length;
  return (100 * (better + 0.5 * equal)) / list.length;
}

/* --- filtry meczowe --------------------------------------------------------- */
export const FILTERS = {
  all: { label: 'Sezon', apply: (rows) => rows },
  last5: { label: 'Ostatnie 5', apply: (rows) => rows.slice(-5) },
  home: { label: 'Dom', apply: (rows) => rows.filter((r) => r.home) },
  away: { label: 'Wyjazd', apply: (rows) => rows.filter((r) => !r.home) },
  wins: { label: 'Wygrane', apply: (rows) => rows.filter((r) => r.pts > r.opp_pts) },
  losses: { label: 'Porazki', apply: (rows) => rows.filter((r) => r.pts < r.opp_pts) },
};

export function byDate(rows) {
  return [...rows].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
}
