"""Ekstraktor danych z FIBA LiveStats (Genius Sports).

Publiczny endpoint meczu:
    https://fibalivestats.dcd.shared.geniussports.com/data/<matchId>/data.json

Zawiera boxscore, pelne play-by-play oraz wspolrzedne wszystkich rzutow z gry,
czyli wszystko, czego potrzebujemy do map rzutow i analizy piatek.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import court
from .http import Fetcher
from .model import Event, Game, Player, Shot, Team

BASE = "https://fibalivestats.dcd.shared.geniussports.com"
DATA_URL = BASE + "/data/{match_id}/data.json"
PAGE_URL = BASE + "/u/{org}/{match_id}/index.html"

MATCH_ID_RE = re.compile(r"/(?:u/[A-Za-z]+/|data/)(\d{4,})(?:/|$)")

#: akcje pbp traktowane jako rzut z gry
SHOT_ACTIONS = {"2pt", "3pt"}

TEAM_STAT_MAP = {
    "sMinutes": "min",
    "sFieldGoalsMade": "fgm",
    "sFieldGoalsAttempted": "fga",
    "sThreePointersMade": "tpm",
    "sThreePointersAttempted": "tpa",
    "sTwoPointersMade": "twom",
    "sTwoPointersAttempted": "twoa",
    "sFreeThrowsMade": "ftm",
    "sFreeThrowsAttempted": "fta",
    "sReboundsDefensive": "drb",
    "sReboundsOffensive": "orb",
    "sReboundsTotal": "trb",
    "sAssists": "ast",
    "sTurnovers": "tov",
    "sSteals": "stl",
    "sBlocks": "blk",
    "sBlocksReceived": "blkr",
    "sFoulsPersonal": "pf",
    "sFoulsOn": "fd",
    "sPoints": "pts",
    "sPointsFromTurnovers": "pts_off_tov",
    "sPointsSecondChance": "pts_2nd",
    "sPointsFastBreak": "pts_fb",
    "sBenchPoints": "pts_bench",
    "sPointsInThePaint": "pts_paint",
    "sPlusMinusPoints": "plus_minus",
    "sBiggestLead": "biggest_lead",
    "sBiggestScoringRun": "biggest_run",
    "sLeadChanges": "lead_changes",
    "sTimesScoresLevel": "times_tied",
    "sReboundsTeam": "team_reb",
    "sReboundsTeamDefensive": "team_drb",
    "sReboundsTeamOffensive": "team_orb",
    "sTurnoversTeam": "team_tov",
}


def parse_match_id(url_or_id: str) -> str:
    """Wyciaga numer meczu z URL-a FIBA LiveStats albo zwraca podany numer."""
    s = str(url_or_id).strip()
    if s.isdigit():
        return s
    m = MATCH_ID_RE.search(s)
    if not m:
        raise ValueError("Nie rozpoznano identyfikatora meczu w: " + repr(url_or_id))
    return m.group(1)


def fetch_raw(match_id: str, fetcher: Fetcher, *, force: bool = False) -> dict[str, Any]:
    return fetcher.get_json(DATA_URL.format(match_id=match_id), force=force)


def _clock_seconds(gt: str) -> int:
    try:
        parts = str(gt).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return 0


def _period_length(period: int, raw: dict[str, Any]) -> int:
    reg = int(raw.get("periodLengthREGULAR") or 10)
    ot = int(raw.get("periodLengthOVERTIME") or 5)
    periods_max = int(raw.get("periodsMax") or 4)
    return reg if period <= periods_max else ot


def _elapsed(period: int, remaining: int, raw: dict[str, Any]) -> int:
    reg = int(raw.get("periodLengthREGULAR") or 10) * 60
    ot = int(raw.get("periodLengthOVERTIME") or 5) * 60
    periods_max = int(raw.get("periodsMax") or 4)
    before = 0
    for p in range(1, max(period, 1)):
        before += reg if p <= periods_max else ot
    return before + (_period_length(period, raw) * 60 - remaining)


def _minutes_to_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value or "").strip()
    if not s:
        return 0.0
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60.0
        return float(s)
    except ValueError:
        return 0.0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_team(tno: int, raw_team: dict[str, Any], raw: dict[str, Any]) -> Team:
    stats: dict[str, Any] = {}
    for src, dst in TEAM_STAT_MAP.items():
        key = "tot_" + src
        if key in raw_team:
            stats[dst] = raw_team[key]
    stats["min"] = _minutes_to_float(stats.get("min", 0))

    periods: list[int] = []
    periods_max = int(raw.get("periodsMax") or 4)
    for p in range(1, periods_max + 6):
        key = "p{}_score".format(p)
        if key in raw_team and raw_team[key] not in (None, ""):
            periods.append(int(raw_team[key]))
        elif p <= periods_max:
            periods.append(0)

    logo = ""
    logo_s = raw_team.get("logoS")
    if isinstance(logo_s, dict):
        logo = logo_s.get("url", "") or ""
    if not logo:
        logo = raw_team.get("logo") or ""

    team = Team(
        tno=tno,
        name=(raw_team.get("name") or "").strip(),
        short_name=(raw_team.get("shortName") or "").strip(),
        code=(raw_team.get("code") or "").strip(),
        logo=logo,
        coach=(raw_team.get("coach") or "").strip(),
        is_home=(tno == 1),
        score=int(raw_team.get("score") or 0),
        periods=periods,
        stats=stats,
    )

    for pno_s, rp in (raw_team.get("pl") or {}).items():
        try:
            pno = int(pno_s)
        except ValueError:
            continue
        pstats = {dst: rp[src] for src, dst in TEAM_STAT_MAP.items() if src in rp}
        pstats["min"] = _minutes_to_float(rp.get("sMinutes", "0:00"))
        team.players[pno] = Player(
            pno=pno,
            tno=tno,
            name=(rp.get("name") or rp.get("scoreboardName") or "").strip(),
            first_name=(rp.get("firstName") or "").strip(),
            family_name=(rp.get("familyName") or "").strip(),
            shirt=str(rp.get("shirtNumber") or "").strip(),
            position=(rp.get("playingPosition") or "").strip(),
            starter=bool(rp.get("starter")),
            active=bool(rp.get("active", 1)),
            photo=(rp.get("photoS") or rp.get("photoT") or "").strip(),
            stats=pstats,
        )
    return team


def _build_events(raw: dict[str, Any]) -> list[Event]:
    events: list[Event] = []
    for e in raw.get("pbp") or []:
        period = int(e.get("period") or 0)
        remaining = _clock_seconds(e.get("gt") or "00:00")
        events.append(
            Event(
                order=int(e.get("actionNumber") or 0),
                period=period,
                period_type=e.get("periodType") or "REGULAR",
                gt=e.get("gt") or "",
                remaining=remaining,
                elapsed=_elapsed(period, remaining, raw),
                tno=int(e.get("tno") or 0),
                pno=int(e.get("pno") or 0),
                player=(e.get("player") or "").strip(),
                shirt=str(e.get("shirtNumber") or "").strip(),
                action=e.get("actionType") or "",
                sub_type=e.get("subType") or "",
                success=int(e.get("success") or 0),
                scoring=int(e.get("scoring") or 0),
                s1=int(e.get("s1") or 0),
                s2=int(e.get("s2") or 0),
                qualifiers=list(e.get("qualifier") or []),
            )
        )
    # data.json podaje pbp od konca meczu - porzadkujemy chronologicznie
    events.sort(key=lambda ev: ev.order)
    for i, ev in enumerate(events):
        ev.order = i
    return events


def _build_shots(raw: dict[str, Any]) -> list[Shot]:
    shots: list[Shot] = []
    for tno_s, raw_team in (raw.get("tm") or {}).items():
        try:
            tno = int(tno_s)
        except ValueError:
            continue
        for s in raw_team.get("shot") or []:
            if s.get("x") is None or s.get("y") is None:
                continue
            is_three = s.get("actionType") == "3pt"
            loc = court.normalize(float(s["x"]), float(s["y"]))
            shots.append(
                Shot(
                    tno=tno,
                    pno=int(s.get("pno") or 0),
                    player=(s.get("player") or "").strip(),
                    period=int(s.get("per") or 0),
                    made=bool(s.get("r")),
                    is_three=is_three,
                    sub_type=s.get("subType") or "",
                    action_number=int(s.get("actionNumber") or 0),
                    x=loc.half_x,
                    y=loc.half_y,
                    distance=loc.distance,
                    angle=loc.angle,
                    zone=court.classify(loc, is_three),
                    zone_detail=court.classify_detailed(loc, is_three),
                )
            )
    shots.sort(key=lambda s: (s.period, s.action_number))
    return shots


def parse(raw: dict[str, Any], match_id: str) -> Game:
    """Zamienia surowy data.json na znormalizowany obiekt meczu."""
    game = Game(
        match_id=str(match_id),
        source="fiba",
        periods_max=int(raw.get("periodsMax") or 4),
        period_length=int(raw.get("periodLengthREGULAR") or 10),
        ot_length=int(raw.get("periodLengthOVERTIME") or 5),
        attendance=_int_or_none(raw.get("attendance")),
    )
    for tno_s in ("1", "2"):
        if tno_s in (raw.get("tm") or {}):
            game.teams[int(tno_s)] = _build_team(int(tno_s), raw["tm"][tno_s], raw)
    game.pbp = _build_events(raw)
    game.shots = _build_shots(raw)

    if not game.shots:
        game.warnings.append("brak wspolrzednych rzutow w data.json")
    if len(game.teams) != 2:
        game.warnings.append("mecz nie ma dwoch druzyn")
    return game


def load(match_id: str, fetcher: Fetcher, *, force: bool = False) -> Game:
    mid = parse_match_id(match_id)
    return parse(fetch_raw(mid, fetcher, force=force), mid)


def save_raw(match_id: str, fetcher: Fetcher, dest: Path, *, force: bool = False) -> Path:
    raw = fetch_raw(parse_match_id(match_id), fetcher, force=force)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return dest
