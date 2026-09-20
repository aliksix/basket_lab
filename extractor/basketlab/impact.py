"""Ratingi skorygowane o rywala oraz model wplywu zawodnika (Impact).

Dwa poziomy:

``adjusted_team_ratings``
    Iteracyjna korekta ORTG/DRTG o sile przeciwnikow - odpowiednik AdjO/AdjD
    z KenPom. Druzyna, ktora zdobyla 110 pkt/100 przeciwko najlepszej obronie
    ligi, zagrala lepiej niz ta, ktora zdobyla 112 przeciwko najgorszej.

``player_impact``
    Impact v1 z ``inspiration.md``: skorygowane on/off zmieszane z modelem
    box-score. Model box-score nie jest przepisany z innej ligi - dopasowujemy
    go regresja grzbietowa do skorygowanego on/off tej konkretnej ligi, wiec
    wspolczynniki opisuja 1 LM, a nie NBA. Dzieki liniowosci modelu ten sam
    zestaw wspolczynnikow daje rozbicie wplywu na rzuty, kreowanie, straty,
    zbiorki i obrone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from . import linalg, metrics

#: przewaga wlasnej hali w punktach na 100 posiadan
HOME_ADVANTAGE = 1.6

#: liczba posiadan, przy ktorej ufamy on/off w polowie
ON_OFF_TRUST = 900.0

#: sila sciagania modelu box-score do sredniej przy malej probce
BOX_PRIOR_POSSESSIONS = 250.0


@dataclass
class TeamRating:
    key: str
    gp: int = 0
    ortg: float = 0.0
    drtg: float = 0.0
    adj_ortg: float = 0.0
    adj_drtg: float = 0.0
    sos: float = 0.0

    @property
    def net(self) -> float:
        return self.ortg - self.drtg

    @property
    def adj_net(self) -> float:
        return self.adj_ortg - self.adj_drtg


def adjusted_team_ratings(
    rows: Sequence,
    *,
    iterations: int = 60,
    home_advantage: float = HOME_ADVANTAGE,
    recency_halflife: float | None = None,
) -> dict[str, TeamRating]:
    """Iteracyjna korekta efektywnosci o sile rywala.

    ``rows`` to obiekty z polami ``team``, ``opponent``, ``home``, ``points``,
    ``opp_points``, ``poss``, ``opp_poss`` (czyli ``season.TeamGame``).
    """
    teams = sorted({r.team for r in rows} | {r.opponent for r in rows})
    if not teams:
        return {}

    total_pts = sum(r.points for r in rows)
    total_poss = sum(r.poss for r in rows) or 1.0
    league = 100.0 * total_pts / total_poss

    ratings = {k: TeamRating(key=k, adj_ortg=league, adj_drtg=league) for k in teams}
    weights = _recency_weights(rows, recency_halflife)

    raw_o: dict[str, list[tuple[float, float, float, str]]] = {k: [] for k in teams}
    raw_d: dict[str, list[tuple[float, float, float, str]]] = {k: [] for k in teams}
    for row, weight in zip(rows, weights):
        if not row.poss or not row.opp_poss:
            continue
        edge = home_advantage / 2.0 * (1.0 if row.home else -1.0)
        raw_o[row.team].append((100.0 * row.points / row.poss - edge, weight, row.poss, row.opponent))
        raw_d[row.team].append((100.0 * row.opp_points / row.opp_poss + edge, weight, row.opp_poss, row.opponent))

    for key, rating in ratings.items():
        rating.gp = len(raw_o[key])
        rating.ortg = _weighted(raw_o[key]) or league
        rating.drtg = _weighted(raw_d[key]) or league
        rating.adj_ortg = rating.ortg
        rating.adj_drtg = rating.drtg

    for _ in range(iterations):
        new_o, new_d = {}, {}
        for key in teams:
            new_o[key] = _weighted(
                [(value * league / max(ratings[opp].adj_drtg, 1.0), w, p, opp) for value, w, p, opp in raw_o[key]]
            ) or league
            new_d[key] = _weighted(
                [(value * league / max(ratings[opp].adj_ortg, 1.0), w, p, opp) for value, w, p, opp in raw_d[key]]
            ) or league
        shift = max(
            max(abs(new_o[k] - ratings[k].adj_ortg) for k in teams),
            max(abs(new_d[k] - ratings[k].adj_drtg) for k in teams),
        )
        for key in teams:
            ratings[key].adj_ortg = new_o[key]
            ratings[key].adj_drtg = new_d[key]
        if shift < 1e-4:
            break

    for key in teams:
        opponents = [opp for _, _, _, opp in raw_o[key]]
        if opponents:
            ratings[key].sos = sum(ratings[o].adj_net for o in opponents) / len(opponents)
    return ratings


def _weighted(items: Iterable[tuple[float, float, float, str]]) -> float | None:
    total = 0.0
    weight_sum = 0.0
    for value, weight, poss, _ in items:
        w = weight * max(poss, 1.0)
        total += value * w
        weight_sum += w
    return total / weight_sum if weight_sum else None


def _recency_weights(rows: Sequence, halflife: float | None) -> list[float]:
    if not halflife:
        return [1.0] * len(rows)
    dates = sorted({r.date for r in rows if r.date})
    if not dates:
        return [1.0] * len(rows)
    order = {d: i for i, d in enumerate(dates)}
    newest = len(dates) - 1
    return [0.5 ** ((newest - order.get(r.date, newest)) / halflife) for r in rows]


# --- wplyw zawodnika ----------------------------------------------------------
#: cechy modelu box-score (per 100 posiadan albo w procentach) wraz z grupa,
#: do ktorej trafia ich wklad w rozbiciu wplywu
OFFENSE_FEATURES = [
    ("scoring_100", "shooting"),
    ("ts_added_100", "shooting"),
    ("three_rate", "shooting"),
    ("ast_100", "creation"),
    ("usage", "creation"),
    ("tov_100", "turnovers"),
    ("orb_rate", "rebounding"),
    ("ftr", "shooting"),
]

DEFENSE_FEATURES = [
    ("stl_100", "disruption"),
    ("blk_100", "rim_protection"),
    ("drb_rate", "rebounding"),
    ("pf_100", "fouls"),
]

FEATURE_LABELS_PL = {
    "scoring_100": "punkty / 100",
    "ts_added_100": "skutecznosc ponad liga",
    "three_rate": "udzial trojek",
    "ast_100": "asysty / 100",
    "usage": "udzial w akcjach",
    "tov_100": "straty / 100",
    "orb_rate": "zbiorki w ataku",
    "ftr": "rzuty wolne",
    "stl_100": "przechwyty / 100",
    "blk_100": "bloki / 100",
    "drb_rate": "zbiorki w obronie",
    "pf_100": "faule / 100",
}

GROUP_LABELS_PL = {
    "shooting": "Rzuty",
    "creation": "Kreowanie",
    "turnovers": "Strata pilki",
    "rebounding": "Zbiorki",
    "disruption": "Przechwyty i presja",
    "rim_protection": "Obrona obreczy",
    "fouls": "Faule",
}


@dataclass
class ImpactModel:
    """Dopasowany model box-score -> wplyw na 100 posiadan."""

    offense: list[float] = field(default_factory=list)
    defense: list[float] = field(default_factory=list)
    offense_means: list[float] = field(default_factory=list)
    offense_stds: list[float] = field(default_factory=list)
    defense_means: list[float] = field(default_factory=list)
    defense_stds: list[float] = field(default_factory=list)
    sample: int = 0

    def predict_offense(self, features: Mapping[str, float]) -> tuple[float, dict[str, float]]:
        return self._predict(features, OFFENSE_FEATURES, self.offense, self.offense_means, self.offense_stds)

    def predict_defense(self, features: Mapping[str, float]) -> tuple[float, dict[str, float]]:
        return self._predict(features, DEFENSE_FEATURES, self.defense, self.defense_means, self.defense_stds)

    @staticmethod
    def _predict(
        features: Mapping[str, float],
        spec: Sequence[tuple[str, str]],
        coefficients: Sequence[float],
        means: Sequence[float],
        stds: Sequence[float],
    ) -> tuple[float, dict[str, float]]:
        if not coefficients:
            return 0.0, {}
        contributions: dict[str, float] = {}
        total = coefficients[-1]
        for i, (name, group) in enumerate(spec):
            value = float(features.get(name) or 0.0)
            scaled = (value - means[i]) / (stds[i] or 1.0)
            part = coefficients[i] * scaled
            total += part
            contributions[group] = contributions.get(group, 0.0) + part
        return total, contributions


def fit_impact_model(samples: Sequence[Mapping[str, Any]], alpha: float = 8.0) -> ImpactModel:
    """Dopasowuje model box-score do skorygowanego on/off calej ligi."""
    usable = [s for s in samples if s.get("on_poss", 0) >= 150]
    if len(usable) < 20:
        return ImpactModel()

    model = ImpactModel(sample=len(usable))
    for spec, target_key, attr in (
        (OFFENSE_FEATURES, "adj_on_off_off", "offense"),
        (DEFENSE_FEATURES, "adj_on_off_def", "defense"),
    ):
        rows = [[float(s["features"].get(name) or 0.0) for name, _ in spec] for s in usable]
        scaled, means, stds = linalg.standardize(rows)
        target = [float(s.get(target_key) or 0.0) for s in usable]
        weights = [float(s.get("on_poss") or 0.0) for s in usable]
        coefficients = linalg.ridge(scaled, target, weights, alpha=alpha)
        setattr(model, attr, coefficients)
        setattr(model, attr + "_means", means)
        setattr(model, attr + "_stds", stds)
    return model


def blend(adjusted_on_off: float | None, box: float, possessions: float) -> float:
    """Miesza skorygowane on/off z modelem box-score wedlug wielkosci proby."""
    if adjusted_on_off is None:
        return box
    weight = possessions / (possessions + ON_OFF_TRUST)
    return weight * adjusted_on_off + (1.0 - weight) * box


def shrink(value: float | None, possessions: float, prior: float = 0.0) -> float | None:
    """Sciaga wynik do sredniej, gdy proba jest mala."""
    if value is None:
        return None
    weight = possessions / (possessions + BOX_PRIOR_POSSESSIONS)
    return weight * value + (1.0 - weight) * prior
