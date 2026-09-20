"""Geometria boiska FIBA i klasyfikacja stref rzutowych.

Genius Sports / FIBA LiveStats podaje wspolrzedne rzutu jako procent wymiarow
calego boiska: x w zakresie 0-100 wzdluz dlugosci (28 m), y w zakresie 0-100
wzdluz szerokosci (15 m). Kosz lezy 1.575 m od linii koncowej, na srodku
szerokosci, czyli w (x=5.625, y=50) dla polowy "lewej" i (x=94.375, y=50) dla
"prawej". Rzuty z drugiej polowy lustrzanie odbijamy na jedna polowe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- wymiary boiska FIBA (metry) ---------------------------------------------
COURT_LENGTH = 28.0
COURT_WIDTH = 15.0
HOOP_FROM_BASELINE = 1.575
KEY_HALF_WIDTH = 2.45          # szerokosc pola 4.9 m
FREE_THROW_LINE = 5.80         # od linii koncowej
THREE_ARC_RADIUS = 6.75
THREE_CORNER_Y = 6.60          # 0.90 m od linii bocznej -> 7.5 - 0.90
RESTRICTED_AREA_RADIUS = 1.25  # polkole 1.25 m
RIM_ZONE_RADIUS = 1.80         # "rim" na potrzeby analityki (nieco szerzej)
SHORT_MID_RADIUS = 4.50

#: x, przy ktorym luk za 3 styka sie z prostym odcinkiem naroznika
CORNER_ARC_X = math.sqrt(THREE_ARC_RADIUS ** 2 - THREE_CORNER_Y ** 2)

#: pas naroznika - rzuty z tego obszaru liczymy jako "corner 3".
#: protokolanci klikaja z rozrzutem, wiec bierzemy nieco szerzej niz czysta geometria
CORNER_BAND_Y = 6.20
CORNER_BAND_X = 3.20

ZONES = [
    "RIM",
    "PAINT",
    "SHORT_MID",
    "LONG_MID",
    "CORNER_3",
    "ABOVE_BREAK_3",
]

ZONE_LABELS_PL = {
    "RIM": "Spod kosza",
    "PAINT": "Pomalowane (poza RA)",
    "SHORT_MID": "Bliski srednidystans",
    "LONG_MID": "Daleki sredni dystans",
    "CORNER_3": "Trojka z naroznika",
    "ABOVE_BREAK_3": "Trojka czolowa",
}

ZONE_POINT_VALUE = {
    "RIM": 2,
    "PAINT": 2,
    "SHORT_MID": 2,
    "LONG_MID": 2,
    "CORNER_3": 3,
    "ABOVE_BREAK_3": 3,
}


@dataclass(frozen=True)
class ShotLocation:
    """Pozycja rzutu sprowadzona do jednej polowy boiska."""

    #: metry od linii koncowej wzdluz dlugosci boiska (kosz = 1.575)
    x_m: float
    #: metry od lewej linii bocznej (srodek = 7.5)
    y_m: float
    #: metry od srodka obreczy, wzdluz dlugosci (dodatnie = w strone srodka)
    dx: float
    #: metry od osi kosza w poprzek boiska (dodatnie = w prawo)
    dy: float
    #: odleglosc od srodka obreczy w metrach
    distance: float
    #: kat wzgledem osi kosza w stopniach (0 = prosto na czolo, +/-90 = naroznik)
    angle: float
    #: znormalizowany x/y w skali 0-100 na polowie boiska (do rysowania)
    half_x: float
    half_y: float


def normalize(x: float, y: float) -> ShotLocation:
    """Sprowadza surowe wspolrzedne 0-100 do ukladu jednej polowy boiska."""
    if x > 50.0:
        x = 100.0 - x
        y = 100.0 - y
    x_m = x / 100.0 * COURT_LENGTH
    y_m = y / 100.0 * COURT_WIDTH
    dx = x_m - HOOP_FROM_BASELINE
    dy = y_m - COURT_WIDTH / 2.0
    distance = math.hypot(dx, dy)
    # 0 stopni = prosto na czolo kosza, +90 = prawa linia boczna,
    # wartosci powyzej |90| to rzuty zza linii kosza
    angle = math.degrees(math.atan2(dy, dx))
    return ShotLocation(
        x_m=round(x_m, 3),
        y_m=round(y_m, 3),
        dx=round(dx, 3),
        dy=round(dy, 3),
        distance=round(distance, 3),
        angle=round(angle, 1),
        half_x=round(x * 2.0, 3),
        half_y=round(y, 3),
    )


def is_geometric_three(loc: ShotLocation) -> bool:
    """Czy pozycja lezy za linia 6.75 wedlug samej geometrii."""
    if abs(loc.dy) >= THREE_CORNER_Y and loc.dx <= CORNER_ARC_X:
        return True
    return loc.distance >= THREE_ARC_RADIUS


def classify(loc: ShotLocation, is_three: bool | None = None) -> str:
    """Zwraca strefe rzutowa.

    ``is_three`` pochodzi z pola ``actionType`` (2pt/3pt) i ma pierwszenstwo nad
    geometria - protokolant myli sie rzadziej niz piksel na tablecie.
    """
    if is_three is None:
        is_three = is_geometric_three(loc)

    if is_three:
        # naroznik: rzut oddany w pasie przy linii bocznej, przed zalamaniem luku
        if abs(loc.dy) >= CORNER_BAND_Y and loc.dx <= CORNER_BAND_X:
            return "CORNER_3"
        return "ABOVE_BREAK_3"

    if loc.distance <= RIM_ZONE_RADIUS:
        return "RIM"
    in_key = abs(loc.dy) <= KEY_HALF_WIDTH and -0.2 <= loc.x_m <= FREE_THROW_LINE
    if in_key:
        return "PAINT"
    if loc.distance <= SHORT_MID_RADIUS:
        return "SHORT_MID"
    return "LONG_MID"


def hex_bin(loc: ShotLocation, size: float = 1.0) -> tuple[int, int]:
    """Kubelkuje rzut do siatki heksagonalnej o zadanym boku (metry)."""
    q = (math.sqrt(3) / 3 * loc.dy - loc.dx / 3) / size
    r = (2.0 / 3 * loc.dx) / size
    return _hex_round(q, r)


def _hex_round(q: float, r: float) -> tuple[int, int]:
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


# --- szczegolowa siatka stref (uklad zblizony do NBA.com/stats) ---------------
#: granice sektorow katowych dla sredniego dystansu (5 sektorow)
MID_SECTORS = [(-180.0, -54.0, "L"), (-54.0, -18.0, "LC"), (-18.0, 18.0, "C"),
               (18.0, 54.0, "RC"), (54.0, 180.0, "R")]
#: granice sektorow katowych dla trojek czolowych (3 sektory)
ARC_SECTORS = [(-180.0, -22.0, "L"), (-22.0, 22.0, "C"), (22.0, 180.0, "R")]

#: promien, od ktorego zaczyna sie daleki sredni dystans
LONG_MID_RADIUS = 4.50

DETAILED_ZONES = [
    "RA",
    "PAINT",
    "SM_L", "SM_R",
    "LM_L", "LM_LC", "LM_C", "LM_RC", "LM_R",
    "C3_L", "C3_R",
    "AB3_L", "AB3_C", "AB3_R",
]

DETAILED_LABELS_PL = {
    "RA": "Podkoszowe",
    "PAINT": "Pomalowane",
    "SM_L": "Bliski dystans lewa",
    "SM_R": "Bliski dystans prawa",
    "LM_L": "Sredni lewa",
    "LM_LC": "Sredni lewe skrzydlo",
    "LM_C": "Sredni czolo",
    "LM_RC": "Sredni prawe skrzydlo",
    "LM_R": "Sredni prawa",
    "C3_L": "Trojka lewy naroznik",
    "C3_R": "Trojka prawy naroznik",
    "AB3_L": "Trojka lewe skrzydlo",
    "AB3_C": "Trojka z czola",
    "AB3_R": "Trojka prawe skrzydlo",
}

#: przypisanie strefy szczegolowej do strefy zbiorczej
DETAILED_TO_ZONE = {
    "RA": "RIM", "PAINT": "PAINT",
    "SM_L": "SHORT_MID", "SM_R": "SHORT_MID",
    "LM_L": "LONG_MID", "LM_LC": "LONG_MID", "LM_C": "LONG_MID",
    "LM_RC": "LONG_MID", "LM_R": "LONG_MID",
    "C3_L": "CORNER_3", "C3_R": "CORNER_3",
    "AB3_L": "ABOVE_BREAK_3", "AB3_C": "ABOVE_BREAK_3", "AB3_R": "ABOVE_BREAK_3",
}


def _sector(angle: float, sectors) -> str:
    for low, high, name in sectors:
        if low <= angle < high:
            return name
    return sectors[-1][2]


def classify_detailed(loc: ShotLocation, is_three: bool | None = None) -> str:
    """Strefa w siatce szczegolowej - podstawa mapy rzutow w portalu.

    Podzial jest ten sam co w ``classify``, tylko dokladniejszy: sredni dystans
    i trojki czolowe dziela sie dodatkowo na sektory katowe, dzieki czemu widac
    strone boiska, z ktorej padaja rzuty.
    """
    if is_three is None:
        is_three = is_geometric_three(loc)

    if is_three:
        if abs(loc.dy) >= CORNER_BAND_Y and loc.dx <= CORNER_BAND_X:
            return "C3_L" if loc.dy < 0 else "C3_R"
        return "AB3_" + _sector(loc.angle, ARC_SECTORS)

    if loc.distance <= RESTRICTED_AREA_RADIUS:
        return "RA"
    if abs(loc.dy) <= KEY_HALF_WIDTH and -0.2 <= loc.x_m <= FREE_THROW_LINE:
        return "PAINT"
    if loc.distance <= LONG_MID_RADIUS:
        return "SM_L" if loc.dy < 0 else "SM_R"
    return "LM_" + _sector(loc.angle, MID_SECTORS)
