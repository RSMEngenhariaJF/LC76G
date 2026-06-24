"""
Testes da biblioteca modular de dispositivos (gps_devices).

Executar:
    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lc76g_gnss import core
from lc76g_gnss import devices
from lc76g_gnss.devices.quectel import QUECTEL_PAIR_CATALOG


class TestRegistry(unittest.TestCase):
    def test_default_profile_exists(self):
        self.assertIn(devices.DEFAULT_DEVICE_ID, devices.DEVICE_PROFILES)
        self.assertIs(devices.default_profile(),
                      devices.DEVICE_PROFILES[devices.DEFAULT_DEVICE_ID])

    def test_default_is_lc76g(self):
        self.assertEqual(devices.default_profile().id, "LC76G")

    def test_get_profile_unknown_returns_none(self):
        self.assertIsNone(devices.get_profile("NAO_EXISTE"))

    def test_ids_unique(self):
        ids = [p.id for p in devices.list_profiles()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_names_unique(self):
        names = [p.name for p in devices.list_profiles()]
        self.assertEqual(len(names), len(set(names)))


class TestProfilesProduceValidSentences(unittest.TestCase):
    def test_start_commands_build_valid_nmea(self):
        # Todo start definido deve gerar uma sentença com checksum válido.
        for prof in devices.list_profiles():
            for kind, payload in prof.start_commands.items():
                sentence = core.build_sentence(payload)
                self.assertTrue(core.verify_checksum(sentence),
                                f"{prof.id}/{kind}: checksum inválido")

    def test_catalog_commands_build_valid_nmea(self):
        for prof in devices.list_profiles():
            for cmd in prof.command_catalog:
                sentence = core.build_sentence(cmd.payload)
                self.assertTrue(core.verify_checksum(sentence),
                                f"{prof.id}/{cmd.label}: checksum inválido")


class TestQuectelFamily(unittest.TestCase):
    def test_pair_family_shares_starts(self):
        expected = {"cold": "PAIR006", "warm": "PAIR005", "hot": "PAIR004"}
        for dev_id in ("LC76G", "LC26G", "LC86G"):
            prof = devices.get_profile(dev_id)
            self.assertEqual(prof.start_commands, expected)
            self.assertEqual(prof.bypass_command, core.BYPASS_COMMAND)
            self.assertTrue(prof.supports_start("cold"))

    def test_pair_family_shares_catalog(self):
        for dev_id in ("LC76G", "LC26G", "LC86G"):
            self.assertEqual(devices.get_profile(dev_id).command_catalog,
                             list(QUECTEL_PAIR_CATALOG))

    def test_quectel_catalog_not_empty_and_labels_unique(self):
        labels = [c.label for c in QUECTEL_PAIR_CATALOG]
        self.assertGreater(len(labels), 0)
        self.assertEqual(len(labels), len(set(labels)))


class TestGenericDevice(unittest.TestCase):
    def test_generic_has_no_starts(self):
        prof = devices.get_profile("GENERIC")
        for kind in ("cold", "warm", "hot"):
            self.assertFalse(prof.supports_start(kind))
        self.assertIsNone(prof.start_payload("cold"))

    def test_generic_has_no_bypass(self):
        self.assertIsNone(devices.get_profile("GENERIC").bypass_command)


UBLOX_IDS = ("GY-GPS6MV2", "UBX-M10050", "BEITIAN-BN220", "BEITIAN-BN880",
             "BEITIAN-BK359", "UBLOX")


class TestUbloxDevices(unittest.TestCase):
    def test_all_registered(self):
        for dev_id in UBLOX_IDS:
            self.assertIsNotNone(devices.get_profile(dev_id), dev_id)

    def test_defaults_direct_9600(self):
        for dev_id in UBLOX_IDS:
            prof = devices.get_profile(dev_id)
            self.assertEqual(prof.default_baud, 9600, dev_id)
            self.assertIsNone(prof.bypass_command, dev_id)   # conexão direta

    def test_starts_are_binary_ubx(self):
        for dev_id in UBLOX_IDS:
            prof = devices.get_profile(dev_id)
            for kind in ("cold", "warm", "hot"):
                self.assertTrue(prof.supports_start(kind), f"{dev_id}/{kind}")
                self.assertIsNone(prof.start_payload(kind))   # não é NMEA
                frame = prof.start_frame(kind)
                self.assertIsInstance(frame, bytes)
                self.assertEqual(frame[:2], b"\xB5\x62")       # sync UBX

    def test_pubx_catalog_is_valid_nmea(self):
        for dev_id in UBLOX_IDS:
            for cmd in devices.get_profile(dev_id).command_catalog:
                self.assertTrue(
                    core.verify_checksum(core.build_sentence(cmd.payload)),
                    f"{dev_id}/{cmd.label}")


class TestCasicDevice(unittest.TestCase):
    def test_at6558_registered(self):
        prof = devices.get_profile("AT6558")
        self.assertIsNotNone(prof)
        self.assertEqual(prof.default_baud, 9600)
        self.assertIsNone(prof.bypass_command)

    def test_starts_are_nmea_pcas(self):
        prof = devices.get_profile("AT6558")
        expected = {"cold": "PCAS10,2", "warm": "PCAS10,1", "hot": "PCAS10,0"}
        for kind, payload in expected.items():
            self.assertTrue(prof.supports_start(kind))
            self.assertEqual(prof.start_payload(kind), payload)   # NMEA, não UBX
            self.assertIsNone(prof.start_frame(kind))
            self.assertTrue(
                core.verify_checksum(core.build_sentence(payload)))


if __name__ == "__main__":
    unittest.main()
