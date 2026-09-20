"""Testy jednostkowe ekstraktora - bez dostepu do sieci.

    python -m unittest discover -s extractor/tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basketlab import court, fiba, metrics, pzkosz  # noqa: E402
from basketlab.possessions import split_possessions  # noqa: E402


class CourtZones(unittest.TestCase):
    """Wspolrzedne LiveStats to procenty calego boiska 28 x 15 m."""

    def zone(self, x: float, y: float, three: bool) -> str:
        return court.classify(court.normalize(x, y), three)

    def test_layup_to_rim(self):
        self.assertEqual(self.zone(5.96, 44.46, False), "RIM")

    def test_mirrors_far_half(self):
        near = court.normalize(5.96, 44.46)
        far = court.normalize(94.04, 55.54)
        self.assertAlmostEqual(near.distance, far.distance, places=3)

    def test_corner_three(self):
        self.assertEqual(self.zone(5.18, 2.09, True), "CORNER_3")

    def test_wing_three(self):
        self.assertEqual(self.zone(29.4, 36.0, True), "ABOVE_BREAK_3")

    def test_free_throw_area_is_paint(self):
        self.assertEqual(self.zone(20.0, 50.0, False), "PAINT")

    def test_long_two(self):
        self.assertEqual(self.zone(28.0, 20.0, False), "LONG_MID")


class DetailedZones(unittest.TestCase):
    """Siatka szczegolowa steruje mapa rzutow w portalu."""

    def zone(self, x: float, y: float, three: bool) -> str:
        return court.classify_detailed(court.normalize(x, y), three)

    def test_restricted_area(self):
        self.assertEqual(self.zone(5.96, 44.46, False), "RA")

    def test_corner_sides(self):
        self.assertEqual(self.zone(5.18, 2.09, True), "C3_L")
        self.assertEqual(self.zone(5.18, 97.91, True), "C3_R")

    def test_arc_sectors_are_symmetric(self):
        self.assertEqual(self.zone(29.4, 36.0, True), "AB3_C")
        left = self.zone(20.0, 12.0, True)
        right = self.zone(20.0, 88.0, True)
        self.assertEqual(left[:-1], right[:-1])
        self.assertNotEqual(left, right)

    def test_every_zone_maps_to_a_summary_zone(self):
        for zone in court.DETAILED_ZONES:
            self.assertIn(court.DETAILED_TO_ZONE[zone], court.ZONES)

    def test_detailed_and_summary_agree(self):
        for x, y, three in [(5.96, 44.46, False), (17.97, 10, True), (5.18, 2.09, True),
                            (20.0, 50.0, False), (28.0, 20.0, False), (8.0, 30.0, False)]:
            loc = court.normalize(x, y)
            with self.subTest(x=x, y=y):
                self.assertEqual(
                    court.DETAILED_TO_ZONE[court.classify_detailed(loc, three)],
                    court.classify(loc, three),
                )


class Metrics(unittest.TestCase):
    def test_efg_counts_three_as_one_and_half(self):
        self.assertAlmostEqual(metrics.efg({"fgm": 10, "tpm": 4, "fga": 20}), 60.0)

    def test_true_shooting(self):
        value = metrics.ts({"pts": 25, "fga": 15, "fta": 6})
        self.assertAlmostEqual(value, 100 * 25 / (2 * (15 + 0.44 * 6)), places=6)

    def test_possessions_formula(self):
        stats = {"fga": 70, "orb": 10, "tov": 12, "fta": 20}
        self.assertAlmostEqual(metrics.possessions(stats), 70 - 10 + 12 + 8.8)

    def test_percentiles_order(self):
        ranks = metrics.percentile_ranks({"a": 1.0, "b": 2.0, "c": 3.0})
        self.assertLess(ranks["a"], ranks["c"])

    def test_ranks_start_at_one(self):
        places = metrics.ranks({"a": 1.0, "b": 3.0, "c": 2.0})
        self.assertEqual(places["b"], 1)
        self.assertEqual(places["a"], 3)


def _raw_game() -> dict:
    """Minimalny mecz: dwie druzyny po piatce i kilka akcji."""

    def squad(prefix: str) -> dict:
        return {
            str(i): {
                "name": "{} {}".format(prefix, i),
                "firstName": prefix,
                "familyName": str(i),
                "shirtNumber": str(i),
                "starter": 1,
                "active": 1,
                "sMinutes": "20:00",
                "sPoints": 0,
            }
            for i in range(1, 6)
        }

    def event(number, period, gt, tno, pno, action, sub="", success=1, s1=0, s2=0):
        return {
            "actionNumber": number, "period": period, "gt": gt, "tno": tno, "pno": pno,
            "actionType": action, "subType": sub, "success": success, "scoring": 0,
            "s1": s1, "s2": s2, "player": "", "shirtNumber": "",
        }

    return {
        "periodsMax": 4, "periodLengthREGULAR": 10, "periodLengthOVERTIME": 5,
        "tm": {
            "1": {"name": "Gospodarze", "score": 2, "pl": squad("A"), "tot_sPoints": 2},
            "2": {"name": "Goscie", "score": 3, "pl": squad("B"), "tot_sPoints": 3},
        },
        "pbp": [
            event(10, 1, "09:00", 2, 1, "3pt", "jumpshot", 1, 0, 3),
            event(9, 1, "09:20", 1, 2, "rebound", "defensive"),
            event(8, 1, "09:25", 2, 3, "2pt", "layup", 0),
            event(7, 1, "09:40", 1, 1, "2pt", "layup", 1, 2, 0),
            event(6, 1, "10:00", 0, 0, "period", "start"),
        ],
    }


class Possessions(unittest.TestCase):
    def setUp(self):
        self.game = fiba.parse(_raw_game(), "test")

    def test_events_are_chronological(self):
        self.assertEqual(self.game.pbp[0].action, "period")
        self.assertEqual(self.game.pbp[-1].action, "3pt")

    def test_splits_into_possessions(self):
        possessions, tracker = split_possessions(self.game)
        self.assertEqual(tracker.warnings, [])
        offenses = [p.offense for p in possessions]
        self.assertEqual(offenses, [1, 2, 1, 2])
        self.assertEqual(possessions[0].points, 2)
        self.assertEqual(possessions[-1].points, 3)

    def test_lineups_are_complete(self):
        possessions, _ = split_possessions(self.game)
        for poss in possessions:
            self.assertEqual(len(poss.lineups[1]), 5)
            self.assertEqual(len(poss.lineups[2]), 5)

    def test_durations_tile_the_game(self):
        possessions, _ = split_possessions(self.game)
        for earlier, later in zip(possessions, possessions[1:]):
            self.assertLessEqual(later.start_elapsed, earlier.end_elapsed)


class MatchIds(unittest.TestCase):
    def test_reads_livestats_url(self):
        url = "https://fibalivestats.dcd.shared.geniussports.com/u/POL/2905346/index.html"
        self.assertEqual(fiba.parse_match_id(url), "2905346")

    def test_accepts_bare_id(self):
        self.assertEqual(fiba.parse_match_id("2905346"), "2905346")

    def test_reads_pzkosz_url(self):
        url = "https://1lm.pzkosz.pl/mecz/223889/gks-tychy---pge-spojnia-stargard.html"
        self.assertEqual(pzkosz.parse_match_id(url), "223889")


class PolishPlayByPlay(unittest.TestCase):
    """Opisy akcji na stronie PZKosz sa po polsku - mapujemy je na model FIBA."""

    CASES = [
        ("celny lay-up", ("2pt", "layup", 1)),
        ("niecelny z wyskoku za 3", ("3pt", "jumpshot", 0)),
        ("celny rzut wolny 2z2", ("freethrow", "2of2", 1)),
        ("niecelny rzut wolny 1z2", ("freethrow", "1of2", 0)),
        ("zbiórka w ataku", ("rebound", "offensive", 1)),
        ("strata - błąd kozłowania", ("turnover", "ballhandling", 1)),
        ("zmiana - wejście", ("substitution", "in", 1)),
        ("faul techniczny trenera", ("foul", "coachTechnical", 1)),
    ]

    def test_known_phrases(self):
        for phrase, expected in self.CASES:
            with self.subTest(phrase=phrase):
                self.assertEqual(pzkosz._classify(phrase), expected)

    def test_player_prefix_is_split_off(self):
        shirt, name, rest = pzkosz._split_player("4, T. Śnieg, celny lay-up")
        self.assertEqual((shirt, name, rest), ("4", "T. Śnieg", "celny lay-up"))

    def test_clock_is_read_as_remaining_seconds(self):
        self.assertEqual(pzkosz._clock_to_remaining("09:38:00"), 578)


class KillShots(unittest.TestCase):
    def test_counts_runs_of_ten(self):
        class Fake:
            def __init__(self, s1, s2):
                self.s1, self.s2 = s1, s2

        events = [Fake(s, 0) for s in (2, 5, 7, 10, 12)]
        self.assertEqual(metrics.kill_shots(events)[1], 1)

    def test_answer_breaks_the_run(self):
        class Fake:
            def __init__(self, s1, s2):
                self.s1, self.s2 = s1, s2

        events = [Fake(2, 0), Fake(5, 0), Fake(5, 2), Fake(9, 2)]
        self.assertEqual(metrics.kill_shots(events)[1], 0)


if __name__ == "__main__":
    unittest.main()
