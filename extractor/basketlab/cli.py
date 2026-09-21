"""Interfejs wiersza polecen ekstraktora.

    python -m basketlab game <url|id>        - jeden mecz do JSON-a
    python -m basketlab pbp <url|id>         - samo play-by-play (FIBA lub PZKosz)
    python -m basketlab schedule             - terminarz sezonu
    python -m basketlab discover             - mapowanie terminarz -> LiveStats
    python -m basketlab build                - komplet danych dla portalu
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import discover as discover_mod
from . import fiba, photos as photos_mod, pzkosz
from .build import BuildConfig, SiteBuilder
from .http import Fetcher
from .site import write_site

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "extractor" / "config.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit("Brak pliku konfiguracyjnego: {}".format(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _fetcher(cfg: dict[str, Any], args) -> Fetcher:
    cache = ROOT / cfg.get("cache_dir", "data/raw/cache")
    return Fetcher(cache, ttl=None if not args.refresh else 0.0)


def _dump(payload: Any, out: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("zapisano {}".format(out))
    else:
        sys.stdout.write(text + "\n")


# --- polecenia ----------------------------------------------------------------
def cmd_game(args, cfg) -> None:
    fetcher = _fetcher(cfg, args)
    game = fiba.load(args.match, fetcher, force=args.refresh)
    payload = game.to_dict()
    if args.raw:
        out = Path(args.out) if args.out else ROOT / "data" / "raw" / (game.match_id + ".json")
        fiba.save_raw(game.match_id, fetcher, out, force=args.refresh)
        return
    _dump(payload, Path(args.out) if args.out else None)


def cmd_pbp(args, cfg) -> None:
    fetcher = _fetcher(cfg, args)
    target = args.match
    if "pzkosz" in target or args.source == "pzkosz":
        game = pzkosz.load_playbyplay(target, fetcher, force=args.refresh)
    else:
        game = fiba.load(target, fetcher, force=args.refresh)
    rows = [asdict(e) for e in game.pbp]
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
            writer.writeheader()
            for row in rows:
                row["qualifiers"] = ",".join(row.get("qualifiers") or [])
                writer.writerow(row)
        print("zapisano {} zdarzen do {}".format(len(rows), out))
        return
    _dump(
        {
            "match_id": game.match_id,
            "source": game.source,
            "teams": {str(t): game.teams[t].name for t in game.teams},
            "events": rows,
            "shots": [asdict(s) for s in game.shots],
        },
        Path(args.out) if args.out else None,
    )


def cmd_shots(args, cfg) -> None:
    fetcher = _fetcher(cfg, args)
    game = fiba.load(args.match, fetcher, force=args.refresh)
    _dump([asdict(s) for s in game.shots], Path(args.out) if args.out else None)


def cmd_schedule(args, cfg) -> None:
    fetcher = _fetcher(cfg, args)
    base = args.base or cfg.get("pzkosz_base", pzkosz.DEFAULT_BASE)
    if args.seasons:
        _dump(pzkosz.fetch_seasons(fetcher, base, force=args.refresh), Path(args.out) if args.out else None)
        return
    archive = args.archive if args.archive is not None else cfg.get("archive_id")
    schedule = pzkosz.fetch_schedule(fetcher, base, archive_id=archive, force=args.refresh)
    _dump(schedule, Path(args.out) if args.out else None)


def cmd_discover(args, cfg) -> None:
    fetcher = _fetcher(cfg, args)
    base = args.base or cfg.get("pzkosz_base", pzkosz.DEFAULT_BASE)
    archive = args.archive if args.archive is not None else cfg.get("archive_id")
    schedule = pzkosz.fetch_schedule(fetcher, base, archive_id=archive, force=args.refresh)
    registry_path = Path(args.registry) if args.registry else ROOT / cfg["registry"]
    registry = discover_mod.Registry.load(registry_path)
    registry.season = args.season or cfg.get("season", "")
    registry.competition = cfg.get("competition", "")

    raw_range = args.range or cfg.get("scan_range")
    scan_range = None
    if raw_range:
        lo, hi = (int(v) for v in str(raw_range).split("-"))
        scan_range = (lo, hi)

    def log(message: str) -> None:
        print(message, flush=True)
        registry.save(registry_path)

    discover_mod.resolve_season(
        schedule,
        registry,
        scan_range=scan_range,
        coarse_step=args.step,
        expand=args.expand,
        window=args.window,
        rounds=args.rounds,
        workers=args.workers,
        force_scan=args.rescan or bool(args.range),
        log=log,
    )
    registry.save(registry_path)
    print("dopasowano {}/{} meczow".format(len(registry.resolved), sum(1 for g in schedule if g["finished"])))


def cmd_add(args, cfg) -> None:
    """Recznie dopisuje mecz do rejestru (gdy znamy identyfikator LiveStats)."""
    registry_path = Path(args.registry) if args.registry else ROOT / cfg["registry"]
    registry = discover_mod.Registry.load(registry_path)
    fiba_id = int(fiba.parse_match_id(args.match))
    fetcher = _fetcher(cfg, args)
    game = fiba.load(str(fiba_id), fetcher)
    registry.matches = [m for m in registry.matches if int(m.get("fiba_id") or 0) != fiba_id]
    registry.matches.append(
        {
            "pzkosz_id": args.pzkosz_id or "",
            "round": args.round,
            "date": args.date or "",
            "home": game.teams[1].name,
            "away": game.teams[2].name,
            "home_score": game.teams[1].score,
            "away_score": game.teams[2].score,
            "finished": True,
            "fiba_id": fiba_id,
        }
    )
    registry.save(registry_path)
    print("dopisano mecz {} ({} {}:{} {})".format(fiba_id, game.teams[1].name, game.teams[1].score, game.teams[2].score, game.teams[2].name))


def cmd_photos(args, cfg) -> None:
    """Pobiera portrety z PZKosz i zapisuje je z przezroczystym tlem."""
    fetcher = _fetcher(cfg, args)
    out_dir = ROOT / cfg.get("out_dir", "docs/data")
    assets = ROOT / cfg.get("assets_dir", "docs/assets") / "players"
    players_file = out_dir / "players.json"
    if not players_file.exists():
        raise SystemExit("Najpierw uruchom `basketlab build` - brak {}".format(players_file))

    players = json.loads(players_file.read_text(encoding="utf-8"))
    written = photos_mod.build_photos(
        fetcher,
        cfg["club"]["official"],
        players,
        assets,
        size=args.size,
        base=cfg.get("pzkosz_base", pzkosz.DEFAULT_BASE),
    )
    print("przetworzono {} z {} zawodnikow".format(len(written), len(players)))
    if written:
        print("uruchom ponownie `basketlab build`, zeby profile wskazaly nowe pliki")


def cmd_verify(args, cfg) -> None:
    registry_path = Path(args.registry) if args.registry else ROOT / cfg["registry"]
    registry = discover_mod.Registry.load(registry_path)
    before = len(registry.matches)
    dropped = discover_mod.verify_registry(registry, workers=args.workers)
    registry.save(registry_path)
    print("sprawdzono {} wpisow, usunieto {}".format(before, dropped))


def cmd_build(args, cfg) -> None:
    config = BuildConfig(
        club=cfg["club"]["official"],
        club_display=cfg["club"]["name"],
        competition=cfg.get("competition", ""),
        season=args.season or cfg.get("season", ""),
        registry_path=Path(args.registry) if args.registry else ROOT / cfg["registry"],
        out_dir=Path(args.out) if args.out else ROOT / cfg.get("out_dir", "docs/data"),
        cache_dir=ROOT / cfg.get("cache_dir", "data/raw/cache"),
        assets_dir=ROOT / cfg.get("assets_dir", "docs/assets"),
        download_assets=not args.no_assets,
        limit=args.limit,
    )
    builder = SiteBuilder(config)
    try:
        builder.schedule = pzkosz.fetch_schedule(
            _fetcher(cfg, args),
            cfg.get("pzkosz_base", pzkosz.DEFAULT_BASE),
            archive_id=cfg.get("archive_id"),
        )
    except Exception as exc:  # pragma: no cover - siec
        print("nie udalo sie pobrac terminarza: {}".format(exc))
    builder.load()
    payload = builder.build()
    write_site(builder, payload)
    if builder.season.warnings:
        print("ostrzezenia ({}):".format(len(builder.season.warnings)))
        for warning in builder.season.warnings[:15]:
            print("  - " + warning)


# --- parser -------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="basketlab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--refresh", action="store_true", help="pomija cache i pobiera dane od nowa")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("game", help="pobiera caly mecz z FIBA LiveStats")
    p.add_argument("match", help="URL albo identyfikator meczu")
    p.add_argument("--out")
    p.add_argument("--raw", action="store_true", help="zapisuje surowy data.json")
    p.set_defaults(func=cmd_game)

    p = sub.add_parser("pbp", help="play-by-play z FIBA LiveStats albo PZKosz")
    p.add_argument("match")
    p.add_argument("--source", choices=("fiba", "pzkosz"), default="fiba")
    p.add_argument("--out")
    p.add_argument("--csv")
    p.set_defaults(func=cmd_pbp)

    p = sub.add_parser("shots", help="mapa rzutow jednego meczu")
    p.add_argument("match")
    p.add_argument("--out")
    p.set_defaults(func=cmd_shots)

    p = sub.add_parser("schedule", help="terminarz i wyniki z PZKosz")
    p.add_argument("--archive", help="identyfikator archiwalnego sezonu")
    p.add_argument("--base")
    p.add_argument("--seasons", action="store_true", help="lista dostepnych sezonow")
    p.add_argument("--out")
    p.set_defaults(func=cmd_schedule)

    p = sub.add_parser("discover", help="mapuje terminarz na identyfikatory LiveStats")
    p.add_argument("--archive")
    p.add_argument("--base")
    p.add_argument("--registry")
    p.add_argument("--season")
    p.add_argument("--range", help="zakres skanu, np. 2620000-2790000")
    p.add_argument("--step", type=int, default=20)
    p.add_argument("--expand", type=int, default=260)
    p.add_argument("--window", type=int, default=1400)
    p.add_argument("--rounds", type=int, default=12)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--rescan", action="store_true", help="powtarza skan zgrubny mimo wpisow w rejestrze")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("add", help="recznie dopisuje mecz do rejestru")
    p.add_argument("match")
    p.add_argument("--registry")
    p.add_argument("--pzkosz-id", dest="pzkosz_id")
    p.add_argument("--date")
    p.add_argument("--round", type=int)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("photos", help="portrety z PZKosz z przezroczystym tlem (wymaga Pillow)")
    p.add_argument("--size", type=int, default=photos_mod.OUTPUT_SIZE)
    p.set_defaults(func=cmd_photos)

    p = sub.add_parser("verify", help="sprawdza poprawnosc wpisow w rejestrze")
    p.add_argument("--registry")
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("build", help="buduje dane portalu")
    p.add_argument("--registry")
    p.add_argument("--season")
    p.add_argument("--out")
    p.add_argument("--limit", type=int)
    p.add_argument("--no-assets", action="store_true")
    p.set_defaults(func=cmd_build)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config))
    args.func(args, cfg)


if __name__ == "__main__":
    main()
