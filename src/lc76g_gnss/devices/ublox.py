"""
lc76g_gnss.devices.ublox
------------------------
Perfis da família **u-blox** (protocolo binário UBX + NMEA) e módulos baseados
em u-blox.

Cold/warm/hot start usam **UBX-CFG-RST** (binário), via
:mod:`lc76g_gnss.ublox_proto`. Os comandos rápidos são *polls* ``$PUBX`` (NMEA).
Conexão direta (USB-TTL), padrão 9600 bps. O baud é ajustável na interface.

Módulos incluídos:
  * **GY-GPS6MV2** — u-blox NEO-6M (GPS L1).
  * **u-blox M10 (UBX-M10050)** — M10, multi-GNSS (GPS/GLONASS/Galileo/BeiDou).
  * **Beitian BN-220 / BN-880** — baseados em u-blox M8 (multi-GNSS).
  * **Beitian BK-359** — tratado como u-blox-compatível (confirme o chipset).
  * **u-blox (genérico)** — qualquer receptor u-blox.
"""

from __future__ import annotations

from ..core import BAUD_RATES, Command
from ..ublox_proto import START_FRAMES
from .base import DeviceProfile

# Polls $PUBX (NMEA proprietário u-blox) — solicitam respostas ao receptor.
PUBX_CATALOG = [
    Command("PUBX,00 — Posição (poll)", "PUBX,00",
            "Solicita posição/altitude/precisão (resposta $PUBX,00)."),
    Command("PUBX,03 — Satélites (poll)", "PUBX,03",
            "Solicita o status dos satélites (resposta $PUBX,03)."),
    Command("PUBX,04 — Data/hora (poll)", "PUBX,04",
            "Solicita data, hora e semana GPS (resposta $PUBX,04)."),
]


def _ublox_profile(dev_id, name, description, default_baud=9600, notes=None):
    return DeviceProfile(
        id=dev_id,
        name=name,
        description=description,
        start_commands={},                 # u-blox não reinicia por NMEA
        start_frames=dict(START_FRAMES),    # cold/warm/hot via UBX-CFG-RST
        command_catalog=list(PUBX_CATALOG),
        baud_rates=list(BAUD_RATES),
        default_baud=default_baud,
        bypass_command=None,                # conexão direta (USB-TTL)
        version_query=None,
        notes=notes or ("u-blox: cold/warm/hot via UBX-CFG-RST (binário). "
                        "Comandos $PUBX são NMEA. Conexão direta (sem bypass)."),
    )


GY_GPS6MV2 = _ublox_profile(
    "GY-GPS6MV2", "GY-GPS6MV2 (u-blox NEO-6M)",
    "GPS u-blox NEO-6M (GPS L1, NMEA). Padrão 9600 bps.")

UBX_M10050 = _ublox_profile(
    "UBX-M10050", "u-blox M10 (UBX-M10050)",
    "u-blox M10 multi-GNSS (GPS/GLONASS/Galileo/BeiDou). Padrão 9600 bps. "
    "Ex.: placas QUESCAN M10.")

BEITIAN_BN220 = _ublox_profile(
    "BEITIAN-BN220", "Beitian BN-220 (u-blox M8)",
    "Beitian BN-220, baseado em u-blox M8 (GPS+GLONASS). Padrão 9600 bps.")

BEITIAN_BN880 = _ublox_profile(
    "BEITIAN-BN880", "Beitian BN-880 (u-blox M8N)",
    "Beitian BN-880, u-blox M8N multi-GNSS (+ bússola I2C). Padrão 9600 bps.")

BEITIAN_BK359 = _ublox_profile(
    "BEITIAN-BK359", "Beitian BK-359 (u-blox compat.)",
    "Beitian BK-359 — tratado como u-blox-compatível. CONFIRME o chipset: se "
    "não for u-blox, os comandos UBX-CFG-RST podem não ter efeito.")

UBLOX = _ublox_profile(
    "UBLOX", "u-blox (genérico)",
    "Receptor u-blox genérico (UBX + NMEA).")

#: Perfis exportados por esta família.
PROFILES = [GY_GPS6MV2, UBX_M10050, BEITIAN_BN220, BEITIAN_BN880,
            BEITIAN_BK359, UBLOX]
