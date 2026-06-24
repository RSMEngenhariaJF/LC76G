"""
Testes da geração de relatório (lc76g_gnss.report).

Pulam automaticamente se ``python-docx`` não estiver instalado.

Executar:
    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import accuracy as acc
from lc76g_gnss import weather as wx

try:
    from lc76g_gnss import report
    HAVE_DOCX = True
except ImportError:
    HAVE_DOCX = False


def _sample_points():
    p1 = acc.AccuracyPoint(1, 10.0, -22.2340, -45.7036, 10.1, 50,
                           hdop=1.1, sats=9, time_local="2026-06-23 12:00:00",
                           gnss_utc="120000.000",
                           samples=[(-22.2340, -45.7036), (-22.2341, -45.7036)])
    p2 = acc.AccuracyPoint(2, 20.0, -22.2339, -45.7036, 20.2, 50,
                           hdop=1.2, sats=10, time_local="2026-06-23 12:02:00",
                           gnss_utc="120200.000",
                           samples=[(-22.2339, -45.7036)])
    return [p1, p2]


@unittest.skipUnless(HAVE_DOCX, "python-docx não instalado")
class TestReport(unittest.TestCase):
    def test_glossary_present(self):
        termos = {t for t, _ in report.GLOSSARY}
        for esperado in ("TTFF", "HDOP", "RMS", "Índice Kp", "Haversine"):
            self.assertIn(esperado, termos)

    def test_build_report_creates_file(self):
        points = _sample_points()
        stats = acc.error_stats(points)
        wd = wx.WeatherData(temperature_c=18.3, humidity_pct=95,
                            surface_pressure_hpa=917.5, kp_index=2.0)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "rel.docx")
            report.build_precision_report(
                out, title="Teste", responsible="Fulano",
                device="Quectel LC76G", mode="origem",
                reference=(-22.2340, -45.7036), points=points, stats=stats,
                weather=wd, sample_count=50, decimals=5,
                generated_at=datetime(2026, 6, 23, 12, 30, 0))
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), 5000)

    def test_build_report_without_weather(self):
        points = _sample_points()
        stats = acc.error_stats(points)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "rel2.docx")
            report.build_precision_report(
                out, title="Sem clima", responsible="", device="Genérico",
                mode="trecho", reference=None, points=points, stats=stats,
                weather=None, sample_count=None, decimals=None,
                generated_at=datetime(2026, 6, 23, 12, 30, 0))
            self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
