"""
Testes do módulo de clima (lc76g_gnss.weather) — sem acesso à rede (injeção de
``get_json`` com respostas de exemplo).

Executar:
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import weather as wx

# Respostas de exemplo (formato real das APIs).
OPEN_METEO_SAMPLE = {
    "latitude": -22.25, "longitude": -45.74, "elevation": 872.0,
    "current": {
        "time": "2026-06-23T18:45", "temperature_2m": 18.3,
        "relative_humidity_2m": 95, "surface_pressure": 917.5,
        "pressure_msl": 1015.2, "cloud_cover": 98, "precipitation": 0.10,
        "wind_speed_10m": 8.7,
    },
}
NOAA_KP_DICTS = [
    {"time_tag": "2026-06-16T00:00:00", "Kp": 2.00},
    {"time_tag": "2026-06-16T03:00:00", "Kp": 3.33},
]
NOAA_KP_ARRAYS = [
    ["time_tag", "Kp", "a_running"],
    ["2026-06-16T00:00:00", "2.00", "7"],
    ["2026-06-16T03:00:00", "4.67", "27"],
]


def make_get_json(meteo=OPEN_METEO_SAMPLE, kp=NOAA_KP_DICTS, fail=None):
    def _get(url, timeout=10.0):
        if fail:
            raise fail
        return meteo if "open-meteo" in url else kp
    return _get


class TestParsing(unittest.TestCase):
    def test_apply_open_meteo(self):
        wd = wx.apply_open_meteo(wx.WeatherData(), OPEN_METEO_SAMPLE)
        self.assertEqual(wd.temperature_c, 18.3)
        self.assertEqual(wd.humidity_pct, 95)
        self.assertEqual(wd.surface_pressure_hpa, 917.5)
        self.assertEqual(wd.pressure_msl_hpa, 1015.2)
        self.assertEqual(wd.cloud_cover_pct, 98)
        self.assertEqual(wd.precipitation_mm, 0.10)
        self.assertEqual(wd.wind_speed_kmh, 8.7)
        self.assertEqual(wd.elevation_m, 872.0)
        self.assertEqual(wd.observed_utc, "2026-06-23T18:45")

    def test_parse_kp_dicts(self):
        self.assertEqual(wx.parse_kp(NOAA_KP_DICTS), 3.33)

    def test_parse_kp_arrays(self):
        self.assertEqual(wx.parse_kp(NOAA_KP_ARRAYS), 4.67)

    def test_parse_kp_empty(self):
        self.assertIsNone(wx.parse_kp([]))


class TestFetch(unittest.TestCase):
    def test_fetch_ok(self):
        wd = wx.fetch_weather(-22.234, -45.703, get_json=make_get_json())
        self.assertEqual(wd.temperature_c, 18.3)
        self.assertEqual(wd.kp_index, 3.33)
        self.assertIsNone(wd.error)

    def test_fetch_network_failure_is_graceful(self):
        wd = wx.fetch_weather(-22.234, -45.703,
                              get_json=make_get_json(fail=OSError("sem rede")))
        self.assertIsNotNone(wd.error)
        self.assertIsNone(wd.temperature_c)
        self.assertIsNone(wd.kp_index)


class TestFormatSummary(unittest.TestCase):
    def test_summary_has_fields(self):
        wd = wx.fetch_weather(-22.234, -45.703, get_json=make_get_json())
        s = wx.format_summary(wd)
        self.assertIn("18.3°C", s)
        self.assertIn("Kp 3.3", s)

    def test_summary_unavailable(self):
        self.assertIn("indisponível",
                      wx.format_summary(wx.WeatherData(error="x")))


if __name__ == "__main__":
    unittest.main()
