"""
lc76g_gnss.devices
------------------
Biblioteca **modular** de perfis de dispositivos GPS/GNSS.

Cada família de hardware vive em seu próprio módulo (``quectel``, ``generic``,
``ublox``, …) e expõe uma lista ``PROFILES``. Este pacote agrega todas em um
registro único, consumido pela interface.

Para adicionar uma nova família:
    1. Crie ``lc76g_gnss/devices/<fabricante>.py`` definindo os ``DeviceProfile``
       e uma lista ``PROFILES``.
    2. Importe e some seus perfis em ``_ALL_PROFILES`` abaixo.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import DeviceProfile
from .casic import PROFILES as _CASIC_PROFILES
from .generic import PROFILES as _GENERIC_PROFILES
from .quectel import PROFILES as _QUECTEL_PROFILES
from .ublox import PROFILES as _UBLOX_PROFILES

#: Ordem de exibição na caixa de seleção da interface.
_ALL_PROFILES: List[DeviceProfile] = [
    *_QUECTEL_PROFILES,
    *_UBLOX_PROFILES,
    *_CASIC_PROFILES,
    *_GENERIC_PROFILES,
]

#: Mapa ``id -> DeviceProfile`` de todos os dispositivos conhecidos.
DEVICE_PROFILES: Dict[str, DeviceProfile] = {p.id: p for p in _ALL_PROFILES}

#: Dispositivo selecionado por padrão ao abrir a ferramenta.
DEFAULT_DEVICE_ID = "LC76G"


def get_profile(device_id: str) -> Optional[DeviceProfile]:
    """Retorna o perfil pelo ``id`` (ou ``None`` se desconhecido)."""
    return DEVICE_PROFILES.get(device_id)


def default_profile() -> DeviceProfile:
    """Retorna o perfil padrão."""
    return DEVICE_PROFILES[DEFAULT_DEVICE_ID]


def list_profiles() -> List[DeviceProfile]:
    """Lista os perfis na ordem de exibição."""
    return list(_ALL_PROFILES)


__all__ = [
    "DeviceProfile",
    "DEVICE_PROFILES",
    "DEFAULT_DEVICE_ID",
    "get_profile",
    "default_profile",
    "list_profiles",
]
