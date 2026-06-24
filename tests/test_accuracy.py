"""
Testes do módulo de ensaio de precisão (lc76g_gnss.accuracy).

Executar:
    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import accuracy as acc


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(acc.haversine_m(-22.0, -45.0, -22.0, -45.0), 0.0)

    def test_one_degree_latitude(self):
        # 1° de latitude ≈ 111195 m (raio médio IUGG).
        d = acc.haversine_m(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 111195, delta=5)

    def test_symmetric(self):
        d1 = acc.haversine_m(-22.234, -45.703, -22.235, -45.704)
        d2 = acc.haversine_m(-22.235, -45.704, -22.234, -45.703)
        self.assertAlmostEqual(d1, d2, places=9)

    def test_known_small_distance(self):
        # ~0.001° de latitude ≈ 111,2 m.
        d = acc.haversine_m(-22.0, -45.0, -22.001, -45.0)
        self.assertAlmostEqual(d, 111.2, delta=0.5)


class TestModeValue(unittest.TestCase):
    def test_mode_with_repeats(self):
        vals = [1.000001, 1.000002, 1.000001, 1.000001, 2.0]
        self.assertEqual(acc.mode_value(vals, decimals=6), 1.000001)

    def test_no_repeats_falls_back_to_median(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        # Com 0 casas todos viram inteiros distintos -> sem repetição -> mediana.
        self.assertEqual(acc.mode_value(vals, decimals=0), 3.0)

    def test_empty_returns_none(self):
        self.assertIsNone(acc.mode_value([]))

    def test_rounding_groups_close_samples(self):
        # Com 3 casas, todos arredondam para 22.234 -> moda 22.234.
        vals = [22.23401, 22.23399, 22.23402, 22.2340, 22.99]
        self.assertEqual(acc.mode_value(vals, decimals=3), 22.234)


class TestModePosition(unittest.TestCase):
    def test_basic(self):
        samples = [(-22.2340, -45.7036)] * 90 + [(-22.5, -45.9)] * 10
        lat, lon = acc.mode_position(samples, decimals=4)
        self.assertAlmostEqual(lat, -22.2340, places=4)
        self.assertAlmostEqual(lon, -45.7036, places=4)

    def test_empty(self):
        self.assertIsNone(acc.mode_position([]))


class TestAccuracyPoint(unittest.TestCase):
    def _point(self, known, measured):
        return acc.AccuracyPoint(index=1, known_distance=known, lat=0.0,
                                 lon=0.0, measured_distance=measured,
                                 n_samples=100)

    def test_error_sign(self):
        self.assertAlmostEqual(self._point(10.0, 12.0).error, 2.0)
        self.assertAlmostEqual(self._point(10.0, 8.0).error, -2.0)

    def test_abs_error(self):
        self.assertAlmostEqual(self._point(10.0, 8.0).abs_error, 2.0)

    def test_error_pct(self):
        self.assertAlmostEqual(self._point(10.0, 11.0).error_pct, 10.0)

    def test_error_pct_zero_distance(self):
        self.assertIsNone(self._point(0.0, 1.0).error_pct)


class TestSampleDeviations(unittest.TestCase):
    def test_empty_without_samples(self):
        p = acc.AccuracyPoint(1, 0.0, -22.0, -45.0, 0.0, 0)
        self.assertEqual(acc.sample_deviations_m(p), [])

    def test_deviations_from_point(self):
        # amostra na própria posição -> 0 m; outra ~1 m ao norte.
        p = acc.AccuracyPoint(
            1, 0.0, -22.0, -45.0, 0.0, 2,
            samples=[(-22.0, -45.0), (-22.0 + 1 / 111320.0, -45.0)])
        devs = acc.sample_deviations_m(p)
        self.assertEqual(len(devs), 2)
        self.assertAlmostEqual(devs[0], 0.0, places=6)
        self.assertAlmostEqual(devs[1], 1.0, delta=0.05)


class TestErrorStats(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(acc.error_stats([]), {"n": 0})

    def test_metrics(self):
        pts = [
            acc.AccuracyPoint(1, 10.0, 0, 0, 12.0, 100),   # erro +2
            acc.AccuracyPoint(2, 20.0, 0, 0, 18.0, 100),   # erro -2
            acc.AccuracyPoint(3, 30.0, 0, 0, 33.0, 100),   # erro +3
        ]
        s = acc.error_stats(pts)
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["mean_error"], 1.0)
        self.assertAlmostEqual(s["mean_abs_error"], 7.0 / 3.0)
        self.assertAlmostEqual(s["max_abs_error"], 3.0)
        self.assertAlmostEqual(s["min_abs_error"], 2.0)
        self.assertAlmostEqual(s["rms_error"], math.sqrt((4 + 4 + 9) / 3.0))
        # erro% absoluto médio: (20 + 10 + 10)/3
        self.assertAlmostEqual(s["mean_abs_error_pct"], (20.0 + 10.0 + 10.0) / 3.0)


if __name__ == "__main__":
    unittest.main()
