"""
lc76g_gnss.devices.casic
------------------------
Perfis da família **CASIC / ZhongKeWei (ZKW)** — chip **AT6558** e similares.

Diferente do u-blox, o AT6558 **não usa UBX**: a configuração e os reinícios são
feitos por comandos **NMEA proprietários `$PCAS`**. Por isso os starts são
comandos NMEA normais (checksum calculado automaticamente).

Reinício — ``$PCAS10,<modo>``:
    0 = hot start · 1 = warm start · 2 = cold start · 3 = reinício de fábrica.

Modo GNSS — ``$PCAS04,<m>``: 1=GPS, 2=BDS, 3=GPS+BDS, 4=GLONASS,
5=GPS+GLONASS, 7=GPS+BDS+GLONASS.

Baud — ``$PCAS01,<b>``: 0=4800, 1=9600, 2=19200, 3=38400, 4=57600, 5=115200.
"""

from __future__ import annotations

from ..core import BAUD_RATES, Command
from .base import DeviceProfile

PCAS_CATALOG = [
    Command("PCAS10,0 — Hot start", "PCAS10,0",
            "Reinício a quente (mantém todos os dados)."),
    Command("PCAS10,1 — Warm start", "PCAS10,1",
            "Reinício morno (mantém tempo/posição/almanaque)."),
    Command("PCAS10,2 — Cold start", "PCAS10,2",
            "Reinício a frio (limpa efemérides/posição/tempo)."),
    Command("PCAS10,3 — Reinício de fábrica", "PCAS10,3",
            "Restaura configurações de fábrica e limpa tudo."),
    Command("PCAS00 — Salvar config", "PCAS00",
            "Salva as configurações atuais na memória flash."),
    Command("PCAS04,7 — GPS+BDS+GLONASS", "PCAS04,7",
            "Define o modo multi-GNSS (GPS+BeiDou+GLONASS)."),
    Command("PCAS01,5 — Baud 115200", "PCAS01,5",
            "Configura a UART para 115200 bps (requer salvar/reiniciar)."),
]


def _casic_profile(dev_id, name, description):
    return DeviceProfile(
        id=dev_id,
        name=name,
        description=description,
        # AT6558 reinicia por NMEA $PCAS10 (não há binário UBX aqui).
        start_commands={"cold": "PCAS10,2", "warm": "PCAS10,1", "hot": "PCAS10,0"},
        command_catalog=list(PCAS_CATALOG),
        baud_rates=list(BAUD_RATES),
        default_baud=9600,
        bypass_command=None,                # conexão direta (USB-TTL)
        version_query=None,
        notes="AT6558 (CASIC/ZKW): comandos NMEA $PCAS, não UBX. Reinício "
              "$PCAS10,0/1/2 (hot/warm/cold). Conexão direta (sem bypass).",
    )


AT6558 = _casic_profile(
    "AT6558", "AT6558 (CASIC/ZKW)",
    "GNSS AT6558 multi-GNSS (GPS/BDS/GLONASS), NMEA + $PCAS. Padrão 9600 bps.")

#: Perfis exportados por esta família.
PROFILES = [AT6558]
