"""
lc76g_gnss.weather
------------------
Coleta opcional de dados **meteorológicos** e de **clima espacial** para
correlacionar com o ensaio de precisão. Usa APIs públicas e gratuitas, sem chave:

  * **Open-Meteo** — clima local (temperatura, umidade, pressão, nuvens,
    precipitação, vento) e elevação do terreno, por latitude/longitude.
  * **NOAA SWPC** — índice **Kp** planetário (indicador de distúrbio
    ionosférico, relevante para o erro de GNSS de banda única).

As funções de *parsing* são separadas das de rede para permitir teste sem
internet (injete ``get_json``). Em falha de rede, ``fetch_weather`` não levanta
exceção: retorna um :class:`WeatherData` com o campo ``error`` preenchido.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from urllib.request import urlopen

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

#: Variáveis horárias/atuais pedidas à Open-Meteo.
_OPEN_METEO_CURRENT = ("temperature_2m,relative_humidity_2m,surface_pressure,"
                       "pressure_msl,cloud_cover,precipitation,wind_speed_10m")


@dataclass
class WeatherData:
    """Condições no momento/ponto do ensaio (campos ``None`` se indisponíveis)."""

    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    surface_pressure_hpa: Optional[float] = None
    pressure_msl_hpa: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    elevation_m: Optional[float] = None
    kp_index: Optional[float] = None
    observed_utc: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> dict:
        return asdict(self)


def _http_get_json(url: str, timeout: float = 10.0):
    """GET simples que decodifica JSON (usa urllib da biblioteca padrão)."""
    with urlopen(url, timeout=timeout) as resp:  # nosec - URLs fixas/HTTPS
        return json.loads(resp.read().decode("utf-8"))


def apply_open_meteo(wd: WeatherData, data: dict) -> WeatherData:
    """Preenche ``wd`` a partir de uma resposta da Open-Meteo."""
    current = data.get("current", {}) if isinstance(data, dict) else {}
    wd.temperature_c = current.get("temperature_2m")
    wd.humidity_pct = current.get("relative_humidity_2m")
    wd.surface_pressure_hpa = current.get("surface_pressure")
    wd.pressure_msl_hpa = current.get("pressure_msl")
    wd.cloud_cover_pct = current.get("cloud_cover")
    wd.precipitation_mm = current.get("precipitation")
    wd.wind_speed_kmh = current.get("wind_speed_10m")
    wd.elevation_m = data.get("elevation") if isinstance(data, dict) else None
    wd.observed_utc = current.get("time")
    return wd


def parse_kp(data) -> Optional[float]:
    """Extrai o índice Kp mais recente da resposta da NOAA SWPC.

    Aceita tanto o formato de lista de dicionários (``[{"Kp": ...}]``) quanto o
    de lista de listas com cabeçalho (``[["time_tag","Kp",...], [...]]``).
    """
    if not data:
        return None
    if isinstance(data[0], dict):
        for row in reversed(data):
            if row.get("Kp") is not None:
                try:
                    return float(row["Kp"])
                except (ValueError, TypeError):
                    return None
        return None
    # Lista de listas com cabeçalho.
    header = data[0]
    if "Kp" in header:
        ki = header.index("Kp")
        for row in reversed(data[1:]):
            try:
                return float(row[ki])
            except (ValueError, TypeError, IndexError):
                continue
    return None


def fetch_weather(lat: float, lon: float, timeout: float = 10.0,
                  get_json: Optional[Callable] = None) -> WeatherData:
    """Busca clima local (Open-Meteo) e Kp (NOAA) para a posição informada.

    Nunca levanta exceção de rede: erros vão para ``WeatherData.error``.
    ``get_json`` pode ser injetado nos testes para evitar acesso à rede.
    """
    get = get_json or _http_get_json
    wd = WeatherData()
    errors = []
    try:
        url = (f"{OPEN_METEO_URL}?latitude={lat:.6f}&longitude={lon:.6f}"
               f"&current={_OPEN_METEO_CURRENT}")
        apply_open_meteo(wd, get(url, timeout))
    except Exception as exc:  # rede, timeout, JSON inválido…
        errors.append(f"clima: {exc}")
    try:
        wd.kp_index = parse_kp(get(NOAA_KP_URL, timeout))
    except Exception as exc:
        errors.append(f"kp: {exc}")
    if errors:
        wd.error = "; ".join(errors)
    return wd


def format_summary(wd: WeatherData) -> str:
    """Resumo legível (uma linha) para log/relatório."""
    if wd is None:
        return "—"
    parts = []
    if wd.temperature_c is not None:
        parts.append(f"{wd.temperature_c:.1f}°C")
    if wd.humidity_pct is not None:
        parts.append(f"UR {wd.humidity_pct:.0f}%")
    if wd.surface_pressure_hpa is not None:
        parts.append(f"P {wd.surface_pressure_hpa:.1f} hPa")
    if wd.cloud_cover_pct is not None:
        parts.append(f"nuvens {wd.cloud_cover_pct:.0f}%")
    if wd.precipitation_mm is not None:
        parts.append(f"chuva {wd.precipitation_mm:.1f} mm")
    if wd.wind_speed_kmh is not None:
        parts.append(f"vento {wd.wind_speed_kmh:.1f} km/h")
    if wd.elevation_m is not None:
        parts.append(f"elev {wd.elevation_m:.0f} m")
    if wd.kp_index is not None:
        parts.append(f"Kp {wd.kp_index:.1f}")
    if not parts:
        return f"indisponível ({wd.error})" if wd.error else "indisponível"
    return "  ".join(parts)
