"""Budowa plikow JSON dla portalu KKS Basket Poznan Lab.

Wejsciem jest rejestr meczow (``discover.Registry``), wyjsciem katalog
``docs/data`` z gotowymi danymi dla statycznej strony na GitHub Pages.
Wszystkie wskazniki licza sie tutaj raz; przegladarka robi juz tylko filtry
i sumowanie surowych wierszy meczowych.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import fiba, impact, metrics, season as season_mod
from .court import DETAILED_ZONES, ZONES
from .discover import Registry
from .http import Fetcher
from .season import Season, TeamGame, morey_score, zone_profile

#: minimalny czas gry, zeby zawodnik trafial do rankingow ligowych
MIN_LEAGUE_MINUTES = 120.0
#: minimalna liczba posiadan piatki, zeby pokazac jej ratingi
MIN_LINEUP_POSSESSIONS = 15
#: minimalna liczba posiadan pary zawodnikow
MIN_PAIR_POSSESSIONS = 60

POSITION_GROUPS = {
    "PG": "guards", "SG": "guards", "G": "guards",
    "SF": "wings", "F": "wings", "GF": "wings", "SG/SF": "wings",
    "PF": "bigs", "C": "bigs", "FC": "bigs",
}


@dataclass
class BuildConfig:
    club: str
    club_display: str
    competition: str
    season: str
    registry_path: Path
    out_dir: Path
    cache_dir: Path
    assets_dir: Path
    download_assets: bool = True
    limit: int | None = None


# --- pomocnicze ---------------------------------------------------------------
def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _r(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def _counting(stats: Mapping[str, float]) -> dict[str, float]:
    return {k: round(float(v), 2) for k, v in stats.items()}


# --- statystyki druzyny -------------------------------------------------------
def team_metrics(bundle: Mapping[str, Any]) -> dict[str, Any]:
    stats = bundle["stats"]
    opp = bundle["opp_stats"]
    poss = bundle["poss"] or metrics.possessions(stats)
    opp_poss = bundle["opp_poss"] or metrics.possessions(opp)
    minutes = stats.get("min") or bundle["gp"] * 200.0
    zones = bundle["zones"]
    opp_zones = bundle["opp_zones"]
    zones14 = bundle.get("zones14") or {}
    opp_zones14 = bundle.get("opp_zones14") or {}
    clutch = bundle.get("clutch") or {}
    long15 = bundle.get("long15") or {}

    return {
        "gp": bundle["gp"],
        "w": bundle["w"],
        "l": bundle["l"],
        "pts": bundle["pts"],
        "opp_pts": bundle["opp_pts"],
        "poss": _r(poss),
        "opp_poss": _r(opp_poss),
        "pace": _r(metrics.pace((poss + opp_poss) / 2.0, minutes / 5.0)),
        "ortg": _r(metrics.ortg(bundle["pts"], poss), 2),
        "drtg": _r(metrics.ortg(bundle["opp_pts"], opp_poss), 2),
        "net": _r(
            (metrics.ortg(bundle["pts"], poss) or 0) - (metrics.ortg(bundle["opp_pts"], opp_poss) or 0), 2
        ),
        "ff": {
            "efg": _r(metrics.efg(stats)),
            "tov_rate": _r(metrics.tov_rate(stats, poss)),
            "orb_rate": _r(metrics.orb_rate(stats, opp)),
            "ft_rate": _r(metrics.ft_rate(stats)),
        },
        "opp_ff": {
            "efg": _r(metrics.efg(opp)),
            "tov_rate": _r(metrics.tov_rate(opp, opp_poss)),
            "orb_rate": _r(metrics.orb_rate(opp, stats)),
            "ft_rate": _r(metrics.ft_rate(opp)),
        },
        "ts": _r(metrics.ts(stats)),
        "opp_ts": _r(metrics.ts(opp)),
        "fg_pct": _r(metrics.fg_pct(stats)),
        "three_pct": _r(metrics.three_pct(stats)),
        "two_pct": _r(metrics.two_pct(stats)),
        "ft_pct": _r(metrics.ft_pct(stats)),
        "tpar": _r(metrics.three_rate(stats)),
        "drb_rate": _r(metrics.drb_rate(stats, opp)),
        "ast_rate": _r(metrics.pct(stats.get("ast", 0), stats.get("fgm", 0))),
        "ast_to": _r(metrics.safe_div(stats.get("ast", 0), stats.get("tov", 0)), 2),
        "stl_100": _r(metrics.safe_div(100.0 * stats.get("stl", 0), opp_poss), 2),
        "blk_100": _r(metrics.safe_div(100.0 * stats.get("blk", 0), opp_poss), 2),
        "pts_paint": _r(metrics.safe_div(stats.get("pts_paint", 0), bundle["gp"])),
        "pts_fb": _r(metrics.safe_div(stats.get("pts_fb", 0), bundle["gp"])),
        "pts_2nd": _r(metrics.safe_div(stats.get("pts_2nd", 0), bundle["gp"])),
        "kill_shots": bundle["kill_shots"],
        "kill_allowed": bundle["kill_allowed"],
        "clutch": _counting(clutch),
        "long15": _counting(long15),
        "clutch_ortg": _r(metrics.ortg(clutch.get("pts", 0), clutch.get("off_poss", 0)), 2),
        "clutch_drtg": _r(metrics.ortg(clutch.get("opp_pts", 0), clutch.get("def_poss", 0)), 2),
        "fga_long_rate": _r(metrics.pct(long15.get("fga_long", 0), long15.get("fga", 0))),
        "ppp_long": _r(metrics.safe_div(long15.get("pts_long", 0), long15.get("off_poss_long", 0)), 3),
        "morey": _r(morey_score(zones)),
        "opp_morey": _r(morey_score(opp_zones)),
        "zones": {z: {k: _r(v, 3) for k, v in vals.items()} for z, vals in zone_profile(zones).items()},
        "opp_zones": {z: {k: _r(v, 3) for k, v in vals.items()} for z, vals in zone_profile(opp_zones).items()},
        "zones14": {z: {k: _r(v, 3) for k, v in vals.items()}
                    for z, vals in zone_profile(zones14, DETAILED_ZONES).items()},
        "opp_zones14": {z: {k: _r(v, 3) for k, v in vals.items()}
                        for z, vals in zone_profile(opp_zones14, DETAILED_ZONES).items()},
        "stats": _counting(stats),
        "opp_stats": _counting(opp),
    }


# --- statystyki zawodnika -----------------------------------------------------
def player_features(
    totals: Mapping[str, float],
    team_totals: Mapping[str, float],
    opp_totals: Mapping[str, float],
    on_poss: float,
    on_def_poss: float,
    league_ts: float,
) -> dict[str, float | None]:
    """Cechy uzywane i w profilu zawodnika, i w modelu wplywu."""
    poss_share = on_poss or metrics.possessions(totals)
    ts_value = metrics.ts(totals)
    shots = totals.get("fga", 0) + 0.44 * totals.get("fta", 0)
    return {
        "scoring_100": metrics.safe_div(100.0 * totals.get("pts", 0), poss_share),
        "ts_added_100": (
            None
            if ts_value is None or not poss_share
            else 2.0 * (ts_value - league_ts) / 100.0 * shots * 100.0 / poss_share
        ),
        "three_rate": metrics.three_rate(totals),
        "ast_100": metrics.safe_div(100.0 * totals.get("ast", 0), poss_share),
        "usage": metrics.usage(totals, team_totals),
        "tov_100": metrics.safe_div(100.0 * totals.get("tov", 0), poss_share),
        "orb_rate": metrics.rebound_rate(totals, team_totals, opp_totals, "off"),
        "ftr": metrics.ft_rate(totals),
        "stl_100": metrics.safe_div(100.0 * totals.get("stl", 0), on_def_poss or poss_share),
        "blk_100": metrics.safe_div(100.0 * totals.get("blk", 0), on_def_poss or poss_share),
        "drb_rate": metrics.rebound_rate(totals, team_totals, opp_totals, "def"),
        "pf_100": metrics.safe_div(100.0 * totals.get("pf", 0), on_def_poss or poss_share),
    }


def player_metrics(
    totals: Mapping[str, float],
    team_totals: Mapping[str, float],
    opp_totals: Mapping[str, float],
    opp_poss: float,
    league_ts: float,
) -> dict[str, Any]:
    ts_value = metrics.ts(totals)
    per_game_keys = ["pts", "trb", "orb", "drb", "ast", "tov", "stl", "blk", "pf", "min", "fga", "tpa", "fta"]
    gp = max(totals.get("gp", 0), 1)
    return {
        "ts": _r(ts_value),
        "rts": _r(None if ts_value is None else ts_value - league_ts),
        "efg": _r(metrics.efg(totals)),
        "fg_pct": _r(metrics.fg_pct(totals)),
        "three_pct": _r(metrics.three_pct(totals)),
        "two_pct": _r(metrics.two_pct(totals)),
        "ft_pct": _r(metrics.ft_pct(totals)),
        "tpar": _r(metrics.three_rate(totals)),
        "ftr": _r(metrics.ft_rate(totals)),
        "usage": _r(metrics.usage(totals, team_totals)),
        "ast_rate": _r(metrics.assist_rate(totals, team_totals)),
        "tov_rate": _r(metrics.turnover_rate(totals)),
        "orb_rate": _r(metrics.rebound_rate(totals, team_totals, opp_totals, "off")),
        "drb_rate": _r(metrics.rebound_rate(totals, team_totals, opp_totals, "def")),
        "trb_rate": _r(metrics.rebound_rate(totals, team_totals, opp_totals, "all")),
        "stl_rate": _r(metrics.steal_rate(totals, team_totals, opp_poss), 2),
        "blk_rate": _r(metrics.block_rate(totals, team_totals, opp_totals), 2),
        "ast_to": _r(metrics.safe_div(totals.get("ast", 0), totals.get("tov", 0)), 2),
        # PPP indywidualne: punkty na jedno posiadanie zakonczone jego akcja
        "ppp_ind": _r(
            metrics.safe_div(
                totals.get("pts", 0),
                totals.get("fga", 0) + 0.44 * totals.get("fta", 0) + totals.get("tov", 0),
            ),
            3,
        ),
        "per_game": {k: _r(metrics.safe_div(totals.get(k, 0), gp)) for k in per_game_keys},
        "per40": {k: _r(v) for k, v in metrics.per_minutes(totals, per_game_keys[:-4] + ["fga", "tpa", "fta"]).items()},
    }


# --- glowny przebieg ----------------------------------------------------------
class SiteBuilder:
    def __init__(self, config: BuildConfig):
        self.cfg = config
        self.fetcher = Fetcher(config.cache_dir)
        self.season = Season()
        self.registry = Registry.load(config.registry_path)
        self.club_key: str = ""
        self.assets: dict[str, str] = {}

    # -- wczytanie meczow ----------------------------------------------------
    def load(self, log=print) -> None:
        entries = [m for m in self.registry.matches if m.get("fiba_id")]
        entries.sort(key=lambda m: (m.get("date") or "", int(m["fiba_id"])))
        if self.cfg.limit:
            entries = entries[: self.cfg.limit]
        canonical: list[str] = []
        for entry in entries:
            for side in ("home", "away"):
                if entry.get(side) and entry[side] not in canonical:
                    canonical.append(entry[side])
        self.season.resolver = season_mod.TeamResolver(canonical)

        for i, entry in enumerate(entries, start=1):
            try:
                game = fiba.load(str(entry["fiba_id"]), self.fetcher)
            except Exception as exc:  # pragma: no cover - siec
                self.season.warnings.append("mecz {}: {}".format(entry["fiba_id"], exc))
                continue
            if not self._verify(game, entry):
                continue
            self.season.add_game(game, entry)
            if i % 25 == 0:
                log("wczytano {}/{} meczow".format(i, len(entries)))
        log("wczytano {} meczow".format(len(self.season.games)))
        self.club_key = self.season.resolver.key(self.cfg.club)

    def _verify(self, game, entry: Mapping[str, Any]) -> bool:
        """Kontrola, czy identyfikator LiveStats naprawde wskazuje ten mecz."""
        if len(game.teams) != 2:
            self.season.warnings.append("mecz {}: niepelne dane".format(entry["fiba_id"]))
            return False
        ok = (
            game.teams[1].score == entry.get("home_score")
            and game.teams[2].score == entry.get("away_score")
        )
        if not ok:
            self.season.warnings.append(
                "mecz {}: wynik {}:{} nie zgadza sie z terminarzem {}:{}".format(
                    entry["fiba_id"],
                    game.teams[1].score,
                    game.teams[2].score,
                    entry.get("home_score"),
                    entry.get("away_score"),
                )
            )
        return ok

    # -- agregaty ------------------------------------------------------------
    def build(self, log=print) -> dict[str, Any]:
        s = self.season
        by_team: dict[str, list[TeamGame]] = defaultdict(list)
        for row in s.team_games:
            by_team[row.team].append(row)

        ratings = impact.adjusted_team_ratings(s.team_games)
        league_stats = metrics.add({}, {})
        for row in s.team_games:
            metrics.add(league_stats, row.stats)
        league_ts = metrics.ts(league_stats) or 55.0
        league_poss = sum(r.poss for r in s.team_games) or 1.0
        league_ortg = 100.0 * sum(r.points for r in s.team_games) / league_poss

        teams_payload: dict[str, Any] = {}
        for key, rows in by_team.items():
            bundle = season_mod.sum_team_games(rows)
            payload = team_metrics(bundle)
            rating = ratings.get(key)
            payload.update(
                {
                    "key": key,
                    "name": s.teams.get(key, {}).get("name", key),
                    "short": s.teams.get(key, {}).get("short", ""),
                    "logo": self.assets.get("logo:" + key, s.teams.get(key, {}).get("logo", "")),
                    "coach": sorted(s.teams.get(key, {}).get("coaches", []) or [""])[-1],
                    "adj_ortg": _r(rating.adj_ortg, 2) if rating else None,
                    "adj_drtg": _r(rating.adj_drtg, 2) if rating else None,
                    "adj_net": _r(rating.adj_net, 2) if rating else None,
                    "sos": _r(rating.sos, 2) if rating else None,
                }
            )
            teams_payload[key] = payload

        players_payload = self._players(league_ts, league_ortg, ratings)
        lineups_payload, pairs_payload = self._lineups(ratings, league_ortg)

        log("druzyny: {}, zawodnicy: {}, piatki: {}".format(len(teams_payload), len(players_payload), len(lineups_payload)))
        return {
            "teams": teams_payload,
            "players": players_payload,
            "lineups": lineups_payload,
            "pairs": pairs_payload,
            "league": {
                "ortg": _r(league_ortg, 2),
                "ts": _r(league_ts),
                "poss": _r(league_poss),
                "zones": {
                    z: {k: _r(v, 3) for k, v in vals.items()}
                    for z, vals in zone_profile(_league_zones(s.team_games)).items()
                },
                "zones14": {
                    z: {k: _r(v, 3) for k, v in vals.items()}
                    for z, vals in zone_profile(_league_zones(s.team_games, "zones14"), DETAILED_ZONES).items()
                },
            },
        }

    # -- zawodnicy -----------------------------------------------------------
    def _players(self, league_ts: float, league_ortg: float, ratings) -> dict[str, Any]:
        s = self.season
        by_player: dict[str, list] = defaultdict(list)
        for row in s.player_games:
            by_player[row.player].append(row)

        team_totals: dict[str, dict[str, float]] = defaultdict(dict)
        opp_totals: dict[str, dict[str, float]] = defaultdict(dict)
        team_opp_poss: dict[str, float] = defaultdict(float)
        for row in s.team_games:
            metrics.add(team_totals[row.team], row.stats)
            metrics.add(opp_totals[row.team], row.opp_stats)
            team_opp_poss[row.team] += row.opp_poss

        samples: list[dict[str, Any]] = []
        payload: dict[str, Any] = {}
        for key, rows in by_player.items():
            profile = dict(s.players[key])
            totals = metrics.add({}, {})
            on = {"off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0, "secs": 0.0}
            off = {"off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0}
            opp_adj_d: list[tuple[float, float]] = []
            opp_adj_o: list[tuple[float, float]] = []
            for row in rows:
                metrics.add(totals, row.stats)
                for k in on:
                    on[k] += float(row.on.get(k, 0) or 0)
                for k in off:
                    off[k] += float(row.off.get(k, 0) or 0)
                rating = ratings.get(row.opponent)
                if rating:
                    opp_adj_d.append((rating.adj_drtg, float(row.on.get("off_poss", 0) or 0)))
                    opp_adj_o.append((rating.adj_ortg, float(row.on.get("def_poss", 0) or 0)))
            totals["gp"] = len(rows)
            totals["gs"] = sum(1 for r in rows if r.started)

            team = profile["team"]
            core = player_metrics(totals, team_totals[team], opp_totals[team], team_opp_poss[team], league_ts)
            features = player_features(
                totals, team_totals[team], opp_totals[team], on["off_poss"], on["def_poss"], league_ts
            )

            on_ortg = metrics.ortg(on["pts"], on["off_poss"])
            on_drtg = metrics.ortg(on["opp_pts"], on["def_poss"])
            off_ortg = metrics.ortg(off["pts"], off["off_poss"])
            off_drtg = metrics.ortg(off["opp_pts"], off["def_poss"])
            exp_d = _weighted_average(opp_adj_d)
            exp_o = _weighted_average(opp_adj_o)
            adj_off = None if on_ortg is None or exp_d is None else on_ortg - exp_d
            adj_def = None if on_drtg is None or exp_o is None else exp_o - on_drtg

            entry = {
                **profile,
                "gp": totals["gp"],
                "gs": totals["gs"],
                "min": _r(totals.get("min", 0)),
                "totals": _counting(totals),
                "metrics": core,
                "features": {k: _r(v, 3) for k, v in features.items()},
                "on_off": {
                    "on_poss": _r(on["off_poss"], 0),
                    "on_def_poss": _r(on["def_poss"], 0),
                    "on_ortg": _r(on_ortg, 2),
                    "on_drtg": _r(on_drtg, 2),
                    "on_net": _r(None if on_ortg is None or on_drtg is None else on_ortg - on_drtg, 2),
                    "off_ortg": _r(off_ortg, 2),
                    "off_drtg": _r(off_drtg, 2),
                    "off_net": _r(None if off_ortg is None or off_drtg is None else off_ortg - off_drtg, 2),
                    "diff": _r(
                        None
                        if None in (on_ortg, on_drtg, off_ortg, off_drtg)
                        else (on_ortg - on_drtg) - (off_ortg - off_drtg),
                        2,
                    ),
                    "adj_off": _r(adj_off, 2),
                    "adj_def": _r(adj_def, 2),
                    "adj_net": _r(None if adj_off is None or adj_def is None else adj_off + adj_def, 2),
                },
                "games": [
                    {
                        "match_id": r.match_id,
                        "date": r.date,
                        "round": r.round_no,
                        "opp": r.opponent,
                        "home": r.home,
                        "win": r.win,
                        "started": r.started,
                        "stats": _counting(r.stats),
                        "on": {k: _r(v, 1) for k, v in r.on.items()},
                        "off": {k: _r(v, 1) for k, v in r.off.items()},
                        "clutch": {k: _r(v, 1) for k, v in r.clutch.items()},
                        "long15": {k: _r(v, 1) for k, v in r.long15.items()},
                    }
                    for r in sorted(rows, key=lambda r: (r.date, r.match_id))
                ],
            }
            payload[key] = entry
            if totals.get("min", 0) >= MIN_LEAGUE_MINUTES:
                samples.append(
                    {
                        "key": key,
                        "features": features,
                        "on_poss": on["off_poss"] + on["def_poss"],
                        "adj_on_off_off": adj_off,
                        "adj_on_off_def": adj_def,
                    }
                )

        model = impact.fit_impact_model([s for s in samples if s["adj_on_off_off"] is not None])
        self._apply_impact(payload, model, league_ortg)
        self._apply_percentiles(payload)
        return payload

    def _apply_impact(self, payload: dict[str, Any], model: impact.ImpactModel, league_ortg: float) -> None:
        for entry in payload.values():
            features = {k: (v or 0.0) for k, v in entry["features"].items()}
            box_off, off_parts = model.predict_offense(features)
            box_def, def_parts = model.predict_defense(features)
            on_poss = float(entry["on_off"]["on_poss"] or 0) + float(entry["on_off"]["on_def_poss"] or 0)
            total_off = impact.blend(entry["on_off"]["adj_off"], box_off, on_poss)
            total_def = impact.blend(entry["on_off"]["adj_def"], box_def, on_poss)
            total_off = impact.shrink(total_off, on_poss) or 0.0
            total_def = impact.shrink(total_def, on_poss) or 0.0
            entry["impact"] = {
                "total": _r(total_off + total_def, 2),
                "off": _r(total_off, 2),
                "def": _r(total_def, 2),
                "box_off": _r(box_off, 2),
                "box_def": _r(box_def, 2),
                "breakdown": {k: _r(v, 2) for k, v in {**off_parts, **def_parts}.items()},
            }

    def _apply_percentiles(self, payload: dict[str, Any]) -> None:
        pool = {k: v for k, v in payload.items() if float(v.get("min") or 0) >= MIN_LEAGUE_MINUTES}
        if len(pool) < 5:
            pool = payload
        specs: list[tuple[str, str, bool]] = [
            ("metrics", "ts", True), ("metrics", "rts", True), ("metrics", "efg", True),
            ("metrics", "three_pct", True), ("metrics", "ft_pct", True), ("metrics", "usage", True),
            ("metrics", "ast_rate", True), ("metrics", "tov_rate", False), ("metrics", "orb_rate", True),
            ("metrics", "drb_rate", True), ("metrics", "trb_rate", True), ("metrics", "stl_rate", True),
            ("metrics", "blk_rate", True), ("metrics", "ftr", True), ("metrics", "tpar", True),
            ("impact", "total", True), ("impact", "off", True), ("impact", "def", True),
            # osie wykresu radarowego i kafla zawodnika
            ("metrics", "ppp_ind", True), ("features", "scoring_100", True),
            ("on_off", "on_ortg", True), ("on_off", "on_drtg", False),
        ]
        groups = defaultdict(list)
        for key, entry in pool.items():
            groups[POSITION_GROUPS.get(entry.get("position", ""), "wings")].append(key)

        for entry in payload.values():
            entry.setdefault("percentiles", {})
            entry.setdefault("percentiles_pos", {})
        for section, metric, higher in specs:
            values = {k: _value(v, section, metric) for k, v in pool.items()}
            for key, rank in metrics.percentile_ranks(values, higher).items():
                payload[key]["percentiles"][metric] = rank
            for members in groups.values():
                subset = {k: values[k] for k in members}
                for key, rank in metrics.percentile_ranks(subset, higher).items():
                    payload[key]["percentiles_pos"][metric] = rank

    # -- piatki --------------------------------------------------------------
    def _lineups(self, ratings, league_ortg: float):
        s = self.season
        merged: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        for row in s.lineup_games + s.pair_games:
            key = (row.team, row.players)
            bucket = merged.setdefault(
                key,
                {
                    "team": row.team,
                    "players": list(row.players),
                    "size": len(row.players),
                    "secs": 0.0,
                    "off_poss": 0.0,
                    "def_poss": 0.0,
                    "pts": 0.0,
                    "opp_pts": 0.0,
                    "off": defaultdict(float),
                    "deff": defaultdict(float),
                    "clutch": defaultdict(float),
                    "long15": defaultdict(float),
                    "games": [],
                },
            )
            bucket["secs"] += row.seconds
            bucket["off_poss"] += row.off_poss
            bucket["def_poss"] += row.def_poss
            bucket["pts"] += row.points
            bucket["opp_pts"] += row.opp_points
            for k, v in row.off.items():
                bucket["off"][k] += v
            for k, v in row.deff.items():
                bucket["deff"][k] += v
            for k, v in row.clutch.items():
                bucket["clutch"][k] += v
            for k, v in row.long15.items():
                bucket["long15"][k] += v
            bucket["games"].append(
                {
                    "match_id": row.match_id,
                    "date": row.date,
                    "opp": row.opponent,
                    "secs": round(row.seconds, 1),
                    "off_poss": row.off_poss,
                    "def_poss": row.def_poss,
                    "pts": row.points,
                    "opp_pts": row.opp_points,
                    "clutch": dict(row.clutch),
                    "long15": dict(row.long15),
                }
            )

        lineups: list[dict[str, Any]] = []
        pairs: list[dict[str, Any]] = []
        for (team, members), bucket in merged.items():
            ortg = metrics.ortg(bucket["pts"], bucket["off_poss"])
            drtg = metrics.ortg(bucket["opp_pts"], bucket["def_poss"])
            entry = {
                "id": _lineup_id(team, members),
                "team": team,
                "players": list(members),
                "size": bucket["size"],
                "min": _r(bucket["secs"] / 60.0),
                "off_poss": _r(bucket["off_poss"], 0),
                "def_poss": _r(bucket["def_poss"], 0),
                "pts": bucket["pts"],
                "opp_pts": bucket["opp_pts"],
                "ortg": _r(ortg, 2),
                "drtg": _r(drtg, 2),
                "net": _r(None if ortg is None or drtg is None else ortg - drtg, 2),
                "ff": {
                    "efg": _r(metrics.efg(bucket["off"])),
                    "tov_rate": _r(metrics.pct(bucket["off"].get("tov", 0), bucket["off_poss"])),
                    "ft_rate": _r(metrics.ft_rate(bucket["off"])),
                },
                "opp_ff": {
                    "efg": _r(metrics.efg(bucket["deff"])),
                    "tov_rate": _r(metrics.pct(bucket["deff"].get("tov", 0), bucket["def_poss"])),
                    "ft_rate": _r(metrics.ft_rate(bucket["deff"])),
                },
                "clutch": _counting(bucket["clutch"]),
                "long15": _counting(bucket["long15"]),
                "fga_long_rate": _r(metrics.pct(bucket["long15"].get("fga_long", 0), bucket["long15"].get("fga", 0))),
                "ppp_long": _r(metrics.safe_div(bucket["long15"].get("pts_long", 0), bucket["long15"].get("off_poss_long", 0)), 3),
                "games": _merge_lineup_games(bucket["games"]),
            }
            if bucket["size"] == 5:
                lineups.append(entry)
            else:
                pairs.append(entry)

        lineups.sort(key=lambda e: -(e["off_poss"] + e["def_poss"]))
        pairs.sort(key=lambda e: -(e["off_poss"] + e["def_poss"]))
        return lineups, pairs


def _merge_lineup_games(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = merged.setdefault(
            row["match_id"],
            {"match_id": row["match_id"], "date": row["date"], "opp": row["opp"],
             "secs": 0.0, "off_poss": 0.0, "def_poss": 0.0, "pts": 0.0, "opp_pts": 0.0,
             "clutch": defaultdict(float), "long15": defaultdict(float)},
        )
        for k in ("secs", "off_poss", "def_poss", "pts", "opp_pts"):
            bucket[k] += float(row[k])
        for part in ("clutch", "long15"):
            for k, v in (row.get(part) or {}).items():
                bucket[part][k] += float(v)
    out = sorted(merged.values(), key=lambda r: r["date"])
    for row in out:
        ortg = metrics.ortg(row["pts"], row["off_poss"])
        drtg = metrics.ortg(row["opp_pts"], row["def_poss"])
        row["min"] = round(row["secs"] / 60.0, 1)
        row["ortg"] = _r(ortg, 1)
        row["drtg"] = _r(drtg, 1)
        row["net"] = _r(None if ortg is None or drtg is None else ortg - drtg, 1)
        row["clutch"] = _counting(row["clutch"])
        row["long15"] = _counting(row["long15"])
    return out


def _lineup_id(team: str, members: Sequence[str]) -> str:
    short = [m.split(":")[-1] for m in members]
    return team + "__" + "_".join(sorted(short))


def _value(entry: Mapping[str, Any], section: str, metric: str) -> float | None:
    part = entry.get(section) or {}
    value = part.get(metric)
    return None if value is None else float(value)


def _weighted_average(items: Sequence[tuple[float, float]]) -> float | None:
    total = sum(v * w for v, w in items)
    weight = sum(w for _, w in items)
    return total / weight if weight else None


def _league_zones(rows: Sequence[TeamGame], attr: str = "zones") -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        for zone, values in (getattr(row, attr) or {}).items():
            bucket = out.setdefault(zone, {"fga": 0.0, "fgm": 0.0, "pts": 0.0})
            for k, v in values.items():
                bucket[k] = bucket.get(k, 0.0) + float(v)
    return out
