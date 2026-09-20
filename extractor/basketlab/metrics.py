"""Metryki zaawansowane liczone z sum statystyk.

Wszystkie funkcje sa czyste - przyjmuja slownik sum (``fga``, ``pts``, ...)
i zwracaja wartosci pochodne. Dzieki temu ten sam kod obsluguje statystyki
druzyny, zawodnika, piatki i dowolny wycinek sezonu.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

#: liczba posiadan, ponizej ktorej nie pokazujemy wskaznikow tempa
MIN_POSSESSIONS = 20

#: wspolczynnik zamiany rzutow wolnych na posiadania
FT_POSSESSION_FACTOR = 0.44


def g(stats: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(stats.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def safe_div(num: float, den: float, default: float | None = None) -> float | None:
    return num / den if den else default


def pct(num: float, den: float) -> float | None:
    v = safe_div(num, den)
    return None if v is None else v * 100.0


# --- podstawowe wskazniki skutecznosci ---------------------------------------
def efg(stats: Mapping[str, Any]) -> float | None:
    """Effective FG% - trojka wazy 1.5 rzutu za dwa."""
    return pct(g(stats, "fgm") + 0.5 * g(stats, "tpm"), g(stats, "fga"))


def ts(stats: Mapping[str, Any]) -> float | None:
    """True Shooting% - skutecznosc z uwzglednieniem rzutow wolnych."""
    den = 2.0 * (g(stats, "fga") + FT_POSSESSION_FACTOR * g(stats, "fta"))
    return pct(g(stats, "pts"), den)


def three_rate(stats: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "tpa"), g(stats, "fga"))


def ft_rate(stats: Mapping[str, Any]) -> float | None:
    """FTr - ile rzutow wolnych przypada na rzut z gry."""
    return pct(g(stats, "fta"), g(stats, "fga"))


def ft_pct(stats: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "ftm"), g(stats, "fta"))


def fg_pct(stats: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "fgm"), g(stats, "fga"))


def three_pct(stats: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "tpm"), g(stats, "tpa"))


def two_pct(stats: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "fgm") - g(stats, "tpm"), g(stats, "fga") - g(stats, "tpa"))


def pps(stats: Mapping[str, Any]) -> float | None:
    """Punkty na rzut z gry (bez rzutow wolnych)."""
    return safe_div(2.0 * (g(stats, "fgm") - g(stats, "tpm")) + 3.0 * g(stats, "tpm"), g(stats, "fga"))


# --- tempo i efektywnosc ------------------------------------------------------
def possessions(stats: Mapping[str, Any]) -> float:
    """Posiadania z boxscore (uzywane, gdy brak play-by-play)."""
    return (
        g(stats, "fga")
        - g(stats, "orb")
        + g(stats, "tov")
        + FT_POSSESSION_FACTOR * g(stats, "fta")
    )


def ortg(points: float, poss: float) -> float | None:
    return safe_div(100.0 * points, poss)


def pace(poss: float, minutes: float, period_minutes: float = 40.0) -> float | None:
    """Posiadania na pelny mecz (40 minut gry piatek)."""
    return safe_div(poss * period_minutes, minutes)


# --- four factors -------------------------------------------------------------
def tov_rate(stats: Mapping[str, Any], poss: float | None = None) -> float | None:
    den = poss if poss else possessions(stats)
    return pct(g(stats, "tov"), den)


def orb_rate(stats: Mapping[str, Any], opp: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "orb"), g(stats, "orb") + g(opp, "drb"))


def drb_rate(stats: Mapping[str, Any], opp: Mapping[str, Any]) -> float | None:
    return pct(g(stats, "drb"), g(stats, "drb") + g(opp, "orb"))


def four_factors(stats: Mapping[str, Any], opp: Mapping[str, Any], poss: float | None = None) -> dict[str, float | None]:
    return {
        "efg": efg(stats),
        "tov_rate": tov_rate(stats, poss),
        "orb_rate": orb_rate(stats, opp),
        "ft_rate": ft_rate(stats),
    }


# --- udzial zawodnika w grze druzyny -----------------------------------------
def usage(player: Mapping[str, Any], team: Mapping[str, Any]) -> float | None:
    """USG% - odsetek posiadan druzyny konczonych akcja zawodnika."""
    pmin, tmin = g(player, "min"), g(team, "min")
    if not pmin or not tmin:
        return None
    player_plays = g(player, "fga") + FT_POSSESSION_FACTOR * g(player, "fta") + g(player, "tov")
    team_plays = g(team, "fga") + FT_POSSESSION_FACTOR * g(team, "fta") + g(team, "tov")
    return pct(player_plays * (tmin / 5.0), pmin * team_plays)


def assist_rate(player: Mapping[str, Any], team: Mapping[str, Any]) -> float | None:
    """AST% - odsetek trafien kolegow z asysta zawodnika, gdy jest na parkiecie."""
    pmin, tmin = g(player, "min"), g(team, "min")
    if not pmin or not tmin:
        return None
    den = (pmin / (tmin / 5.0)) * g(team, "fgm") - g(player, "fgm")
    return pct(g(player, "ast"), den)


def turnover_rate(player: Mapping[str, Any]) -> float | None:
    den = g(player, "fga") + FT_POSSESSION_FACTOR * g(player, "fta") + g(player, "tov")
    return pct(g(player, "tov"), den)


def rebound_rate(player: Mapping[str, Any], team: Mapping[str, Any], opp: Mapping[str, Any], side: str) -> float | None:
    """ORB%/DRB%/TRB% - odsetek zbiorek zebranych przy zawodniku na parkiecie."""
    pmin, tmin = g(player, "min"), g(team, "min")
    if not pmin or not tmin:
        return None
    if side == "off":
        pool = g(team, "orb") + g(opp, "drb")
        own = g(player, "orb")
    elif side == "def":
        pool = g(team, "drb") + g(opp, "orb")
        own = g(player, "drb")
    else:
        pool = g(team, "trb") + g(opp, "trb")
        own = g(player, "trb")
    return pct(own * (tmin / 5.0), pmin * pool)


def steal_rate(player: Mapping[str, Any], team: Mapping[str, Any], opp_poss: float) -> float | None:
    pmin, tmin = g(player, "min"), g(team, "min")
    if not pmin or not tmin or not opp_poss:
        return None
    return pct(g(player, "stl") * (tmin / 5.0), pmin * opp_poss)


def block_rate(player: Mapping[str, Any], team: Mapping[str, Any], opp: Mapping[str, Any]) -> float | None:
    pmin, tmin = g(player, "min"), g(team, "min")
    opp_two = g(opp, "fga") - g(opp, "tpa")
    if not pmin or not tmin or not opp_two:
        return None
    return pct(g(player, "blk") * (tmin / 5.0), pmin * opp_two)


def per_minutes(stats: Mapping[str, Any], keys: Iterable[str], minutes: float = 40.0) -> dict[str, float | None]:
    played = g(stats, "min")
    return {k: safe_div(g(stats, k) * minutes, played) for k in keys}


def per_possessions(stats: Mapping[str, Any], keys: Iterable[str], poss: float, base: float = 100.0) -> dict[str, float | None]:
    return {k: safe_div(g(stats, k) * base, poss) for k in keys}


# --- serie punktowe -----------------------------------------------------------
def kill_shots(events, threshold: int = 10) -> dict[int, int]:
    """Liczy serie co najmniej ``threshold`` punktow bez odpowiedzi rywala."""
    counts = {1: 0, 2: 0}
    run_team = 0
    run = 0
    prev = (0, 0)
    for ev in events:
        cur = (ev.s1, ev.s2)
        d1, d2 = cur[0] - prev[0], cur[1] - prev[1]
        if d1 <= 0 and d2 <= 0:
            continue
        scorer = 1 if d1 > 0 else 2
        gained = d1 if scorer == 1 else d2
        if scorer == run_team:
            run += gained
        else:
            run_team, run = scorer, gained
        if run >= threshold:
            counts[scorer] += 1
            run_team, run = 0, 0
        prev = cur
    return counts


# --- narzedzia ----------------------------------------------------------------
def percentile_ranks(values: Mapping[str, float | None], higher_is_better: bool = True) -> dict[str, float | None]:
    """Percentyl kazdej wartosci w obrebie podanego zbioru (metoda srodkowej rangi)."""
    present = [v for v in values.values() if v is not None]
    n = len(present)
    if n < 2:
        return {k: (50.0 if v is not None else None) for k, v in values.items()}
    out: dict[str, float | None] = {}
    for key, value in values.items():
        if value is None:
            out[key] = None
            continue
        if higher_is_better:
            better = sum(1 for v in present if v < value)
        else:
            better = sum(1 for v in present if v > value)
        equal = sum(1 for v in present if v == value)
        out[key] = round(100.0 * (better + 0.5 * equal) / n, 1)
    return out


def ranks(values: Mapping[str, float | None], higher_is_better: bool = True) -> dict[str, int | None]:
    """Miejsce w stawce (1 = najlepsze)."""
    present = [(k, v) for k, v in values.items() if v is not None]
    present.sort(key=lambda kv: kv[1], reverse=higher_is_better)
    out: dict[str, int | None] = {k: None for k in values}
    place = 0
    last: float | None = None
    for i, (key, value) in enumerate(present, start=1):
        if last is None or value != last:
            place = i
            last = value
        out[key] = place
    return out


def add(target: dict[str, float], source: Mapping[str, Any], keys: Iterable[str] | None = None) -> dict[str, float]:
    """Sumuje statystyki licznikowe."""
    for key, value in source.items():
        if keys is not None and key not in keys:
            continue
        if isinstance(value, (int, float)):
            target[key] = target.get(key, 0.0) + float(value)
    return target


def round_all(data: Mapping[str, Any], digits: int = 2) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, float):
            out[key] = round(value, digits)
        elif isinstance(value, dict):
            out[key] = round_all(value, digits)
        else:
            out[key] = value
    return out
