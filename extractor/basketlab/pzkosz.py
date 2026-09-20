"""Ekstraktor play-by-play i terminarza z serwisow PZKosz (np. 1lm.pzkosz.pl).

Strona meczu renderuje play-by-play po stronie serwera jako tabele HTML
w ukladzie: [akcja gospodarzy | pkt | zegar | pkt | akcja gosci].
Nie ma tam wspolrzednych rzutow - to zrodlo zapasowe wzgledem FIBA LiveStats
(albo jedyne, gdy mecz nie byl obslugiwany przez LiveStats).
"""

from __future__ import annotations

import html as html_mod
import re
from typing import Any, Iterable

from .http import Fetcher
from .model import Event, Game, Player, Team

DEFAULT_BASE = "https://1lm.pzkosz.pl"
SCHEDULE_PATH = "/terminarz-i-wyniki.html"
MATCH_PATH = "/mecz/{match_id}/index.html"

MATCH_URL_RE = re.compile(r"/mecz/(\d+)/")

TAG_RE = re.compile(r"<[^>]+>")
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


# --- mapowanie polskich opisow akcji na model FIBA ---------------------------
#: (fragment opisu, actionType, subType, success)
ACTION_PATTERNS: list[tuple[str, str, str, int]] = [
    ("celny wsad", "2pt", "dunk", 1),
    ("niecelny wsad", "2pt", "dunk", 0),
    ("celny dobitka", "2pt", "tipinlayup", 1),
    ("niecelny dobitka", "2pt", "tipinlayup", 0),
    ("celny lay-up", "2pt", "layup", 1),
    ("niecelny lay-up", "2pt", "layup", 0),
    ("celny eurostep", "2pt", "eurostep", 1),
    ("niecelny eurostep", "2pt", "eurostep", 0),
    ("celny floater z wyskoku za 3", "3pt", "floatingjumpshot", 1),
    ("niecelny floater z wyskoku za 3", "3pt", "floatingjumpshot", 0),
    ("celny floater z wyskoku za 2", "2pt", "floatingjumpshot", 1),
    ("niecelny floater z wyskoku za 2", "2pt", "floatingjumpshot", 0),
    ("celny hakiem za 2", "2pt", "hookshot", 1),
    ("niecelny hakiem za 2", "2pt", "hookshot", 0),
    ("celny hakiem za 3", "3pt", "hookshot", 1),
    ("niecelny hakiem za 3", "3pt", "hookshot", 0),
    ("celny z odskoku za 2", "2pt", "stepbackjumpshot", 1),
    ("niecelny z odskoku za 2", "2pt", "stepbackjumpshot", 0),
    ("celny z odskoku za 3", "3pt", "stepbackjumpshot", 1),
    ("niecelny z odskoku za 3", "3pt", "stepbackjumpshot", 0),
    ("celny z odchylenia za 2", "2pt", "fadeaway", 1),
    ("niecelny z odchylenia za 2", "2pt", "fadeaway", 0),
    ("celny z odchylenia za 3", "3pt", "fadeaway", 1),
    ("niecelny z odchylenia za 3", "3pt", "fadeaway", 0),
    ("celny z wyskoku za 3", "3pt", "jumpshot", 1),
    ("niecelny z wyskoku za 3", "3pt", "jumpshot", 0),
    ("celny z wyskoku za 2", "2pt", "jumpshot", 1),
    ("niecelny z wyskoku za 2", "2pt", "jumpshot", 0),
    ("zbiorka w obronie", "rebound", "defensive", 1),
    ("zbiorka w ataku", "rebound", "offensive", 1),
    ("asysta", "assist", "", 1),
    ("przechwyt", "steal", "", 1),
    ("blok", "block", "", 1),
    ("faulowany", "foulon", "", 1),
    ("faul osobisty", "foul", "personal", 1),
    ("faul w ataku", "foul", "offensive", 1),
    ("faul niesportowy", "foul", "unsportsmanlike", 1),
    ("faul dyskwalifikujacy", "foul", "disqualifying", 1),
    ("faul techniczny trenera", "foul", "coachTechnical", 1),
    ("faul techniczny", "foul", "technical", 1),
    ("strata - blad kozlowania", "turnover", "ballhandling", 1),
    ("strata - zle podanie", "turnover", "badpass", 1),
    ("strata - poza boiskiem", "turnover", "outofbounds", 1),
    ("strata - blad krokow", "turnover", "travel", 1),
    ("strata - blad 3 sekund", "turnover", "3sec", 1),
    ("strata - blad 5 sekund", "turnover", "5sec", 1),
    ("strata - blad 8 sekund", "turnover", "8sec", 1),
    ("strata - blad 24 sekund", "turnover", "24sec", 1),
    ("strata - podwojne kozlowanie", "turnover", "doubledribble", 1),
    ("strata w ataku", "turnover", "offensive", 1),
    ("turnover.other", "turnover", "other", 1),
    ("strata", "turnover", "other", 1),
    ("zmiana - wejscie", "substitution", "in", 1),
    ("zmiana - zejscie", "substitution", "out", 1),
    ("pelna przerwa na zadanie", "timeout", "full", 1),
    ("krotka przerwa na zadanie", "timeout", "short", 1),
    ("wygrany rzut sedziowski", "jumpball", "won", 1),
    ("przegrany rzut sedziowski", "jumpball", "lost", 1),
    ("sytuacja rzutu sedziowskiego", "jumpball", "startperiod", 1),
    ("start czesci gry", "period", "start", 1),
    ("koniec czesci gry", "period", "end", 1),
    ("start meczu", "game", "start", 1),
    ("koniec meczu", "game", "end", 1),
]

FREE_THROW_RE = re.compile(r"(niecelny|celny) rzut wolny (\d)z(\d)")

_PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def _deaccent(text: str) -> str:
    return text.translate(_PL_MAP)


def _text(fragment: str) -> str:
    txt = html_mod.unescape(TAG_RE.sub(" ", fragment))
    return re.sub(r"\s+", " ", txt).strip()


def parse_match_id(url_or_id: str) -> str:
    s = str(url_or_id).strip()
    if s.isdigit():
        return s
    m = MATCH_URL_RE.search(s)
    if not m:
        raise ValueError("Nie rozpoznano identyfikatora meczu PZKosz w: " + repr(url_or_id))
    return m.group(1)


# --- terminarz ----------------------------------------------------------------
ROUND_SPLIT_RE = re.compile(r'id="kolejka-(\d+)">\s*(\d+)\s*kolejka', re.I)
EVENT_ROW_RE = re.compile(r'<tr[^>]*itemtype="[^"]*SportsEvent"[^>]*>(.*?)</tr>', re.S)
SEASON_RE = re.compile(r'href="/archiwum/(\d+)/terminarz-i-wyniki\.html">\s*([0-9]{4}/[0-9]{4})')

_ROW_URL = re.compile(r'itemprop="url" href="([^"]+)"')
_ROW_HOME = re.compile(r'itemprop="homeTeam">(.*?)</span>', re.S)
_ROW_AWAY = re.compile(r'itemprop="awayTeam">(.*?)</span>', re.S)
_ROW_DATE = re.compile(r'itemprop="startDate" content="([^"]+)"')
_ROW_VENUE = re.compile(r'itemtype="http://schema\.org/Place">\s*<meta itemprop="name" content="([^"]*)"', re.S)
_ROW_CITY = re.compile(r'itemprop="addressLocality" content="([^"]*)"')
_ROW_SCORE = re.compile(r'<td class="wynik">(.*?)</td>', re.S)
_SCORE_VALUE = re.compile(r"(\d+)\s*:\s*(\d+)")


def parse_schedule(page: str) -> list[dict[str, Any]]:
    """Parsuje strone terminarza PZKosz na liste meczow (wszystkie kolejki)."""
    games: list[dict[str, Any]] = []
    marks = list(ROUND_SPLIT_RE.finditer(page))
    for idx, mark in enumerate(marks):
        round_no = int(mark.group(2))
        chunk = page[mark.end(): marks[idx + 1].start() if idx + 1 < len(marks) else len(page)]
        for row in EVENT_ROW_RE.findall(chunk):
            url = _first(_ROW_URL, row)
            if not url:
                continue
            score = _parse_score(_first(_ROW_SCORE, row))
            iso = _first(_ROW_DATE, row)
            games.append(
                {
                    "pzkosz_id": parse_match_id(url),
                    "round": round_no,
                    "date": iso.split("T")[0] if iso else "",
                    "tipoff": iso,
                    "venue": _first(_ROW_VENUE, row),
                    "city": _first(_ROW_CITY, row),
                    "home": _text(_first(_ROW_HOME, row)),
                    "away": _text(_first(_ROW_AWAY, row)),
                    "home_score": score[0] if score else None,
                    "away_score": score[1] if score else None,
                    "finished": score is not None,
                    "url": url,
                }
            )
    return games


def _parse_score(cell: str) -> tuple[int, int] | None:
    """Komorka wyniku zawiera tez date dla widoku mobilnego - pomijamy ja."""
    if not cell:
        return None
    cleaned = re.sub(r'<div class="below-sm">.*?</div>', " ", cell, flags=re.S)
    m = _SCORE_VALUE.search(_text(cleaned))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _first(pattern: re.Pattern[str], text: str) -> str:
    m = pattern.search(text)
    return m.group(1) if m else ""


def parse_seasons(page: str) -> list[dict[str, str]]:
    """Lista archiwalnych sezonow dostepnych w serwisie."""
    return [{"archive_id": a, "season": s} for a, s in SEASON_RE.findall(page)]


def schedule_url(base: str = DEFAULT_BASE, archive_id: str | int | None = None) -> str:
    base = base.rstrip("/")
    if archive_id is None:
        return base + SCHEDULE_PATH
    return "{}/archiwum/{}{}".format(base, archive_id, SCHEDULE_PATH)


def fetch_schedule(
    fetcher: Fetcher,
    base: str = DEFAULT_BASE,
    *,
    archive_id: str | int | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    page = fetcher.get_text(schedule_url(base, archive_id), suffix=".html", force=force)
    return parse_schedule(page)


def fetch_seasons(fetcher: Fetcher, base: str = DEFAULT_BASE, *, force: bool = False) -> list[dict[str, str]]:
    page = fetcher.get_text(schedule_url(base), suffix=".html", force=force)
    return parse_seasons(page)


# --- play-by-play -------------------------------------------------------------
def _clock_to_remaining(raw: str) -> int:
    """PZKosz podaje zegar jako MM:SS:cc, odliczany w dol w kwarcie."""
    parts = [p for p in raw.strip().split(":") if p != ""]
    if not parts:
        return 0
    try:
        mm = int(parts[0])
        ss = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return 0
    return mm * 60 + ss


#: wzorce z granica slowa - inaczej "niecelny lay-up" trafilby we wzorzec
#: "celny lay-up", bo zawiera go jako podciag
_COMPILED_PATTERNS = [
    (re.compile(r"(?<![a-z0-9])" + re.escape(needle)), action, sub, success)
    for needle, action, sub, success in ACTION_PATTERNS
]


def _classify(description: str) -> tuple[str, str, int]:
    """Zwraca (actionType, subType, success) dla polskiego opisu akcji."""
    low = _deaccent(description).lower()
    ft = FREE_THROW_RE.search(low)
    if ft:
        return "freethrow", "{}of{}".format(ft.group(2), ft.group(3)), 1 if ft.group(1) == "celny" else 0
    for pattern, action, sub, success in _COMPILED_PATTERNS:
        if pattern.search(low):
            return action, sub, success
    return "unknown", description.strip(), 1


PLAYER_RE = re.compile(r"^\s*(\d+)\s*,\s*([^,]+?)\s*,\s*(.+)$")


def _split_player(cell: str) -> tuple[str, str, str]:
    """Rozdziela 'numer, Nazwisko, opis akcji'."""
    m = PLAYER_RE.match(cell)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return "", "", cell.strip()


def parse_playbyplay(page: str, match_id: str = "") -> Game:
    """Buduje obiekt meczu z tabel play-by-play strony PZKosz."""
    start = page.find('<div id="apatab0"')
    end = page.find('<div id="playbyplay-mobi"')
    block = page[start:end] if start != -1 else page[: end if end != -1 else len(page)]

    game = Game(match_id=str(match_id), source="pzkosz")
    header = re.search(
        r'<th><a href="/druzyny/[^"]*">(.*?)</a></th>.*?<th><a href="/druzyny/[^"]*">(.*?)</a></th>',
        block,
        re.S,
    )
    home_name = _text(header.group(1)) if header else ""
    away_name = _text(header.group(2)) if header else ""
    game.teams[1] = Team(tno=1, name=home_name, is_home=True)
    game.teams[2] = Team(tno=2, name=away_name, is_home=False)

    order = 0
    period = 0
    seen_players: dict[int, dict[str, Player]] = {1: {}, 2: {}}

    for table in re.findall(r"<table[^>]*class=\"statystyki pbp\"[^>]*>(.*?)</table>", block, re.S):
        head = re.search(r"<th><span>(.*?)</span></th>", table, re.S)
        label = _text(head.group(1)) if head else ""
        num = re.search(r"(\d+)", label)
        if "Kwarta" in label or "kwarta" in label:
            period = int(num.group(1)) if num else period + 1
        elif "ogrywka" in label or "OT" in label.upper():
            game.periods_max = 4
            period = 4 + (int(num.group(1)) if num else 1)
        else:
            period = period or 1

        for row in TR_RE.findall(table):
            tds = TD_RE.findall(row)
            if len(tds) != 5:
                continue
            home_cell, home_pts, clock_cell, away_pts, away_cell = (_text(td) for td in tds)
            remaining = _clock_to_remaining(clock_cell)
            # zdarzenia meczowe (start/koniec kwarty) PZKosz wpisuje w obu
            # kolumnach - zapisujemy je raz, bez przypisania do druzyny
            cells = ((1, home_cell), (2, away_cell))
            if home_cell and home_cell == away_cell:
                cells = ((1, home_cell),)
            for tno, cell in cells:
                if not cell:
                    continue
                shirt, player_name, description = _split_player(cell)
                action, sub, success = _classify(description)
                pno = _register_player(game, seen_players, tno, shirt, player_name)
                game.pbp.append(
                    Event(
                        order=order,
                        period=period,
                        period_type="REGULAR" if period <= 4 else "OVERTIME",
                        gt="{:02d}:{:02d}".format(remaining // 60, remaining % 60),
                        remaining=remaining,
                        elapsed=_elapsed(period, remaining),
                        tno=tno if action not in ("game", "period") else 0,
                        pno=pno,
                        player=player_name,
                        shirt=shirt,
                        action=action,
                        sub_type=sub,
                        success=success,
                        scoring=1 if action in ("2pt", "3pt", "freethrow") and success else 0,
                        s1=int(home_pts) if home_pts.isdigit() else 0,
                        s2=int(away_pts) if away_pts.isdigit() else 0,
                    )
                )
                order += 1

    _carry_scores(game.pbp)
    if game.pbp:
        game.teams[1].score = game.pbp[-1].s1
        game.teams[2].score = game.pbp[-1].s2
    game.warnings.append("zrodlo PZKosz: brak wspolrzednych rzutow i brak boxscore")
    return game


def _elapsed(period: int, remaining: int) -> int:
    before = 0
    for p in range(1, max(period, 1)):
        before += 600 if p <= 4 else 300
    length = 600 if period <= 4 else 300
    return before + (length - remaining)


def _register_player(game: Game, seen: dict[int, dict[str, Player]], tno: int, shirt: str, name: str) -> int:
    if not shirt and not name:
        return 0
    key = shirt or name
    bucket = seen[tno]
    if key not in bucket:
        pno = len(bucket) + 1
        player = Player(pno=pno, tno=tno, name=name, shirt=shirt)
        bucket[key] = player
        game.teams[tno].players[pno] = player
    return bucket[key].pno


def _carry_scores(events: Iterable[Event]) -> None:
    """PZKosz wpisuje wynik tylko przy akcji punktujacej - uzupelniamy reszte."""
    s1 = s2 = 0
    for ev in events:
        if ev.s1:
            s1 = ev.s1
        if ev.s2:
            s2 = ev.s2
        ev.s1, ev.s2 = s1, s2


def load_playbyplay(url_or_id: str, fetcher: Fetcher, *, base: str = DEFAULT_BASE, force: bool = False) -> Game:
    s = str(url_or_id).strip()
    if s.startswith("http"):
        url, match_id = s, parse_match_id(s)
    else:
        match_id = parse_match_id(s)
        url = base.rstrip("/") + MATCH_PATH.format(match_id=match_id)
    page = fetcher.get_text(url, suffix=".html", force=force)
    return parse_playbyplay(page, match_id)
