"""
lc76g_gnss.devices.base
-----------------------
Estrutura base da biblioteca de dispositivos: o :class:`DeviceProfile`.

Cada família de hardware (Quectel, u-blox, …) é descrita em seu próprio módulo
dentro deste pacote e registrada em :mod:`lc76g_gnss.devices`. A interface
gráfica consome apenas o perfil selecionado, de modo que trocar de módulo não
exige alterar o código da interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core import BAUD_RATES, BYPASS_COMMAND, Command, DEFAULT_BAUD


@dataclass
class DeviceProfile:
    """Descreve um módulo GPS/GNSS de forma autocontida.

    Attributes:
        id: identificador curto e único (ex.: ``"LC76G"``).
        name: nome exibido na caixa de seleção.
        description: descrição curta exibida ao lado da seleção.
        start_commands: mapa ``{"cold"/"warm"/"hot": payload}``. Pode conter
            apenas os modos suportados pelo dispositivo (os ausentes são
            desabilitados na interface).
        command_catalog: comandos rápidos disponíveis para o módulo.
        baud_rates / default_baud: opções de velocidade da UART.
        bypass_command: comando para o microcontrolador entrar em modo bypass,
            ou ``None`` se o dispositivo é acessado diretamente.
        version_query: payload para consultar o firmware (ou ``None``).
        notes: observações livres sobre o dispositivo.
    """

    id: str
    name: str
    description: str
    start_commands: Dict[str, str] = field(default_factory=dict)
    start_frames: Dict[str, bytes] = field(default_factory=dict)  # starts binários (UBX)
    command_catalog: List[Command] = field(default_factory=list)
    baud_rates: List[int] = field(default_factory=lambda: list(BAUD_RATES))
    default_baud: int = DEFAULT_BAUD
    bypass_command: Optional[str] = BYPASS_COMMAND
    version_query: Optional[str] = None
    notes: str = ""

    def start_payload(self, kind: str) -> Optional[str]:
        """Retorna o payload NMEA do start ``kind`` (cold/warm/hot) ou ``None``."""
        return self.start_commands.get(kind)

    def start_frame(self, kind: str) -> Optional[bytes]:
        """Retorna o quadro binário (UBX) do start ``kind`` ou ``None``."""
        return self.start_frames.get(kind)

    def supports_start(self, kind: str) -> bool:
        """Indica se o dispositivo define o start ``kind`` (NMEA ou binário)."""
        return bool(self.start_commands.get(kind) or self.start_frames.get(kind))
