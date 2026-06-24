"""
lc76g_gnss.devices.quectel
--------------------------
Perfis da família **Quectel** com protocolo ``$PAIR`` / ``$PQTM``.

Os módulos LC26G, LC76G e LC86G compartilham o mesmo conjunto de comandos,
conforme a "LC26G&LC26G-T&LC76G&LC86G Series GNSS Protocol Specification".
Por isso reutilizam o mesmo catálogo e os mesmos comandos de start.
"""

from __future__ import annotations

from ..core import BAUD_RATES, BYPASS_COMMAND, Command, DEFAULT_BAUD
from .base import DeviceProfile

# ---------------------------------------------------------------------------
# Catálogo de comandos da família (cap. 2.3 e 2.4 do manual)
# ---------------------------------------------------------------------------
QUECTEL_PAIR_CATALOG = [
    Command("PQTMVERNO — Versão do firmware", "PQTMVERNO",
            "Consulta a versão do firmware do módulo."),
    Command("PAIR002 — Ligar subsistema GNSS", "PAIR002",
            "Liga o subsistema GNSS (power on)."),
    Command("PAIR003 — Desligar subsistema GNSS", "PAIR003",
            "Desliga o subsistema GNSS (power off)."),
    Command("PAIR004 — Hot start", "PAIR004",
            "Reinício a quente: usa todos os dados do NVRAM (mais rápido)."),
    Command("PAIR005 — Warm start", "PAIR005",
            "Reinício morno: usa tempo, posição e almanaque aproximados."),
    Command("PAIR006 — Cold start", "PAIR006",
            "Reinício a frio: apaga tempo, posição, almanaque e efemérides."),
    Command("PAIR050 — Fix rate 1 Hz", "PAIR050,1000",
            "Define a taxa de posicionamento para 1000 ms (1 Hz)."),
    Command("PAIR062,0,1 — Habilitar GGA", "PAIR062,0,1",
            "Habilita saída da mensagem GGA a cada fix."),
    Command("PAIR513 — Salvar configurações", "PAIR513",
            "Salva as configurações atuais no NVRAM."),
    Command("PAIR514 — Restaurar padrões", "PAIR514",
            "Restaura as configurações de fábrica."),
    Command("PAIR864 — Baud 115200", "PAIR864,0,0,115200",
            "Configura a UART do módulo para 115200 bps (requer reboot)."),
]

#: Comandos de reinício da família $PAIR.
QUECTEL_PAIR_STARTS = {"cold": "PAIR006", "warm": "PAIR005", "hot": "PAIR004"}


def _pair_profile(dev_id: str, name: str, description: str) -> DeviceProfile:
    """Cria um perfil da família Quectel $PAIR (catálogo/starts compartilhados)."""
    return DeviceProfile(
        id=dev_id,
        name=name,
        description=description,
        start_commands=dict(QUECTEL_PAIR_STARTS),
        command_catalog=list(QUECTEL_PAIR_CATALOG),
        baud_rates=list(BAUD_RATES),
        default_baud=DEFAULT_BAUD,
        bypass_command=BYPASS_COMMAND,
        version_query="PQTMVERNO",
        notes="Família Quectel: comandos proprietários $PAIR / $PQTM "
              "(cold=$PAIR006, warm=$PAIR005, hot=$PAIR004).",
    )


LC76G = _pair_profile(
    "LC76G", "Quectel LC76G",
    "GNSS multiconstelação, NMEA 0183 V4.10.")

LC26G = _pair_profile(
    "LC26G", "Quectel LC26G",
    "Mesma família de protocolo do LC76G ($PAIR/$PQTM).")

LC86G = _pair_profile(
    "LC86G", "Quectel LC86G",
    "Mesma família de protocolo do LC76G ($PAIR/$PQTM).")

#: Perfis exportados por esta família.
PROFILES = [LC76G, LC26G, LC86G]
