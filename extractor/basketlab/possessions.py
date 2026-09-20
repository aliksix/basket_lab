"""Rekonstrukcja posiadan i skladow na parkiecie z play-by-play.

Posiadanie definiujemy jako maksymalny ciag zdarzen, w ktorych pilke ma ta sama
druzyna. Zbiorka w ataku nie konczy posiadania (zgodnie z klasyczna definicja
``Poss = FGA - ORB + TOV + 0.44 * FTA``), rzuty wolne po faulu przy celnym
rzucie naleza do tego samego posiadania.

Sklady odtwarzamy ze zdarzen ``substitution`` - protokol FIBA notuje kazde
wejscie i zejscie z numerem zawodnika, wiec da sie wskazac piatke dla dowolnej
sekundy meczu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .model import Event, Game

#: zdarzenia jednoznacznie wskazujace druzyne bedaca w posiadaniu pilki
BALL_TO_EVENT_TEAM = {"2pt", "3pt", "freethrow", "turnover", "assist", "steal"}
#: zdarzenia, przy ktorych pilke ma przeciwnik zawodnika wykonujacego akcje
BALL_TO_OPPONENT = {"block"}

SHOT_ACTIONS = {"2pt", "3pt"}

#: clutch time - ostatnie 5 minut czwartej kwarty i cala dogrywka,
#: przy roznicy punktowej nie wiekszej niz 5
CLUTCH_PERIOD = 4
CLUTCH_SECONDS = 300
CLUTCH_MARGIN = 5

#: prog "dlugiej akcji" - pierwsza szansa trwajaca co najmniej tyle sekund
LONG_POSSESSION_SECONDS = 15


@dataclass
class Possession:
    index: int
    period: int
    offense: int
    defense: int
    start_elapsed: int
    end_elapsed: int
    #: sekundy do konca kwarty w chwili rozpoczecia posiadania
    start_remaining: int = 0
    #: wynik przed rozpoczeciem posiadania (gospodarze, goscie)
    start_score: tuple[int, int] = (0, 0)
    points: int = 0
    fga: int = 0
    fgm: int = 0
    tpa: int = 0
    tpm: int = 0
    fta: int = 0
    ftm: int = 0
    orb: int = 0
    drb: int = 0
    tov: int = 0
    ast: int = 0
    #: rzuty i punkty z pierwszej szansy, czyli przed pierwsza zbiorka w ataku
    first_chance_fga: int = 0
    first_chance_pts: int = 0
    #: moment zamkniecia pierwszej szansy (rzut albo strata); None, gdy nie bylo
    first_chance_elapsed: int | None = None
    lineups: dict[int, tuple[int, ...]] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    @property
    def duration(self) -> int:
        return max(self.end_elapsed - self.start_elapsed, 0)

    @property
    def clutch(self) -> bool:
        """Koncowka meczu przy wyniku w zasiegu jednego posiadania z okladem."""
        if self.period < CLUTCH_PERIOD or self.start_remaining > CLUTCH_SECONDS:
            return False
        return abs(self.start_score[0] - self.start_score[1]) <= CLUTCH_MARGIN

    @property
    def first_chance_seconds(self) -> int:
        """Ile sekund druzyna zuzyla, zanim zamknela pierwsza szanse."""
        end = self.first_chance_elapsed if self.first_chance_elapsed is not None else self.end_elapsed
        return max(end - self.start_elapsed, 0)

    @property
    def long(self) -> bool:
        """Akcja "+15": pierwsza szansa trwala co najmniej 15 sekund."""
        return self.first_chance_seconds >= LONG_POSSESSION_SECONDS


@dataclass
class Stint:
    """Odcinek meczu o niezmiennych skladach obu druzyn."""

    period: int
    start_elapsed: int
    end_elapsed: int
    lineups: dict[int, tuple[int, ...]]
    possessions: list[Possession] = field(default_factory=list)

    @property
    def seconds(self) -> int:
        return max(self.end_elapsed - self.start_elapsed, 0)


class LineupTracker:
    """Odtwarza sklad na parkiecie w kazdym momencie meczu."""

    def __init__(self, game: Game):
        self.game = game
        self.on_court: dict[int, set[int]] = {}
        self.warnings: list[str] = []
        for tno, team in game.teams.items():
            self.on_court[tno] = {p.pno for p in team.players.values() if p.starter}
            if len(self.on_court[tno]) != 5:
                self.warnings.append(
                    "mecz {}: druzyna {} ma {} zawodnikow w pierwszej piatce".format(
                        game.match_id, tno, len(self.on_court[tno])
                    )
                )

    def apply(self, ev: Event) -> None:
        if ev.action != "substitution" or not ev.pno or ev.tno not in self.on_court:
            return
        squad = self.on_court[ev.tno]
        if ev.sub_type == "in":
            squad.add(ev.pno)
        elif ev.sub_type == "out":
            squad.discard(ev.pno)

    def snapshot(self) -> dict[int, tuple[int, ...]]:
        return {tno: tuple(sorted(pnos)) for tno, pnos in self.on_court.items()}

    def valid(self) -> bool:
        return all(len(s) == 5 for s in self.on_court.values())


def _ball_team(ev: Event, opponent_of) -> int | None:
    """Ktora druzyna ma pilke w chwili zdarzenia (None = nie wiadomo)."""
    if not ev.tno:
        return None
    if ev.action in BALL_TO_EVENT_TEAM:
        return ev.tno
    if ev.action in BALL_TO_OPPONENT:
        return opponent_of(ev.tno)
    if ev.action == "rebound":
        return ev.tno  # zbiorka w ataku i w obronie daje pilke druzynie zbierajacej
    return None


def split_possessions(game: Game) -> tuple[list[Possession], LineupTracker]:
    """Dzieli mecz na posiadania wraz ze skladami obu druzyn."""
    tracker = LineupTracker(game)
    possessions: list[Possession] = []
    current: Possession | None = None
    period = 0
    score = (0, 0)

    for ev in game.pbp:
        if ev.action == "substitution":
            tracker.apply(ev)
            continue
        if ev.action == "period" and ev.sub_type == "start":
            period = ev.period
            current = None
            continue
        if ev.action in ("period", "game") and ev.sub_type == "end":
            current = None
            continue

        team = _ball_team(ev, game.opponent_of)
        if team is None:
            if current is not None:
                current.events.append(ev)
            continue

        if current is None or current.offense != team or ev.period != current.period:
            current = Possession(
                index=len(possessions),
                period=ev.period or period,
                offense=team,
                defense=game.opponent_of(team),
                start_elapsed=ev.elapsed,
                end_elapsed=ev.elapsed,
                start_remaining=ev.remaining,
                start_score=score,
                lineups=tracker.snapshot(),
            )
            possessions.append(current)

        current.end_elapsed = ev.elapsed
        current.events.append(ev)
        _accumulate(current, ev)
        score = (ev.s1, ev.s2)

    _tile_durations(possessions)
    return possessions, tracker


def _tile_durations(possessions: list[Possession]) -> None:
    """Skleja posiadania w czasie.

    Zdarzenia oznaczaja tylko momenty, w ktorych cos sie stalo, wiec roznica
    miedzy pierwszym a ostatnim zdarzeniem posiadania nie obejmuje przerwy po
    poprzedniej akcji. Zeby minuty piatek sumowaly sie do czasu meczu,
    posiadanie zaczyna sie tam, gdzie skonczylo sie poprzednie.
    """
    previous: Possession | None = None
    for poss in possessions:
        if previous is not None and previous.period == poss.period:
            poss.start_elapsed = min(poss.start_elapsed, previous.end_elapsed)
        previous = poss


def _accumulate(poss: Possession, ev: Event) -> None:
    own = ev.tno == poss.offense
    # "pierwsza szansa" konczy sie z chwila zbiorki w ataku - wszystko, co
    # dzieje sie pozniej, to dogrywanie akcji po wlasnym niecelnym rzucie
    first_chance = poss.orb == 0

    if ev.action in SHOT_ACTIONS:
        if own:
            poss.fga += 1
            if ev.action == "3pt":
                poss.tpa += 1
            if ev.success:
                poss.fgm += 1
                poss.points += 3 if ev.action == "3pt" else 2
                if ev.action == "3pt":
                    poss.tpm += 1
            if first_chance:
                poss.first_chance_fga += 1
                if ev.success:
                    poss.first_chance_pts += 3 if ev.action == "3pt" else 2
                if poss.first_chance_elapsed is None:
                    poss.first_chance_elapsed = ev.elapsed
    elif ev.action == "freethrow":
        if own:
            poss.fta += 1
            if ev.success:
                poss.ftm += 1
                poss.points += 1
                if first_chance:
                    poss.first_chance_pts += 1
    elif ev.action == "rebound":
        if own and ev.sub_type == "offensive":
            poss.orb += 1
        elif not own and ev.sub_type == "defensive":
            poss.drb += 1
    elif ev.action == "turnover" and own:
        poss.tov += 1
        if first_chance and poss.first_chance_elapsed is None:
            poss.first_chance_elapsed = ev.elapsed
    elif ev.action == "assist" and own:
        poss.ast += 1


def build_stints(possessions: Iterable[Possession]) -> list[Stint]:
    """Skleja kolejne posiadania o identycznych skladach w odcinki gry."""
    stints: list[Stint] = []
    for poss in possessions:
        key = (poss.period, poss.lineups.get(1), poss.lineups.get(2))
        if stints:
            last = stints[-1]
            if (last.period, last.lineups.get(1), last.lineups.get(2)) == key:
                last.end_elapsed = poss.end_elapsed
                last.possessions.append(poss)
                continue
        stints.append(
            Stint(
                period=poss.period,
                start_elapsed=poss.start_elapsed,
                end_elapsed=poss.end_elapsed,
                lineups=dict(poss.lineups),
                possessions=[poss],
            )
        )
    return stints


def estimated_possessions(stats: dict[str, Any], opp: dict[str, Any] | None = None) -> float:
    """Klasyczne oszacowanie liczby posiadan z boxscore."""
    own = (
        float(stats.get("fga", 0))
        - float(stats.get("orb", 0))
        + float(stats.get("tov", 0))
        + 0.44 * float(stats.get("fta", 0))
    )
    if opp is None:
        return own
    other = (
        float(opp.get("fga", 0))
        - float(opp.get("orb", 0))
        + float(opp.get("tov", 0))
        + 0.44 * float(opp.get("fta", 0))
    )
    return (own + other) / 2.0
