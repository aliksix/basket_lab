"""Zapis danych portalu do katalogu statycznej strony (GitHub Pages).

Rozdzial obowiazkow jest prosty: ``build`` liczy, ``site`` zapisuje. Przegladarka
dostaje surowe wiersze meczowe (zeby moc filtrowac: ostatnie 5, dom, wyjazd,
pojedynczy mecz) oraz gotowe wskazniki sezonowe, ktorych nie da sie policzyc
bez calej ligi (ratingi skorygowane, percentyle, model wplywu).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import metrics
from .build import (
    MIN_LINEUP_POSSESSIONS,
    MIN_PAIR_POSSESSIONS,
    BuildConfig,
    SiteBuilder,
    _counting,
    _r,
    _write,
)
from .court import ZONES
from .glossary import GLOSSARY, ZONE_GLOSSARY
from .http import Fetcher
from .season import Season


def write_site(builder: SiteBuilder, payload: Mapping[str, Any], log=print) -> None:
    """Zapisuje komplet plikow JSON do katalogu strony."""
    cfg = builder.cfg
    s = builder.season
    out = cfg.out_dir
    club = builder.club_key
    teams = payload["teams"]
    players = payload["players"]

    if cfg.download_assets:
        download_assets(builder, teams, players, log=log)

    club_players = {k: v for k, v in players.items() if v.get("team") == club}
    club_lineups = [l for l in payload["lineups"] if l["team"] == club]
    club_pairs = [p for p in payload["pairs"] if p["team"] == club]

    _write(
        out / "meta.json",
        {
            "club": {
                "key": club,
                "name": cfg.club_display,
                "official": teams.get(club, {}).get("name", cfg.club),
                "logo": teams.get(club, {}).get("logo", ""),
                "coach": teams.get(club, {}).get("coach", ""),
            },
            "competition": cfg.competition,
            "season": cfg.season,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "games_played": teams.get(club, {}).get("gp", 0),
            "league_games": len(s.games),
            "teams": [
                {"key": k, "name": v["name"], "short": v.get("short", ""), "logo": v.get("logo", "")}
                for k, v in sorted(teams.items(), key=lambda kv: kv[1]["name"])
            ],
            "zones": ZONES,
            "sources": [
                "FIBA LiveStats (Genius Sports) — boxscore, play-by-play, współrzędne rzutów",
                "PZKosz 1 Liga Mężczyzn — terminarz, wyniki, zapasowe play-by-play",
            ],
            "warnings": s.warnings[:200],
        },
    )

    _write(out / "league.json", {"teams": list(teams.values()), "league": payload["league"]})

    _write(
        out / "league_games.json",
        [
            {
                "match_id": r.match_id,
                "date": r.date,
                "round": r.round_no,
                "team": r.team,
                "opp": r.opponent,
                "home": r.home,
                "pts": r.points,
                "opp_pts": r.opp_points,
                "poss": _r(r.poss, 1),
                "opp_poss": _r(r.opp_poss, 1),
                "kill_shots": r.kill_shots,
                "kill_allowed": r.kill_allowed,
                "stats": _counting(r.stats),
                "opp_stats": _counting(r.opp_stats),
                "zones": {z: _counting(v) for z, v in (r.zones or {}).items()},
                "opp_zones": {z: _counting(v) for z, v in (r.opp_zones or {}).items()},
                "zones14": {z: _counting(v) for z, v in (r.zones14 or {}).items()},
                "opp_zones14": {z: _counting(v) for z, v in (r.opp_zones14 or {}).items()},
                "clutch": _counting(r.clutch or {}),
                "long15": _counting(r.long15 or {}),
            }
            for r in s.team_games
        ],
    )

    _write(
        out / "club.json",
        {**teams.get(club, {}), "games": [g for g in s.games if club in (g["home"], g["away"])]},
    )

    _write(
        out / "players.json",
        [player_tile(v) for v in sorted(club_players.values(), key=lambda p: -(p.get("min") or 0))],
    )

    for key, entry in club_players.items():
        _write(
            out / "player" / (slug(key) + ".json"),
            {**entry, "shots": [sh for sh in s.shots if sh["player"] == key]},
        )

    # wysylamy komplet piatek - prog posiadan ustawia sie w interfejsie
    _write(
        out / "lineups.json",
        [{k: v for k, v in lineup.items() if k != "games"} for lineup in club_lineups],
    )
    for lineup in club_lineups:
        _write(
            out / "lineup" / (lineup["id"] + ".json"),
            {**lineup, "matchups": lineup_matchups(s, lineup)},
        )

    _write(out / "pairs.json", [{k: v for k, v in p.items() if k != "games"} for p in club_pairs])

    # pelne play-by-play meczow klubu - podstawa przegladu przebiegu meczu
    club_matches = [g["match_id"] for g in s.games if club in (g["home"], g["away"])]
    for match_id in club_matches:
        payload_pbp = s.playbyplay.get(match_id)
        if payload_pbp:
            _write(out / "pbp" / (match_id + ".json"), payload_pbp)
    _write(out / "shots.json", [sh for sh in s.shots if sh["team"] == club])
    _write(out / "glossary.json", {"metrics": GLOSSARY, "zones": ZONE_GLOSSARY})
    log("zapisano dane portalu do {}".format(out))


def player_tile(entry: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("key", "name", "short", "shirt", "position", "photo", "team", "gp", "gs", "min")
    return {
        **{k: entry.get(k) for k in keep},
        "metrics": entry.get("metrics", {}),
        "impact": entry.get("impact", {}),
        "on_off": entry.get("on_off", {}),
        "percentiles": entry.get("percentiles", {}),
        "percentiles_pos": entry.get("percentiles_pos", {}),
    }


def lineup_matchups(s: Season, lineup: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Jak piatka spisywala sie przeciwko konkretnym piatkom rywali."""
    members = tuple(sorted(lineup["players"]))
    rows: dict[tuple[str, ...], dict[str, Any]] = {}

    def bucket_for(other: tuple[str, ...]) -> dict[str, Any]:
        return rows.setdefault(
            other,
            {
                "opp_players": list(other),
                "off_poss": 0.0,
                "pts": 0.0,
                "def_poss": 0.0,
                "opp_pts": 0.0,
                "secs": 0.0,
            },
        )

    for (team, off_lineup, def_lineup), values in s.matchups.items():
        if team == lineup["team"] and off_lineup == members:
            bucket = bucket_for(def_lineup)
            bucket["off_poss"] += values["poss"]
            bucket["pts"] += values["pts"]
            bucket["secs"] += values["secs"]
        elif team != lineup["team"] and def_lineup == members:
            bucket = bucket_for(off_lineup)
            bucket["def_poss"] += values["poss"]
            bucket["opp_pts"] += values["pts"]
            bucket["secs"] += values["secs"]

    out = []
    for bucket in rows.values():
        ortg = metrics.ortg(bucket["pts"], bucket["off_poss"])
        drtg = metrics.ortg(bucket["opp_pts"], bucket["def_poss"])
        bucket["min"] = round(bucket["secs"] / 60.0, 1)
        bucket["ortg"] = _r(ortg, 1)
        bucket["drtg"] = _r(drtg, 1)
        bucket["net"] = _r(None if ortg is None or drtg is None else ortg - drtg, 1)
        out.append(bucket)
    out.sort(key=lambda r: -(r["off_poss"] + r["def_poss"]))
    return out[:40]


def slug(player_key: str) -> str:
    return player_key.replace(":", "__")


# --- zasoby graficzne ---------------------------------------------------------
def download_assets(builder: SiteBuilder, teams: dict[str, Any], players: dict[str, Any], log=print) -> None:
    """Sciaga herby i zdjecia, zeby strona nie zalezala od serwerow Genius."""
    cfg = builder.cfg
    logos = cfg.assets_dir / "logos"
    photos = cfg.assets_dir / "players"
    logos.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    prefix = assets_prefix(cfg)
    saved = 0

    for key, team in teams.items():
        url = team.get("logo") or ""
        if not url.startswith("http"):
            continue
        dest = logos / (key + suffix_of(url, ".png"))
        if save(builder.fetcher, url, dest):
            team["logo"] = prefix + "logos/" + dest.name
            saved += 1

    for key, player in players.items():
        if player.get("team") != builder.club_key:
            continue
        url = player.get("photo") or ""
        if not url.startswith("http"):
            continue
        dest = photos / (slug(key) + suffix_of(url, ".jpg"))
        if save(builder.fetcher, url, dest):
            player["photo"] = prefix + "players/" + dest.name
            saved += 1
    log("pobrano zasoby graficzne: {}".format(saved))


def assets_prefix(cfg: BuildConfig) -> str:
    """Sciezka do zasobow widziana ze strony HTML (katalog ``docs``)."""
    try:
        return cfg.assets_dir.relative_to(cfg.out_dir.parent).as_posix().rstrip("/") + "/"
    except ValueError:
        return "assets/"


def suffix_of(url: str, default: str) -> str:
    tail = url.rsplit(".", 1)[-1].lower()
    return "." + tail if tail in ("png", "jpg", "jpeg", "webp", "gif") else default


def save(fetcher: Fetcher, url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        data = fetcher.get(url, suffix=".img")
    except Exception:
        return False
    if not data:
        return False
    dest.write_bytes(data)
    return True
