"""Agregacja sezonu: druzyny, zawodnicy, piatki, strefy rzutowe.

Modul zbiera znormalizowane mecze (``model.Game``) w statystyki sezonowe.
Wszystko liczymy dwutorowo:

* z boxscore - sumy licznikowe zawodnikow i druzyn,
* z play-by-play - posiadania, sklady na parkiecie, on/off i piatki.

Nazwy druzyn w LiveStats potrafia sie roznic od terminarza (sponsorzy zmieniaja
sie w trakcie sezonu), dlatego kazda druzyna dostaje klucz kanoniczny
wyznaczany przez podobienstwo nazw.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from . import metrics
from .court import DETAILED_ZONES, ZONES
from .discover import name_similarity, name_tokens, normalize_name
from .model import Game
from .possessions import build_stints, split_possessions

COUNTING_KEYS = [
    "min", "pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm",
    "orb", "drb", "trb", "ast", "tov", "stl", "blk", "blkr",
    "pf", "fd", "pts_paint", "pts_fb", "pts_2nd", "pts_off_tov",
]

PLAYER_COUNTING_KEYS = COUNTING_KEYS + ["plus_minus"]

#: sumy liczone wylacznie w koncowce meczu (clutch time)
CLUTCH_KEYS = ["off_poss", "def_poss", "pts", "opp_pts", "secs"]

#: sumy dla akcji "+15" - licznik dlugich akcji i ich dorobek
LONG_KEYS = ["off_poss", "off_poss_long", "fga", "fga_long", "pts_long"]

#: statystyki zawodnika zbierane ze zdarzen w koncowce meczu
CLUTCH_BOX_KEYS = ["pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm",
                   "orb", "drb", "trb", "ast", "tov", "stl", "blk"]


def _empty(keys: Iterable[str] = COUNTING_KEYS) -> dict[str, float]:
    return {k: 0.0 for k in keys}


def slugify(value: str) -> str:
    base = normalize_name(value).replace(" ", "-")
    return re.sub(r"-+", "-", base).strip("-") or "x"


# --- tozsamosc druzyn ---------------------------------------------------------
class TeamResolver:
    """Sprowadza rozne warianty nazwy klubu do jednego klucza."""

    def __init__(self, canonical_names: Iterable[str] = ()):
        self.canonical: dict[str, str] = {}
        for name in canonical_names:
            self.canonical[slugify(name)] = name

    def key(self, name: str) -> str:
        slug = slugify(name)
        if slug in self.canonical:
            return slug
        best, score = None, 0.0
        for key, canonical in self.canonical.items():
            sim = name_similarity(canonical, name)
            if sim > score:
                best, score = key, sim
        if best is not None and score >= 0.5:
            return best
        self.canonical[slug] = name
        return slug

    def name(self, key: str) -> str:
        return self.canonical.get(key, key)


# --- wiersze meczowe ----------------------------------------------------------
@dataclass
class TeamGame:
    """Jeden mecz z perspektywy jednej druzyny."""

    match_id: str
    date: str
    round_no: int | None
    team: str
    opponent: str
    home: bool
    points: int
    opp_points: int
    poss: float
    opp_poss: float
    stats: dict[str, float]
    opp_stats: dict[str, float]
    periods: list[int] = field(default_factory=list)
    zones: dict[str, dict[str, float]] = field(default_factory=dict)
    opp_zones: dict[str, dict[str, float]] = field(default_factory=dict)
    zones14: dict[str, dict[str, float]] = field(default_factory=dict)
    opp_zones14: dict[str, dict[str, float]] = field(default_factory=dict)
    clutch: dict[str, float] = field(default_factory=dict)
    long15: dict[str, float] = field(default_factory=dict)
    kill_shots: int = 0
    kill_allowed: int = 0

    @property
    def win(self) -> bool:
        return self.points > self.opp_points


@dataclass
class PlayerGame:
    match_id: str
    date: str
    round_no: int | None
    player: str
    team: str
    opponent: str
    home: bool
    win: bool
    started: bool
    stats: dict[str, float]
    on: dict[str, float] = field(default_factory=dict)
    off: dict[str, float] = field(default_factory=dict)
    #: koncowka meczu przy wyrownanym wyniku - box score i on/off
    clutch: dict[str, float] = field(default_factory=dict)
    #: akcje "+15" - pierwsza szansa trwajaca co najmniej 15 sekund
    long15: dict[str, float] = field(default_factory=dict)


@dataclass
class LineupGame:
    match_id: str
    date: str
    team: str
    opponent: str
    players: tuple[str, ...]
    seconds: float = 0.0
    off_poss: float = 0.0
    def_poss: float = 0.0
    points: float = 0.0
    opp_points: float = 0.0
    off: dict[str, float] = field(default_factory=lambda: _empty(["fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "tov", "ast"]))
    deff: dict[str, float] = field(default_factory=lambda: _empty(["fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "tov", "ast"]))
    clutch: dict[str, float] = field(default_factory=lambda: _empty(CLUTCH_KEYS))
    long15: dict[str, float] = field(default_factory=lambda: _empty(LONG_KEYS))


# --- glowny agregat -----------------------------------------------------------
class Season:
    """Zbiera mecze sezonu i udostepnia gotowe wycinki dla portalu."""

    def __init__(self, canonical_teams: Iterable[str] = ()):
        self.resolver = TeamResolver(canonical_teams)
        self.team_games: list[TeamGame] = []
        self.player_games: list[PlayerGame] = []
        self.lineup_games: list[LineupGame] = []
        self.pair_games: list[LineupGame] = []
        self.matchups: dict[tuple[str, tuple[str, ...], tuple[str, ...]], dict[str, float]] = {}
        self.players: dict[str, dict[str, Any]] = {}
        self.teams: dict[str, dict[str, Any]] = {}
        self.shots: list[dict[str, Any]] = []
        self.playbyplay: dict[str, dict[str, Any]] = {}
        self.games: list[dict[str, Any]] = []
        self.warnings: list[str] = []

    # -- wczytywanie ---------------------------------------------------------
    def add_game(self, game: Game, meta: Mapping[str, Any] | None = None) -> None:
        meta = dict(meta or {})
        date = meta.get("date") or game.date
        round_no = meta.get("round")
        keys = {tno: self.resolver.key(team.name) for tno, team in game.teams.items()}

        for tno, team in game.teams.items():
            info = self.teams.setdefault(keys[tno], {"key": keys[tno], "name": team.name, "logo": "", "coaches": set()})
            info["name"] = self.resolver.name(keys[tno]) or team.name
            info["fiba_name"] = team.name
            if team.logo:
                info["logo"] = team.logo
            if team.coach:
                info["coaches"].add(team.coach)
            if team.short_name:
                info["short"] = team.short_name

        possessions, tracker = split_possessions(game)
        self.warnings.extend(tracker.warnings)
        poss_count = {1: 0.0, 2: 0.0}
        for p in possessions:
            poss_count[p.offense] += 1.0
        for tno in (1, 2):
            if poss_count[tno] < 40:  # niepelne pbp - wracamy do wzoru z boxscore
                est = metrics.possessions(game.teams[tno].stats)
                poss_count[tno] = est
                self.warnings.append(
                    "mecz {}: play-by-play dalo {} posiadan druzyny {}, uzyto oszacowania".format(
                        game.match_id, int(poss_count[tno]), tno
                    )
                )

        team_clutch, team_long = _team_possession_splits(possessions)
        runs = metrics.kill_shots(game.pbp)
        zones = self._zone_totals(game)
        zones14 = self._zone_totals(game, "zone_detail")

        for tno, team in game.teams.items():
            opp_tno = game.opponent_of(tno)
            opp = game.teams[opp_tno]
            self.team_games.append(
                TeamGame(
                    match_id=game.match_id,
                    date=date,
                    round_no=round_no,
                    team=keys[tno],
                    opponent=keys[opp_tno],
                    home=(tno == 1),
                    points=team.score,
                    opp_points=opp.score,
                    poss=poss_count[tno],
                    opp_poss=poss_count[opp_tno],
                    stats={k: float(team.stats.get(k, 0) or 0) for k in COUNTING_KEYS},
                    opp_stats={k: float(opp.stats.get(k, 0) or 0) for k in COUNTING_KEYS},
                    periods=list(team.periods),
                    zones=zones.get(tno, {}),
                    opp_zones=zones.get(opp_tno, {}),
                    zones14=zones14.get(tno, {}),
                    opp_zones14=zones14.get(opp_tno, {}),
                    clutch=team_clutch.get(tno, _empty(CLUTCH_KEYS)),
                    long15=team_long.get(tno, _empty(LONG_KEYS)),
                    kill_shots=runs.get(tno, 0),
                    kill_allowed=runs.get(opp_tno, 0),
                )
            )

        self._add_players(game, keys, date, round_no, possessions, poss_count)
        self._add_lineups(game, keys, date, possessions)
        self._add_shots(game, keys, date)
        self._store_playbyplay(game, keys, date, possessions)

        self.games.append(
            {
                "match_id": game.match_id,
                "date": date,
                "round": round_no,
                "home": keys[1],
                "away": keys[2],
                "home_score": game.teams[1].score,
                "away_score": game.teams[2].score,
                "periods": {keys[1]: game.teams[1].periods, keys[2]: game.teams[2].periods},
                "attendance": game.attendance,
                "venue": meta.get("venue", ""),
                "source": game.source,
                "pzkosz_id": meta.get("pzkosz_id"),
            }
        )

    # -- skladowe ------------------------------------------------------------
    def _zone_totals(self, game: Game, attr: str = "zone") -> dict[int, dict[str, dict[str, float]]]:
        out: dict[int, dict[str, dict[str, float]]] = {1: {}, 2: {}}
        for shot in game.shots:
            key = getattr(shot, attr)
            bucket = out.setdefault(shot.tno, {}).setdefault(key, {"fga": 0.0, "fgm": 0.0, "pts": 0.0})
            bucket["fga"] += 1
            if shot.made:
                bucket["fgm"] += 1
                bucket["pts"] += 3 if shot.is_three else 2
        return out

    def _player_key(self, team_key: str, name: str, first: str = "", family: str = "") -> str:
        full = (family + " " + first).strip() or name
        return team_key + ":" + slugify(full or name)

    def _add_players(
        self,
        game: Game,
        keys: dict[int, str],
        date: str,
        round_no: int | None,
        possessions,
        poss_count: dict[int, float],
    ) -> None:
        on_court: dict[tuple[int, int], dict[str, float]] = defaultdict(
            lambda: {"off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0, "secs": 0.0}
        )
        clutch_on: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: _empty(CLUTCH_KEYS))
        clutch_box: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: _empty(CLUTCH_BOX_KEYS))
        long_on: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: _empty(LONG_KEYS))
        team_totals = {1: {"off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0}, 2: {"off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0}}

        for poss in possessions:
            off, deff = poss.offense, poss.defense
            team_totals[off]["off_poss"] += 1
            team_totals[off]["pts"] += poss.points
            team_totals[deff]["def_poss"] += 1
            team_totals[deff]["opp_pts"] += poss.points
            for pno in poss.lineups.get(off, ()):
                bucket = on_court[(off, pno)]
                bucket["off_poss"] += 1
                bucket["pts"] += poss.points
                bucket["secs"] += poss.duration
                _add_long(long_on[(off, pno)], poss)
                if poss.clutch:
                    entry = clutch_on[(off, pno)]
                    entry["off_poss"] += 1
                    entry["pts"] += poss.points
                    entry["secs"] += poss.duration
            for pno in poss.lineups.get(deff, ()):
                bucket = on_court[(deff, pno)]
                bucket["def_poss"] += 1
                bucket["opp_pts"] += poss.points
                bucket["secs"] += poss.duration
                if poss.clutch:
                    entry = clutch_on[(deff, pno)]
                    entry["def_poss"] += 1
                    entry["opp_pts"] += poss.points
                    entry["secs"] += poss.duration

            if poss.clutch:
                for ev in poss.events:
                    if ev.tno and ev.pno:
                        _add_clutch_box(clutch_box[(ev.tno, ev.pno)], ev)
            # rzuty zawodnika w akcjach "+15" licza sie tylko z pierwszej szansy
            _attribute_long_shots(long_on, poss)

        for tno, team in game.teams.items():
            team_key = keys[tno]
            opp_key = keys[game.opponent_of(tno)]
            win = team.score > game.teams[game.opponent_of(tno)].score
            for pno, player in team.players.items():
                if not player.stats.get("min") and not player.starter:
                    continue
                pkey = self._player_key(team_key, player.name, player.first_name, player.family_name)
                profile = self.players.setdefault(
                    pkey,
                    {
                        "key": pkey,
                        "team": team_key,
                        "name": (player.first_name + " " + player.family_name).strip() or player.name,
                        "short": player.name,
                        "shirt": player.shirt,
                        "position": player.position,
                        "photo": player.photo,
                    },
                )
                if player.photo:
                    profile["photo"] = player.photo
                if player.position:
                    profile["position"] = player.position

                on = dict(on_court[(tno, pno)])
                clutch = {**clutch_on[(tno, pno)], **clutch_box[(tno, pno)]}
                totals = team_totals[tno]
                off_state = {
                    "off_poss": totals["off_poss"] - on["off_poss"],
                    "def_poss": totals["def_poss"] - on["def_poss"],
                    "pts": totals["pts"] - on["pts"],
                    "opp_pts": totals["opp_pts"] - on["opp_pts"],
                }
                self.player_games.append(
                    PlayerGame(
                        match_id=game.match_id,
                        date=date,
                        round_no=round_no,
                        player=pkey,
                        team=team_key,
                        opponent=opp_key,
                        home=(tno == 1),
                        win=win,
                        started=player.starter,
                        stats={k: float(player.stats.get(k, 0) or 0) for k in PLAYER_COUNTING_KEYS},
                        on=on,
                        off=off_state,
                        clutch=clutch,
                        long15=dict(long_on[(tno, pno)]),
                    )
                )

    def _add_lineups(self, game: Game, keys: dict[int, str], date: str, possessions) -> None:
        names = {
            tno: {
                pno: self._player_key(keys[tno], pl.name, pl.first_name, pl.family_name)
                for pno, pl in team.players.items()
            }
            for tno, team in game.teams.items()
        }
        agg: dict[tuple[str, tuple[str, ...]], LineupGame] = {}
        pairs: dict[tuple[str, tuple[str, ...]], LineupGame] = {}

        for poss in possessions:
            for tno in (poss.offense, poss.defense):
                lineup = poss.lineups.get(tno, ())
                if len(lineup) != 5:
                    continue
                members = tuple(sorted(names[tno].get(p, str(p)) for p in lineup))
                row = agg.setdefault(
                    (keys[tno], members),
                    LineupGame(
                        match_id=game.match_id,
                        date=date,
                        team=keys[tno],
                        opponent=keys[game.opponent_of(tno)],
                        players=members,
                    ),
                )
                _apply_possession(row, poss, tno)
                for pair in combinations(members, 2):
                    prow = pairs.setdefault(
                        (keys[tno], pair),
                        LineupGame(
                            match_id=game.match_id,
                            date=date,
                            team=keys[tno],
                            opponent=keys[game.opponent_of(tno)],
                            players=pair,
                        ),
                    )
                    _apply_possession(prow, poss, tno)

            off_lineup = poss.lineups.get(poss.offense, ())
            def_lineup = poss.lineups.get(poss.defense, ())
            if len(off_lineup) == 5 and len(def_lineup) == 5:
                key = (
                    keys[poss.offense],
                    tuple(sorted(names[poss.offense].get(p, str(p)) for p in off_lineup)),
                    tuple(sorted(names[poss.defense].get(p, str(p)) for p in def_lineup)),
                )
                bucket = self.matchups.setdefault(key, {"poss": 0.0, "pts": 0.0, "secs": 0.0})
                bucket["poss"] += 1
                bucket["pts"] += poss.points
                bucket["secs"] += poss.duration

        self.lineup_games.extend(agg.values())
        self.pair_games.extend(pairs.values())

    def _add_shots(self, game: Game, keys: dict[int, str], date: str) -> None:
        for shot in game.shots:
            team = game.teams.get(shot.tno)
            player = team.players.get(shot.pno) if team else None
            pkey = (
                self._player_key(keys[shot.tno], player.name, player.first_name, player.family_name)
                if player
                else ""
            )
            self.shots.append(
                {
                    "match_id": game.match_id,
                    "date": date,
                    "team": keys[shot.tno],
                    "opponent": keys[game.opponent_of(shot.tno)],
                    "player": pkey,
                    "period": shot.period,
                    "made": shot.made,
                    "three": shot.is_three,
                    "type": shot.sub_type,
                    "x": shot.x,
                    "y": shot.y,
                    "dist": shot.distance,
                    "zone": shot.zone,
                    "zone14": shot.zone_detail,
                }
            )


    def _store_playbyplay(self, game: Game, keys: dict[int, str], date: str, possessions) -> None:
        """Zapisuje pelne play-by-play meczu wraz z posiadaniami i skladami.

        Portal uzywa tego do widoku przebiegu meczu i do pokazania akcji
        konkretnego zawodnika - kazde zdarzenie ma juz rozwiazany klucz gracza,
        wiec strona nie musi niczego dopasowywac po nazwisku.
        """
        names = {
            tno: {
                pno: self._player_key(keys[tno], pl.name, pl.first_name, pl.family_name)
                for pno, pl in team.players.items()
            }
            for tno, team in game.teams.items()
        }
        labels = {
            tno: {pno: pl.name for pno, pl in team.players.items()}
            for tno, team in game.teams.items()
        }
        shots_by_action = {s.action_number: s for s in game.shots}

        events = []
        for ev in game.pbp:
            team_key = keys.get(ev.tno, "") if ev.tno else ""
            shot = shots_by_action.get(ev.order)
            events.append(
                {
                    "i": ev.order,
                    "period": ev.period,
                    "gt": ev.gt,
                    "elapsed": ev.elapsed,
                    "team": team_key,
                    "player": names.get(ev.tno, {}).get(ev.pno, ""),
                    "name": labels.get(ev.tno, {}).get(ev.pno, ev.player),
                    "shirt": ev.shirt,
                    "action": ev.action,
                    "sub": ev.sub_type,
                    "made": bool(ev.success) if ev.action in ("2pt", "3pt", "freethrow") else None,
                    "s1": ev.s1,
                    "s2": ev.s2,
                    "shot": None if shot is None else {"x": shot.x, "y": shot.y, "zone": shot.zone, "zone14": shot.zone_detail},
                }
            )

        self.playbyplay[game.match_id] = {
            "match_id": game.match_id,
            "date": date,
            "home": keys.get(1, ""),
            "away": keys.get(2, ""),
            "events": events,
            "possessions": [
                {
                    "i": poss.index,
                    "period": poss.period,
                    "offense": keys.get(poss.offense, ""),
                    "defense": keys.get(poss.defense, ""),
                    "start": poss.start_elapsed,
                    "end": poss.end_elapsed,
                    "points": poss.points,
                    "from": poss.events[0].order if poss.events else None,
                    "to": poss.events[-1].order if poss.events else None,
                    "lineups": {
                        keys[tno]: [names[tno].get(p, str(p)) for p in lineup]
                        for tno, lineup in poss.lineups.items()
                        if tno in keys
                    },
                }
                for poss in possessions
            ],
        }


# --- wycinki posiadan: koncowka meczu i dlugie akcje -------------------------
def _first_chance_shots(poss):
    """Rzuty z gry oddane przed pierwsza zbiorka w ataku tego posiadania."""
    after_orb = False
    for ev in poss.events:
        if ev.action == "rebound" and ev.sub_type == "offensive" and ev.tno == poss.offense:
            after_orb = True
            continue
        if after_orb:
            continue
        if ev.action in ("2pt", "3pt") and ev.tno == poss.offense:
            yield ev


def _add_long(bucket: dict[str, float], poss) -> None:
    """Dokłada posiadanie do licznika akcji "+15"."""
    bucket["off_poss"] += 1
    if poss.long:
        bucket["off_poss_long"] += 1
        bucket["pts_long"] += poss.first_chance_pts


def _attribute_long_shots(buckets, poss) -> None:
    """Przypisuje rzuty z pierwszej szansy zawodnikom, ktorzy je oddali."""
    for ev in _first_chance_shots(poss):
        bucket = buckets[(ev.tno, ev.pno)]
        bucket["fga"] += 1
        if poss.long:
            bucket["fga_long"] += 1


def _add_clutch_box(bucket: dict[str, float], ev) -> None:
    """Box score zawodnika zbierany ze zdarzen w koncowce meczu."""
    if ev.action in ("2pt", "3pt"):
        bucket["fga"] += 1
        if ev.action == "3pt":
            bucket["tpa"] += 1
        if ev.success:
            bucket["fgm"] += 1
            bucket["pts"] += 3 if ev.action == "3pt" else 2
            if ev.action == "3pt":
                bucket["tpm"] += 1
    elif ev.action == "freethrow":
        bucket["fta"] += 1
        if ev.success:
            bucket["ftm"] += 1
            bucket["pts"] += 1
    elif ev.action == "rebound":
        bucket["trb"] += 1
        bucket["orb" if ev.sub_type == "offensive" else "drb"] += 1
    elif ev.action == "assist":
        bucket["ast"] += 1
    elif ev.action == "turnover":
        bucket["tov"] += 1
    elif ev.action == "steal":
        bucket["stl"] += 1
    elif ev.action == "block":
        bucket["blk"] += 1


def _team_possession_splits(possessions):
    """Sumy clutch i "+15" dla obu druzyn w jednym meczu."""
    clutch = {1: _empty(CLUTCH_KEYS), 2: _empty(CLUTCH_KEYS)}
    long15 = {1: _empty(LONG_KEYS), 2: _empty(LONG_KEYS)}
    for poss in possessions:
        off, deff = poss.offense, poss.defense
        if off in long15:
            _add_long(long15[off], poss)
            long15[off]["fga"] += poss.first_chance_fga
            if poss.long:
                long15[off]["fga_long"] += poss.first_chance_fga
        if not poss.clutch:
            continue
        if off in clutch:
            clutch[off]["off_poss"] += 1
            clutch[off]["pts"] += poss.points
            clutch[off]["secs"] += poss.duration
        if deff in clutch:
            clutch[deff]["def_poss"] += 1
            clutch[deff]["opp_pts"] += poss.points
    return clutch, long15


def _apply_possession(row: LineupGame, poss, tno: int) -> None:
    # piatka jest na parkiecie tak samo w ataku, jak i w obronie
    row.seconds += poss.duration
    if poss.clutch:
        row.clutch["secs"] += poss.duration
        if tno == poss.offense:
            row.clutch["off_poss"] += 1
            row.clutch["pts"] += poss.points
        else:
            row.clutch["def_poss"] += 1
            row.clutch["opp_pts"] += poss.points
    if tno == poss.offense:
        _add_long(row.long15, poss)
        row.long15["fga"] += poss.first_chance_fga
        if poss.long:
            row.long15["fga_long"] += poss.first_chance_fga
        row.off_poss += 1
        row.points += poss.points
        row.off["fga"] += poss.fga
        row.off["fgm"] += poss.fgm
        row.off["tpa"] += poss.tpa
        row.off["tpm"] += poss.tpm
        row.off["fta"] += poss.fta
        row.off["ftm"] += poss.ftm
        row.off["orb"] += poss.orb
        row.off["tov"] += poss.tov
        row.off["ast"] += poss.ast
    else:
        row.def_poss += 1
        row.opp_points += poss.points
        row.deff["fga"] += poss.fga
        row.deff["fgm"] += poss.fgm
        row.deff["tpa"] += poss.tpa
        row.deff["tpm"] += poss.tpm
        row.deff["fta"] += poss.fta
        row.deff["ftm"] += poss.ftm
        row.deff["orb"] += poss.orb
        row.deff["tov"] += poss.tov
        row.deff["ast"] += poss.ast


# --- sumowanie wierszy --------------------------------------------------------
def sum_team_games(rows: Sequence[TeamGame]) -> dict[str, Any]:
    stats = _empty()
    opp_stats = _empty()
    zones: dict[str, dict[str, float]] = {}
    opp_zones: dict[str, dict[str, float]] = {}
    zones14: dict[str, dict[str, float]] = {}
    opp_zones14: dict[str, dict[str, float]] = {}
    clutch = _empty(CLUTCH_KEYS)
    long15 = _empty(LONG_KEYS)
    total = {
        "gp": 0, "w": 0, "l": 0, "pts": 0.0, "opp_pts": 0.0,
        "poss": 0.0, "opp_poss": 0.0, "kill_shots": 0.0, "kill_allowed": 0.0,
    }
    for row in rows:
        total["gp"] += 1
        total["w"] += 1 if row.win else 0
        total["l"] += 0 if row.win else 1
        total["pts"] += row.points
        total["opp_pts"] += row.opp_points
        total["poss"] += row.poss
        total["opp_poss"] += row.opp_poss
        total["kill_shots"] += row.kill_shots
        total["kill_allowed"] += row.kill_allowed
        metrics.add(stats, row.stats)
        metrics.add(opp_stats, row.opp_stats)
        _merge_zones(zones, row.zones)
        _merge_zones(opp_zones, row.opp_zones)
        _merge_zones(zones14, row.zones14)
        _merge_zones(opp_zones14, row.opp_zones14)
        metrics.add(clutch, row.clutch)
        metrics.add(long15, row.long15)
    total["stats"] = stats
    total["opp_stats"] = opp_stats
    total["zones"] = zones
    total["opp_zones"] = opp_zones
    total["zones14"] = zones14
    total["opp_zones14"] = opp_zones14
    total["clutch"] = clutch
    total["long15"] = long15
    return total


def _merge_zones(target: dict[str, dict[str, float]], source: Mapping[str, Mapping[str, float]]) -> None:
    for zone, values in (source or {}).items():
        bucket = target.setdefault(zone, {"fga": 0.0, "fgm": 0.0, "pts": 0.0})
        for key, value in values.items():
            bucket[key] = bucket.get(key, 0.0) + float(value)


def zone_profile(
    zones: Mapping[str, Mapping[str, float]],
    names: Sequence[str] = ZONES,
) -> dict[str, dict[str, float | None]]:
    """Czestotliwosc, skutecznosc i punkty na rzut w kazdej strefie."""
    total_fga = sum(float(z.get("fga", 0)) for z in zones.values())
    out: dict[str, dict[str, float | None]] = {}
    for zone in names:
        values = zones.get(zone) or {}
        fga = float(values.get("fga", 0))
        fgm = float(values.get("fgm", 0))
        pts = float(values.get("pts", 0))
        out[zone] = {
            "fga": fga,
            "fgm": fgm,
            "freq": metrics.pct(fga, total_fga),
            "fg_pct": metrics.pct(fgm, fga),
            "pps": metrics.safe_div(pts, fga),
        }
    return out


def morey_score(zones: Mapping[str, Mapping[str, float]]) -> float | None:
    """Odsetek prob spod kosza i za 3 - im wyzej, tym lepszy dobor rzutow."""
    total = sum(float(z.get("fga", 0)) for z in zones.values())
    good = sum(float((zones.get(z) or {}).get("fga", 0)) for z in ("RIM", "CORNER_3", "ABOVE_BREAK_3"))
    return metrics.pct(good, total)
