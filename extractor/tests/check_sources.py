"""Porownanie play-by-play z obu zrodel dla tego samego meczu (wymaga sieci).

    python extractor/tests/check_sources.py 2905344 223889
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basketlab import fiba, pzkosz
from basketlab.http import Fetcher

fiba_id = sys.argv[1] if len(sys.argv) > 1 else "2905344"
pz_id = sys.argv[2] if len(sys.argv) > 2 else "223889"

fetcher = Fetcher("data/raw/cache")
a = fiba.load(fiba_id, fetcher)
b = pzkosz.load_playbyplay(
    "https://1lm.pzkosz.pl/mecz/{}/index.html".format(pz_id), fetcher
)


def summary(game):
    counts = Counter()
    for ev in game.pbp:
        if ev.action in ("2pt", "3pt", "freethrow"):
            counts[(ev.action, "celny" if ev.success else "niecelny")] += 1
        elif ev.action in ("rebound", "turnover", "assist", "steal", "block", "substitution"):
            counts[(ev.action, "")] += 1
    return counts


left, right = summary(a), summary(b)
print("{:<24} {:>8} {:>8}".format("akcja", "FIBA", "PZKosz"))
for key in sorted(set(left) | set(right)):
    label = " ".join(x for x in key if x)
    mark = "" if left[key] == right[key] else "   <-- roznica"
    print("{:<24} {:>8} {:>8}{}".format(label, left[key], right[key], mark))
print()
print("zdarzen:", len(a.pbp), "vs", len(b.pbp))
print("wynik:", a.teams[1].score, ":", a.teams[2].score, "vs", b.teams[1].score, ":", b.teams[2].score)
