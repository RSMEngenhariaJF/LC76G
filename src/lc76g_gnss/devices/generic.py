"""
lc76g_gnss.devices.generic
--------------------------
Perfil de um receptor **NMEA 0183 genérico**, somente leitura: sem comandos
proprietários e sem reinício por comando NMEA. Útil para apenas decodificar e
acompanhar a posição de um módulo desconhecido.
"""

from __future__ import annotations

from .base import DeviceProfile

GENERIC = DeviceProfile(
    id="GENERIC",
    name="Genérico (NMEA)",
    description="Receptor NMEA 0183 sem comandos proprietários.",
    start_commands={},          # sem cold/warm/hot por comando NMEA
    command_catalog=[],
    bypass_command=None,        # acesso direto, sem bypass
    version_query=None,
    notes="Apenas decodificação NMEA. Cold/Warm/Hot indisponíveis por comando.",
)

#: Perfis exportados por esta família.
PROFILES = [GENERIC]
