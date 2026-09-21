"""Portrety zawodnikow z PZKosz: wyciecie tla i ujednolicenie kadru.

LiveStats podaje zdjecia 200 x 200 z szara plansza dookola. PZKosz trzyma te
same sesje w wyzszej rozdzielczosci (496 x 600) pod adresem:

    https://s1.static.esor.pzkosz.pl/internalfiles/image/zawodnicy
        /s<sezon>/<klub>/<szerokosc>-<wysokosc>/<zawodnik>.jpg

Identyfikatory sezonu, klubu i zawodnika czytamy ze strony zawodnika, zeby nie
zaszywac ich w kodzie - wystarczy podmienic rozmiar w sciezce.

Modul wymaga biblioteki Pillow. Reszta pakietu dziala bez zadnych zaleznosci
zewnetrznych, dlatego przetwarzanie zdjec jest osobnym poleceniem uruchamianym
raz na sezon, a nie czescia zwyklego `build`.
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .discover import name_tokens
from .http import Fetcher
from .pzkosz import DEFAULT_BASE

#: rozmiar, w jakim pobieramy oryginal (wiekszy zwraca 404)
SOURCE_SIZE = "600-600"

#: prostokatny portret na karty zawodnikow - proporcje 158 x 190,
#: zapisywane w podwojnej rozdzielczosci pod ekrany o duzej gestosci
PORTRAIT_SIZE = (316, 380)

#: ile wysokosci glowy ma miescic kadr portretu
PORTRAIT_HEADS = 1.75

#: margines nad glowa jako ulamek wysokosci kadru
PORTRAIT_HEADROOM = 0.09

#: zachowane dla zgodnosci z wywolaniami podajacymi pojedynczy rozmiar
OUTPUT_SIZE = PORTRAIT_SIZE[0]

#: bok kwadratowej ikony uzywanej w kolach (tabele, piatki, duety)
ICON_SIZE = 192

#: ciasnosc kadru ikony - wielokrotnosc wysokosci glowy
ICON_ZOOM = 1.25

#: format zapisu - WebP z kanalem alfa wazy kilka razy mniej niz PNG
OUTPUT_FORMAT = "WEBP"
OUTPUT_EXT = ".webp"
OUTPUT_QUALITY = 86

#: maksymalna odleglosc koloru od tla przy wypelnianiu (suma po kanalach)
TOLERANCE = 34

#: rozmycie krawedzi maski, zeby nie zostawaly schodki
FEATHER = 1.1

PHOTO_RE = re.compile(r'https://[^"\']*?/zawodnicy/s\d+/\d+/\d+-\d+/\d+\.jpg')
ROSTER_RE = re.compile(r'href="(/zawodnicy/p/(\d+)/([a-z0-9-]+)\.html)"')
TEAM_RE = re.compile(r'href="(/druzyny/d/(\d+)/([a-z0-9-]+)\.html)"')


class PillowMissing(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Przetwarzanie zdjec wymaga biblioteki Pillow: pip install pillow"
        )


def _pillow():
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:  # pragma: no cover - zalezy od srodowiska
        raise PillowMissing() from exc
    return Image, ImageFilter


# --- wyszukiwanie zrodel ------------------------------------------------------
def find_team_page(fetcher: Fetcher, club: str, base: str = DEFAULT_BASE) -> str | None:
    """Znajduje adres strony klubu po nazwie."""
    page = fetcher.get_text(base.rstrip("/") + "/druzyny.html", suffix=".html")
    wanted = name_tokens(club)
    best, score = None, 0.0
    for href, _, slug in TEAM_RE.findall(page):
        tokens = name_tokens(slug.replace("-", " "))
        if not tokens:
            continue
        overlap = len(tokens & wanted) / min(len(tokens), len(wanted))
        if overlap > score:
            best, score = href, overlap
    return base.rstrip("/") + best if best and score >= 0.5 else None


def roster(fetcher: Fetcher, team_page: str) -> list[dict[str, str]]:
    """Lista zawodnikow klubu: adres strony, identyfikator i nazwa ze sluga."""
    page = fetcher.get_text(team_page, suffix=".html")
    out: dict[str, dict[str, str]] = {}
    for href, pid, slug in ROSTER_RE.findall(page):
        out[pid] = {"url": DEFAULT_BASE + href, "id": pid, "slug": slug}
    return list(out.values())


def photo_url(fetcher: Fetcher, player_page: str, size: str = SOURCE_SIZE) -> str | None:
    """Adres zdjecia w zadanej rozdzielczosci, odczytany ze strony zawodnika."""
    page = fetcher.get_text(player_page, suffix=".html")
    match = PHOTO_RE.search(page)
    if not match:
        return None
    return re.sub(r"/\d+-\d+/", "/" + size + "/", match.group(0))


# --- obrobka ------------------------------------------------------------------
def background_alpha(img, tolerance: int = TOLERANCE):
    """Maska alfa: tlo wyznaczone wypelnieniem od krawedzi kadru.

    Prog na samym kolorze zjadlby biale wykonczenie koszulki i jasne logo.
    Wypelnienie od brzegu usuwa tylko obszar polaczony z krawedzia, wiec jasne
    elementy stroju zostaja nietkniete.
    """
    Image, ImageFilter = _pillow()
    rgb = img.convert("RGB")
    width, height = rgb.size
    px = rgb.load()

    corners = [px[1, 1], px[width - 2, 1], px[1, height - 2], px[width - 2, height - 2]]
    base = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))

    mask = bytearray(width * height)
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        r, g, b = px[x, y]
        if abs(r - base[0]) + abs(g - base[1]) + abs(b - base[2]) > tolerance:
            continue
        mask[index] = 255
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    alpha = Image.frombytes("L", (width, height), bytes(mask)).point(lambda v: 255 - v)
    return alpha.filter(ImageFilter.GaussianBlur(FEATHER))


def head_box(alpha):
    """Prostokat glowy: od czubka do linii, gdzie sylwetka zaczyna sie rozszerzac.

    Szerokosc kolejnych wierszy maski rosnie skokowo na wysokosci ramion -
    to wystarczy, zeby oddzielic glowe bez zadnego rozpoznawania twarzy.
    """
    width, height = alpha.size
    px = alpha.load()
    rows = []
    for y in range(height):
        xs = [x for x in range(0, width, 2) if px[x, y] > 128]
        rows.append((xs[0], xs[-1]) if xs else None)

    filled = [(y, r) for y, r in enumerate(rows) if r]
    if not filled:
        return None

    top = filled[0][0]
    head_rows = [r for _, r in filled[: max(1, len(filled) // 5)]]
    widths = sorted(r[1] - r[0] for r in head_rows)
    head_width = widths[len(widths) // 2]

    bottom = filled[-1][0]
    for y, span in filled:
        if y > top + head_width * 0.4 and (span[1] - span[0]) > head_width * 1.55:
            bottom = y
            break

    left = min(r[0] for y, r in filled if top <= y <= bottom)
    right = max(r[1] for y, r in filled if top <= y <= bottom)
    return left, top, right, bottom


def head_icon(img, size: int = ICON_SIZE, zoom: float = ICON_ZOOM):
    """Ciasny kwadratowy kadr na glowe - do awatarow w kolach."""
    Image, _ = _pillow()
    box = head_box(img.split()[-1])
    if not box:
        return img.resize((size, size), Image.LANCZOS)

    left, top, right, bottom = box
    height = bottom - top
    side = int(height * zoom)
    center_x = (left + right) // 2
    center_y = top + height // 2
    x0 = center_x - side // 2
    y0 = center_y - int(side * 0.47)      # glowa odrobine powyzej srodka kola

    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img.crop((x0, y0, x0 + side, y0 + side)), (0, 0))
    return out.resize((size, size), Image.LANCZOS)


def portrait(img, size: tuple[int, int] = PORTRAIT_SIZE,
             heads: float = PORTRAIT_HEADS, headroom: float = PORTRAIT_HEADROOM):
    """Prostokatny portret zakotwiczony na glowie, w proporcjach 158 x 190.

    Wysokosc kadru liczymy w wysokosciach glowy, a nie w pikselach zrodla -
    dzieki temu wszyscy zawodnicy maja te sama skale twarzy niezaleznie od
    tego, jak ciasno ustawiono aparat na sesji.
    """
    Image, _ = _pillow()
    box = head_box(img.split()[-1])
    if not box:
        return img.resize(size, Image.LANCZOS)

    left, top, right, bottom = box
    head_height = bottom - top
    frame_h = int(head_height * heads)
    frame_w = int(frame_h * size[0] / size[1])
    center_x = (left + right) // 2
    y0 = int(top - frame_h * headroom)

    out = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    out.paste(img.crop((center_x - frame_w // 2, y0,
                        center_x - frame_w // 2 + frame_w, y0 + frame_h)), (0, 0))
    return out.resize(size, Image.LANCZOS)


def _encode(img) -> bytes:
    import io

    buffer = io.BytesIO()
    img.save(buffer, format=OUTPUT_FORMAT, quality=OUTPUT_QUALITY, method=4)
    return buffer.getvalue()


def cut_out(data: bytes, width: int | None = None, icon: int = ICON_SIZE) -> tuple[bytes, bytes]:
    """Z pobranego JPEG-a robi portret i ikone, obie z przezroczystym tlem."""
    import io

    Image, _ = _pillow()
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img.putalpha(background_alpha(img))
    size = PORTRAIT_SIZE if width is None else (width, round(width * PORTRAIT_SIZE[1] / PORTRAIT_SIZE[0]))
    return _encode(portrait(img, size)), _encode(head_icon(img, icon))


# --- calosc -------------------------------------------------------------------
def build_photos(
    fetcher: Fetcher,
    club: str,
    players: Iterable[dict[str, Any]],
    dest: Path,
    *,
    size: int = OUTPUT_SIZE,
    base: str = DEFAULT_BASE,
    log=print,
) -> dict[str, str]:
    """Pobiera i obrabia portrety zawodnikow klubu.

    Zwraca mapowanie klucz zawodnika -> nazwa zapisanego pliku.
    """
    team_page = find_team_page(fetcher, club, base)
    if not team_page:
        log("nie znaleziono strony klubu dla: {}".format(club))
        return {}

    squad = roster(fetcher, team_page)
    log("sklad na stronie klubu: {} zawodnikow".format(len(squad)))

    by_tokens = {frozenset(name_tokens(p["slug"].replace("-", " "))): p for p in squad}
    dest.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    for player in players:
        tokens = frozenset(name_tokens(player.get("name", "")))
        entry = by_tokens.get(tokens)
        if entry is None:  # dopasowanie luzniejsze, gdy roznia sie drugie imiona
            entry = next(
                (p for key, p in by_tokens.items() if key & tokens and len(key & tokens) >= 2),
                None,
            )
        if entry is None:
            log("brak w skladzie PZKosz: {}".format(player.get("name")))
            continue

        url = photo_url(fetcher, entry["url"])
        if not url:
            log("brak zdjecia: {}".format(player.get("name")))
            continue

        stem = player["key"].replace(":", "__")
        try:
            body, icon = cut_out(fetcher.get(url, suffix=".jpg"), size)
        except PillowMissing:
            raise
        except Exception as exc:  # pragma: no cover - siec albo uszkodzony plik
            log("nie udalo sie przetworzyc {}: {}".format(player.get("name"), exc))
            continue
        (dest / (stem + OUTPUT_EXT)).write_bytes(body)
        (dest / (stem + "-icon" + OUTPUT_EXT)).write_bytes(icon)
        written[player["key"]] = stem + OUTPUT_EXT
        log("zapisano {} (+ ikona)".format(stem + OUTPUT_EXT))
    return written
