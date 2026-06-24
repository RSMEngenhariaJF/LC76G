"""
Testes do núcleo (gps_core) — não requerem hardware nem porta serial.

Executar:
    python -m unittest discover -s tests -v
ou
    python -m pytest tests -v
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import core


class TestChecksum(unittest.TestCase):
    def test_checksum_pair002(self):
        # Exemplo do manual: $PAIR002*38
        self.assertEqual(core.nmea_checksum("PAIR002"), "38")

    def test_checksum_pair004(self):
        # $PAIR004*3E
        self.assertEqual(core.nmea_checksum("PAIR004"), "3E")

    def test_checksum_pair864(self):
        # $PAIR864,0,0,115200*1B
        self.assertEqual(core.nmea_checksum("PAIR864,0,0,115200"), "1B")

    def test_checksum_pqtmverno(self):
        # $PQTMVERNO*58
        self.assertEqual(core.nmea_checksum("PQTMVERNO"), "58")

    def test_checksum_rmc_example(self):
        # $GNRMC,...*0E (exemplo do manual)
        payload = ("GNRMC,040143.000,A,3149.334166,N,11706.941670,E,"
                   "0.01,0.00,010522,,,D,V")
        self.assertEqual(core.nmea_checksum(payload), "0E")

    def test_checksum_two_uppercase_hex_chars(self):
        for payload in ("PAIR003", "PAIR513", "GPGGA,123519"):
            chk = core.nmea_checksum(payload)
            self.assertEqual(len(chk), 2)
            self.assertEqual(chk, chk.upper())
            int(chk, 16)  # não deve lançar


class TestBuildSentence(unittest.TestCase):
    def test_build_default_crlf(self):
        self.assertEqual(core.build_sentence("PAIR002"), "$PAIR002*38\r\n")

    def test_build_no_ending(self):
        self.assertEqual(core.build_sentence("PAIR002", ""), "$PAIR002*38")

    def test_build_round_trip_is_valid(self):
        s = core.build_sentence("PAIR864,0,0,115200")
        self.assertTrue(core.verify_checksum(s))


class TestSplitAndVerify(unittest.TestCase):
    def test_split_with_dollar_and_checksum(self):
        payload, chk = core.split_sentence("$PAIR001,004,0*3F")
        self.assertEqual(payload, "PAIR001,004,0")
        self.assertEqual(chk, "3F")

    def test_split_without_checksum(self):
        payload, chk = core.split_sentence("$PAIR002")
        self.assertEqual(payload, "PAIR002")
        self.assertIsNone(chk)

    def test_split_strips_crlf(self):
        payload, chk = core.split_sentence("$PAIR002*38\r\n")
        self.assertEqual(payload, "PAIR002")
        self.assertEqual(chk, "38")

    def test_verify_valid(self):
        self.assertTrue(core.verify_checksum("$PAIR002*38"))

    def test_verify_invalid(self):
        self.assertFalse(core.verify_checksum("$PAIR002*FF"))

    def test_verify_none_when_absent(self):
        self.assertIsNone(core.verify_checksum("$PAIR002"))

    def test_verify_case_insensitive(self):
        self.assertTrue(core.verify_checksum("$PAIR002*38"))
        self.assertTrue(core.verify_checksum("$pair002".upper() + "*38"))


class TestCoordinateConversion(unittest.TestCase):
    def test_latitude_north(self):
        # 3149.334166 N -> 31 + 49.334166/60
        self.assertAlmostEqual(core.dm_to_decimal("3149.334166", "N"),
                               31.822236, places=5)

    def test_longitude_east(self):
        self.assertAlmostEqual(core.dm_to_decimal("11706.941670", "E"),
                               117.115695, places=5)

    def test_south_is_negative(self):
        self.assertLess(core.dm_to_decimal("3149.334166", "S"), 0)

    def test_west_is_negative(self):
        self.assertLess(core.dm_to_decimal("11706.941670", "W"), 0)

    def test_empty_returns_none(self):
        self.assertIsNone(core.dm_to_decimal("", "N"))
        self.assertIsNone(core.dm_to_decimal("3149.33", ""))


class TestParseNmea(unittest.TestCase):
    def test_parse_standard_rmc(self):
        s = core.parse_nmea("$GNRMC,040143.000,A,3149.33,N,11706.94,E,0,0,010522,,,D,V*XX")
        self.assertEqual(s.talker, "GN")
        self.assertEqual(s.sentence_type, "RMC")
        self.assertFalse(s.is_proprietary)

    def test_parse_proprietary_pair(self):
        s = core.parse_nmea("$PAIR001,004,0*3F")
        self.assertTrue(s.is_proprietary)
        self.assertEqual(s.talker, "P")
        self.assertEqual(s.sentence_type, "PAIR001")
        self.assertTrue(s.checksum_ok)

    def test_parse_proprietary_pqtm(self):
        s = core.parse_nmea("$PQTMVERNO,LC76GABNR02A01S,2022/09/14,11:47:03*3D")
        self.assertTrue(s.is_proprietary)
        self.assertEqual(s.sentence_type, "PQTMVERNO")

    def test_parse_empty_returns_none(self):
        self.assertIsNone(core.parse_nmea(""))
        self.assertIsNone(core.parse_nmea("   \r\n"))

    def test_parse_bad_checksum_flagged(self):
        s = core.parse_nmea("$PAIR002*FF")
        self.assertFalse(s.checksum_ok)

    def test_parse_no_checksum(self):
        s = core.parse_nmea("$GPTXT,hello")
        self.assertIsNone(s.checksum_ok)


class TestParseFix(unittest.TestCase):
    RMC = "$GNRMC,040143.000,A,3149.334166,N,11706.941670,E,0.01,0.00,010522,,,D,V*0E"
    GGA = "$GNGGA,040143.000,3149.334166,N,11706.941670,E,2,36,0.48,61.496,M,,M,,*XX"

    def test_parse_rmc_fix(self):
        fix = core.parse_rmc(core.parse_nmea(self.RMC))
        self.assertTrue(fix.valid)
        self.assertAlmostEqual(fix.latitude, 31.822236, places=5)
        self.assertAlmostEqual(fix.longitude, 117.115695, places=5)
        self.assertEqual(fix.speed_knots, 0.01)
        self.assertEqual(fix.date, "010522")
        self.assertEqual(fix.utc, "040143.000")

    def test_parse_gga_fix(self):
        fix = core.parse_gga(core.parse_nmea(self.GGA))
        self.assertTrue(fix.valid)
        self.assertEqual(fix.quality, 2)
        self.assertEqual(fix.satellites_used, 36)
        self.assertEqual(fix.hdop, 0.48)
        self.assertEqual(fix.altitude, 61.496)

    def test_rmc_invalid_status(self):
        line = "$GNRMC,,V,,,,,,,,,,N,V*XX"
        fix = core.parse_rmc(core.parse_nmea(line))
        self.assertFalse(fix.valid)
        self.assertIsNone(fix.latitude)

    def test_parse_rmc_rejects_gga(self):
        self.assertIsNone(core.parse_rmc(core.parse_nmea(self.GGA)))

    def test_parse_gga_rejects_rmc(self):
        self.assertIsNone(core.parse_gga(core.parse_nmea(self.RMC)))


class TestSatellitesAndFix(unittest.TestCase):
    GSV_GP = "$GPGSV,3,1,10,22,65,210,32,17,60,046,33,14,54,169,26,30,49,129,32,1*6F"
    GSV_GL = "$GLGSV,2,1,05,67,63,332,20,68,47,225,32,78,41,212,34,77,21,147,21,1*7D"
    GSA_3D = "$GNGSA,A,3,22,17,14,30,20,19,21,05,,,,,0.99,0.67,0.73,1*08"
    GSA_NO = "$GNGSA,A,1,,,,,,,,,,,,,,,,1*1D"

    def test_parse_gsv_in_view(self):
        talker, in_view, msg_num, total = core.parse_gsv(core.parse_nmea(self.GSV_GP))
        self.assertEqual(talker, "GP")
        self.assertEqual(in_view, 10)
        self.assertEqual(msg_num, 1)
        self.assertEqual(total, 3)

    def test_parse_gsv_rejects_non_gsv(self):
        self.assertIsNone(core.parse_gsv(core.parse_nmea(self.GSA_3D)))

    def test_parse_gsa_fix_type_3d(self):
        self.assertEqual(core.parse_gsa_fix_type(core.parse_nmea(self.GSA_3D)), 3)

    def test_parse_gsa_fix_type_nofix(self):
        self.assertEqual(core.parse_gsa_fix_type(core.parse_nmea(self.GSA_NO)), 1)

    def test_is_valid_fix_true_for_active_rmc(self):
        rmc = "$GNRMC,040143.000,A,3149.33,N,11706.94,E,0,0,010522,,,A,V*XX"
        self.assertTrue(core.is_valid_fix(core.parse_nmea(rmc)))

    def test_is_valid_fix_false_for_void_rmc(self):
        rmc = "$GNRMC,,V,,,,,,,,,,N,V*37"
        self.assertFalse(core.is_valid_fix(core.parse_nmea(rmc)))

    def test_is_valid_fix_false_for_empty_gga(self):
        gga = "$GNGGA,235946.011,,,,,0,0,,,M,,M,,*59"
        self.assertFalse(core.is_valid_fix(core.parse_nmea(gga)))

    def test_satellite_tracker_sums_constellations(self):
        tracker = core.SatelliteTracker()
        self.assertTrue(tracker.feed(core.parse_nmea(self.GSV_GP)))  # 10
        self.assertTrue(tracker.feed(core.parse_nmea(self.GSV_GL)))  # 5
        self.assertEqual(tracker.total_in_view, 15)
        self.assertEqual(tracker.per_constellation, {"GP": 10, "GL": 5})

    def test_satellite_tracker_updates_same_constellation(self):
        tracker = core.SatelliteTracker()
        tracker.feed(core.parse_nmea(self.GSV_GP))            # GP=10
        tracker.feed(core.parse_nmea("$GPGSV,3,1,09,22,65,210,32,1*68"))  # GP=9
        self.assertEqual(tracker.per_constellation["GP"], 9)
        self.assertEqual(tracker.total_in_view, 9)

    def test_satellite_tracker_reset(self):
        tracker = core.SatelliteTracker()
        tracker.feed(core.parse_nmea(self.GSV_GP))
        tracker.reset()
        self.assertEqual(tracker.total_in_view, 0)


class FakeSerial:
    """Porta serial falsa para testar o SerialManager sem hardware."""

    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.written = bytearray()
        self._rx = bytearray()
        self._lock = threading.Lock()

    def feed(self, data: bytes):
        with self._lock:
            self._rx.extend(data)

    def read(self, size=1):
        time.sleep(0.005)
        with self._lock:
            if not self._rx:
                return b""
            chunk = bytes(self._rx[:size])
            del self._rx[:size]
            return chunk

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def flush(self):
        pass

    def close(self):
        self.is_open = False


class TestSerialManager(unittest.TestCase):
    def setUp(self):
        self.received = []
        self.errors = []
        self.fakes = []

        def factory(port, baud, timeout):
            fake = FakeSerial(port, baud, timeout)
            self.fakes.append(fake)
            return fake

        self.mgr = core.SerialManager(
            on_line=self.received.append,
            on_error=self.errors.append,
            serial_factory=factory,
        )

    def tearDown(self):
        self.mgr.close()

    def test_open_and_close(self):
        self.assertFalse(self.mgr.is_open)
        self.mgr.open("COM_TEST", 115200)
        self.assertTrue(self.mgr.is_open)
        self.mgr.close()
        self.assertFalse(self.mgr.is_open)

    def test_write_line_encodes(self):
        self.mgr.open("COM_TEST", 115200)
        self.mgr.write_line("#gps\r\n")
        self.assertEqual(bytes(self.fakes[-1].written), b"#gps\r\n")

    def test_write_without_open_raises(self):
        with self.assertRaises(RuntimeError):
            self.mgr.write_line("x")

    def test_reader_splits_lines(self):
        self.mgr.open("COM_TEST", 115200)
        self.fakes[-1].feed(b"$PAIR001,004,0*3F\r\n$PQTMVERNO*58\r\n")
        # aguarda a thread de leitura processar
        deadline = time.time() + 2.0
        while len(self.received) < 2 and time.time() < deadline:
            time.sleep(0.02)
        self.assertIn("$PAIR001,004,0*3F", self.received)
        self.assertIn("$PQTMVERNO*58", self.received)


if __name__ == "__main__":
    unittest.main(verbosity=2)
