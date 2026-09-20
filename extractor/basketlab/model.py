"""Znormalizowany model meczu wspolny dla wszystkich zrodel danych."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Player:
    pno: int
    tno: int
    name: str
    first_name: str = ""
    family_name: str = ""
    shirt: str = ""
    position: str = ""
    starter: bool = False
    active: bool = True
    photo: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class Team:
    tno: int
    name: str
    short_name: str = ""
    code: str = ""
    logo: str = ""
    coach: str = ""
    is_home: bool = False
    score: int = 0
    periods: list[int] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    players: dict[int, Player] = field(default_factory=dict)


@dataclass
class Event:
    """Pojedyncze zdarzenie play-by-play w jednolitej postaci."""

    order: int
    period: int
    period_type: str
    gt: str                 # czas pozostaly w kwarcie "MM:SS"
    remaining: int          # sekundy pozostale w kwarcie
    elapsed: int            # sekundy od poczatku meczu
    tno: int                # 0 = zdarzenie meczowe (start/koniec)
    pno: int                # 0 = zdarzenie druzynowe
    player: str
    shirt: str
    action: str             # 2pt, 3pt, freethrow, rebound, turnover, ...
    sub_type: str
    success: int
    scoring: int
    s1: int
    s2: int
    qualifiers: list[str] = field(default_factory=list)


@dataclass
class Shot:
    tno: int
    pno: int
    player: str
    period: int
    made: bool
    is_three: bool
    sub_type: str
    action_number: int
    x: float                # znormalizowane 0-100 na polowie boiska
    y: float
    distance: float
    angle: float
    zone: str
    zone_detail: str = ""


@dataclass
class Game:
    match_id: str
    source: str
    competition: str = ""
    season: str = ""
    date: str = ""
    round_no: int | None = None
    venue: str = ""
    attendance: int | None = None
    periods_max: int = 4
    period_length: int = 10
    ot_length: int = 5
    teams: dict[int, Team] = field(default_factory=dict)
    pbp: list[Event] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def home(self) -> Team:
        return self.teams[1]

    @property
    def away(self) -> Team:
        return self.teams[2]

    def opponent_of(self, tno: int) -> int:
        return 2 if tno == 1 else 1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["teams"] = {
            str(tno): {
                **{k: v for k, v in asdict(t).items() if k != "players"},
                "players": {str(p): asdict(pl) for p, pl in t.players.items()},
            }
            for tno, t in self.teams.items()
        }
        return d
