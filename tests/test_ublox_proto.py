"""
Testes do protocolo binário UBX (lc76g_gnss.ublox_proto).

Compara com quadros UBX-CFG-RST conhecidos/documentados do u-blox.

Executar:
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import ublox_proto as ubx


class TestUbxFrame(unittest.TestCase):
    def test_checksum_known(self):
        # body = classe+id+len+payload do CFG-RST cold start
        body = bytes.fromhex("0604040 0FFFF0200".replace(" ", ""))
        self.assertEqual(ubx.ubx_checksum(body), bytes([0x0E, 0x61]))

    def test_frame_has_sync_and_checksum(self):
        f = ubx.ubx_frame(0x06, 0x04, bytes.fromhex("FFFF0200"))
        self.assertEqual(f[:2], b"\xB5\x62")
        self.assertEqual(len(f), 2 + 4 + 4 + 2)  # sync+header+payload+checksum


class TestCfgRstFrames(unittest.TestCase):
    # Quadros UBX-CFG-RST conhecidos (sync..checksum):
    COLD = bytes.fromhex("B562060404 00FFFF02000E61".replace(" ", ""))
    WARM = bytes.fromhex("B56206040400010002 00116C".replace(" ", ""))
    HOT = bytes.fromhex("B5620604040000000200 1068".replace(" ", ""))

    def test_cold(self):
        self.assertEqual(ubx.START_FRAMES["cold"], self.COLD)

    def test_warm(self):
        self.assertEqual(ubx.START_FRAMES["warm"], self.WARM)

    def test_hot(self):
        self.assertEqual(ubx.START_FRAMES["hot"], self.HOT)

    def test_masks(self):
        self.assertEqual(ubx.NAV_BBR_COLDSTART, 0xFFFF)
        self.assertEqual(ubx.NAV_BBR_WARMSTART, 0x0001)
        self.assertEqual(ubx.NAV_BBR_HOTSTART, 0x0000)


if __name__ == "__main__":
    unittest.main()
