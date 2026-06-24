"""
lc76g_gnss.ublox_proto
----------------------
Construção de mensagens **binárias UBX** do protocolo u-blox (NEO-6M e família).

Implementa o necessário para os reinícios cold/warm/hot via **UBX-CFG-RST**
(classe 0x06, id 0x04), já que o u-blox não usa comandos NMEA para isso.

Estrutura de um quadro UBX:
    B5 62 | classe | id | comprimento (2 bytes LE) | payload | CK_A CK_B
O checksum é o algoritmo de Fletcher de 8 bits sobre classe+id+comprimento+payload.
"""

from __future__ import annotations

UBX_SYNC = b"\xB5\x62"

# Máscaras BBR (battery-backed RAM) para UBX-CFG-RST:
NAV_BBR_HOTSTART = 0x0000   # mantém tudo
NAV_BBR_WARMSTART = 0x0001  # limpa efemérides
NAV_BBR_COLDSTART = 0xFFFF  # limpa tudo

# Modo de reinício: 0x02 = reset de software controlado (somente GNSS), preserva
# a UART/conexão serial (não faz reboot de hardware).
RESET_MODE_GNSS_SW = 0x02


def ubx_checksum(body: bytes) -> bytes:
    """Checksum (Fletcher-8) sobre ``body`` = classe+id+comprimento+payload."""
    ck_a = ck_b = 0
    for b in body:
        ck_a = (ck_a + b) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return bytes([ck_a, ck_b])


def ubx_frame(msg_class: int, msg_id: int, payload: bytes = b"") -> bytes:
    """Monta um quadro UBX completo (com sync e checksum)."""
    length = len(payload)
    body = bytes([msg_class, msg_id, length & 0xFF, (length >> 8) & 0xFF]) + payload
    return UBX_SYNC + body + ubx_checksum(body)


def cfg_rst(nav_bbr_mask: int, reset_mode: int = RESET_MODE_GNSS_SW) -> bytes:
    """Monta um UBX-CFG-RST (reinício do receptor)."""
    payload = bytes([
        nav_bbr_mask & 0xFF, (nav_bbr_mask >> 8) & 0xFF,
        reset_mode & 0xFF, 0x00,  # reserved1
    ])
    return ubx_frame(0x06, 0x04, payload)


#: Quadros prontos de reinício para cold/warm/hot start.
START_FRAMES = {
    "cold": cfg_rst(NAV_BBR_COLDSTART),
    "warm": cfg_rst(NAV_BBR_WARMSTART),
    "hot": cfg_rst(NAV_BBR_HOTSTART),
}
