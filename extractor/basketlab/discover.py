"""Wyszukiwanie identyfikatorow meczow w FIBA LiveStats.

Genius Sports nie udostepnia publicznego indeksu rozgrywek - ``data.json``
pojawia sie dopiero dla rozegranego meczu, a identyfikatory sa nadawane
globalnie, rosnaco w czasie. Dlatego mapowanie "mecz z terminarza PZKosz ->
identyfikator LiveStats" budujemy raz i zapisujemy w rejestrze:

1. ``scan``   - rzadki skan zadanego zakresu, zeby znalezc pierwsze kotwice,
2. ``expand`` - gesty skan wokol kazdej kotwicy (mecze jednej kolejki leza obok
   siebie),
3. ``predict``- interpolacja data -> identyfikator na podstawie juz
   dopasowanych meczow i skan waskiego okna wokol przewidywanej wartosci.

Kroki 2-3 powtarzamy, dopoki przybywa dopasowan. Rejestr jest wznawialny -
kolejne uruchomienie dopina tylko brakujace mecze.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from .fiba import DATA_URL
from .http import USER_AGENT

_PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

#: czlony nazw, ktore nie identyfikuja klubu (sponsorzy, formy prawne)
STOPWORDS = {
    "ks", "kks", "mks", "uks", "sks", "gks", "bks", "azs", "klub", "sportowy",
    "koszykowki", "koszykowka", "sa", "sp", "zoo", "team", "basket", "basketball",
}


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(name).translate(_PL_MAP).lower()).strip()


def name_tokens(name: str) -> set[str]:
    return {t for t in normalize_name(name).split() if len(t) >= 3 and t not in STOPWORDS}


def name_similarity(a: str, b: str) -> float:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


@dataclass
class Candidate:
    """Skrocony podglad meczu z LiveStats uzywany przy dopasowywaniu.

    Czytamy tylko poczatek ``data.json`` - nazwa i wynik gospodarzy sa tam
    w pierwszym kilobajcie, a dane gosci dopiero za cala kadra gospodarzy
    (ok. 60 kB dalej). Przy skanie dziesiatek tysiecy identyfikatorow ta
    roznica decyduje o czasie i transferze, a para (gospodarz, wynik)
    wystarcza do dopasowania; pelna weryfikacja nastepuje przy pobraniu meczu.
    """

    fiba_id: int
    home: str
    home_score: int


@dataclass
class Registry:
    """Trwale mapowanie mecz PZKosz <-> mecz FIBA LiveStats."""

    season: str = ""
    competition: str = ""
    matches: list[dict[str, Any]] = field(default_factory=list)
    checked: list[list[int]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Registry":
        if Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(
                season=data.get("season", ""),
                competition=data.get("competition", ""),
                matches=data.get("matches", []),
                checked=data.get("checked", []),
            )
        return cls()

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(
                {
                    "season": self.season,
                    "competition": self.competition,
                    "matches": sorted(self.matches, key=lambda m: (m.get("date") or "", m.get("pzkosz_id") or "")),
                    "checked": _merge_ranges(self.checked),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @property
    def resolved(self) -> dict[str, int]:
        return {m["pzkosz_id"]: int(m["fiba_id"]) for m in self.matches if m.get("fiba_id")}

    def anchors(self) -> list[tuple[str, int]]:
        pairs = [(m["date"], int(m["fiba_id"])) for m in self.matches if m.get("fiba_id") and m.get("date")]
        return sorted(set(pairs))

    def was_checked(self, mid: int) -> bool:
        for lo, hi in self.checked:
            if lo <= mid <= hi:
                return True
        return False

    def mark_checked(self, lo: int, hi: int) -> None:
        self.checked.append([lo, hi])
        self.checked = _merge_ranges(self.checked)


def _merge_ranges(ranges: Iterable[Iterable[int]]) -> list[list[int]]:
    items = sorted([int(a), int(b)] for a, b in ranges)
    merged: list[list[int]] = []
    for lo, hi in items:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


# --- pobieranie podgladu ------------------------------------------------------
_NAME_RE = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SCORE_RE = re.compile(r'"score"\s*:\s*(\d+)')


#: ile bajtow poczatku data.json wystarcza na nazwe i wynik gospodarzy
PEEK_BYTES = 6000


def peek(fiba_id: int, timeout: int = 20) -> Candidate | None:
    """Pobiera poczatek ``data.json`` i wyciaga nazwe oraz wynik gospodarzy."""
    req = urllib.request.Request(
        DATA_URL.format(match_id=fiba_id), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            head = resp.read(PEEK_BYTES).decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None
    name = _NAME_RE.search(head)
    score = _SCORE_RE.search(head)
    if not name or not score:
        return None
    return Candidate(fiba_id=fiba_id, home=_unescape(name.group(1)), home_score=int(score.group(1)))


def _unescape(value: str) -> str:
    return json.loads('"' + value + '"') if "\\" in value else value


@dataclass
class Confirmation:
    """Pelne dane naglowkowe meczu, sluzace do potwierdzenia dopasowania."""

    fiba_id: int
    home: str
    away: str
    home_score: int
    away_score: int


def confirm(fiba_id: int, timeout: int = 30) -> Confirmation | None:
    """Pobiera caly ``data.json`` i odczytuje obie druzyny wraz z wynikiem.

    ``peek`` czyta tylko gospodarzy, wiec potrafi wskazac inny mecz o tym samym
    wyniku gospodarzy. To wywolanie rozstrzyga takie przypadki - robimy je
    wylacznie dla kandydatow, ktorych ``peek`` juz wstepnie dopasowal.
    """
    req = urllib.request.Request(
        DATA_URL.format(match_id=fiba_id), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    teams = data.get("tm") or {}
    if "1" not in teams or "2" not in teams:
        return None
    return Confirmation(
        fiba_id=fiba_id,
        home=(teams["1"].get("name") or "").strip(),
        away=(teams["2"].get("name") or "").strip(),
        home_score=int(teams["1"].get("score") or 0),
        away_score=int(teams["2"].get("score") or 0),
    )


# --- dopasowanie --------------------------------------------------------------
class ScheduleIndex:
    """Indeks meczow z terminarza, po wyniku i nazwach druzyn."""

    def __init__(self, schedule: list[dict[str, Any]]):
        self.by_score: dict[int, list[dict[str, Any]]] = {}
        self.entries = [g for g in schedule if g.get("finished")]
        for g in self.entries:
            self.by_score.setdefault(g["home_score"], []).append(g)

    def match(self, cand: Candidate, min_similarity: float = 0.5) -> dict[str, Any] | None:
        best, best_score = None, 0.0
        for g in self.by_score.get(cand.home_score, []):
            sim = name_similarity(g["home"], cand.home)
            if sim > best_score:
                best, best_score = g, sim
        return best if best_score >= min_similarity else None


# --- skanowanie ---------------------------------------------------------------
def scan_ids(
    ids: Iterable[int],
    index: ScheduleIndex,
    registry: Registry,
    *,
    workers: int = 8,
    on_hit: Callable[[dict[str, Any], Candidate], None] | None = None,
) -> int:
    """Sprawdza podane identyfikatory i dopisuje trafienia do rejestru."""
    resolved = registry.resolved
    taken = set(resolved.values())
    todo = [i for i in ids if i not in taken]
    if not todo:
        return 0

    found = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for cand in pool.map(peek, todo):
            if cand is None:
                continue
            entry = index.match(cand)
            if entry is None or entry["pzkosz_id"] in resolved:
                continue
            full = confirm(cand.fiba_id)
            if full is None or full.away_score != entry.get("away_score"):
                continue
            if name_similarity(entry["away"], full.away) < 0.34:
                continue
            record = dict(entry)
            record["fiba_id"] = cand.fiba_id
            record["fiba_home"] = full.home
            record["fiba_away"] = full.away
            registry.matches.append(record)
            resolved[entry["pzkosz_id"]] = cand.fiba_id
            found += 1
            if on_hit:
                on_hit(record, cand)
    return found


def _unchecked(registry: Registry, lo: int, hi: int, step: int = 1) -> list[int]:
    return [i for i in range(lo, hi + 1, step) if not registry.was_checked(i)]


def interpolate(anchors: list[tuple[str, int]], target: str) -> int | None:
    """Szacuje identyfikator dla daty na podstawie znanych par (data, id)."""
    if not anchors:
        return None
    days = [(_to_ordinal(d), i) for d, i in anchors if _to_ordinal(d)]
    if not days:
        return None
    days.sort()
    t = _to_ordinal(target)
    if t is None:
        return None
    xs = [d for d, _ in days]
    ys = [i for _, i in days]
    if t <= xs[0]:
        return _extrapolate(xs, ys, t, forward=False)
    if t >= xs[-1]:
        return _extrapolate(xs, ys, t, forward=True)
    k = bisect_left(xs, t)
    x0, x1 = xs[k - 1], xs[k]
    y0, y1 = ys[k - 1], ys[k]
    if x1 == x0:
        return y0
    return int(y0 + (y1 - y0) * (t - x0) / (x1 - x0))


def _extrapolate(xs: list[int], ys: list[int], t: int, *, forward: bool) -> int:
    if len(xs) < 2:
        return ys[0]
    if forward:
        x0, x1, y0, y1 = xs[-2], xs[-1], ys[-2], ys[-1]
    else:
        x0, x1, y0, y1 = xs[0], xs[1], ys[0], ys[1]
    slope = (y1 - y0) / max(x1 - x0, 1)
    base_x, base_y = (xs[-1], ys[-1]) if forward else (xs[0], ys[0])
    return int(base_y + slope * (t - base_x))


def _to_ordinal(value: str) -> int | None:
    try:
        return date.fromisoformat(str(value)[:10]).toordinal()
    except ValueError:
        return None


def resolve_season(
    schedule: list[dict[str, Any]],
    registry: Registry,
    *,
    scan_range: tuple[int, int] | None = None,
    coarse_step: int = 20,
    expand: int = 240,
    window: int = 900,
    predict_step: int = 6,
    rounds: int = 8,
    workers: int = 8,
    force_scan: bool = False,
    log: Callable[[str], None] = print,
) -> Registry:
    """Buduje mapowanie terminarz -> LiveStats dla calego sezonu."""
    index = ScheduleIndex(schedule)
    total = len(index.entries)

    if scan_range and (force_scan or not registry.matches):
        lo, hi = scan_range
        log("skan zgrubny {}-{} (krok {})".format(lo, hi, coarse_step))
        found = scan_ids(_unchecked(registry, lo, hi, coarse_step), index, registry, workers=workers)
        log("  kotwice: {}".format(found))

    for iteration in range(rounds):
        before = len(registry.resolved)

        # 2. zageszczenie wokol znanych trafien - mecze kolejki leza obok siebie
        ids: set[int] = set()
        windows: list[tuple[int, int]] = []
        for _, fid in registry.anchors():
            windows.append((fid - expand, fid + expand))
            ids.update(_unchecked(registry, fid - expand, fid + expand))
        if ids:
            log("iteracja {}: zageszczanie {} id".format(iteration + 1, len(ids)))
            scan_ids(sorted(ids), index, registry, workers=workers)
            for lo, hi in windows:
                registry.mark_checked(lo, hi)

        # 3. przewidywanie po dacie dla meczow, ktorych jeszcze nie znamy
        resolved = registry.resolved
        missing_dates = sorted({g["date"] for g in index.entries if g["pzkosz_id"] not in resolved and g.get("date")})
        anchors = registry.anchors()
        ids = set()
        for d in missing_dates:
            guess = interpolate(anchors, d)
            if guess:
                ids.update(_unchecked(registry, guess - window, guess + window, predict_step))
        if ids:
            log("iteracja {}: predykcja {} id dla {} dat".format(iteration + 1, len(ids), len(missing_dates)))
            scan_ids(sorted(ids), index, registry, workers=workers)

        after = len(registry.resolved)
        log("iteracja {}: dopasowano {}/{}".format(iteration + 1, after, total))
        if after == before or after == total:
            break

    return registry


def verify_registry(registry: Registry, *, workers: int = 8, log: Callable[[str], None] = print) -> int:
    """Sprawdza wpisy rejestru pelnym pobraniem i usuwa bledne dopasowania.

    Zwraca liczbe usunietych wpisow. Zwalnia tez zakresy oznaczone jako
    sprawdzone wokol usunietych identyfikatorow, zeby kolejny skan mial szanse
    znalezc wlasciwy mecz.
    """
    entries = [m for m in registry.matches if m.get("fiba_id")]
    if not entries:
        return 0
    ids = [int(m["fiba_id"]) for m in entries]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(confirm, ids))

    good: list[dict[str, Any]] = []
    dropped = 0
    for entry, full in zip(entries, results):
        if (
            full is not None
            and full.home_score == entry.get("home_score")
            and full.away_score == entry.get("away_score")
            and name_similarity(entry.get("home", ""), full.home) >= 0.34
            and name_similarity(entry.get("away", ""), full.away) >= 0.34
        ):
            entry["fiba_home"] = full.home
            entry["fiba_away"] = full.away
            entry["verified"] = True
            good.append(entry)
        else:
            dropped += 1
            log("usuwam bledne dopasowanie {} -> {}".format(entry.get("fiba_id"), entry.get("url", "")))
    registry.matches = good
    if dropped:
        registry.checked = []
    return dropped
