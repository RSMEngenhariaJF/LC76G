"""
lc76g_gnss.accuracy
-------------------
Cálculos do **ensaio de precisão** (sem dependência de interface gráfica):

  * distância geodésica entre dois pontos (fórmula de haversine);
  * posição representativa de uma amostra pela **moda** das coordenadas;
  * estatísticas de erro de distância (média, RMS, desvio, MAE, máx, %…).

A separação permite testar a matemática sem hardware nem GUI.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

#: Raio médio da Terra (IUGG), em metros.
EARTH_RADIUS_M = 6371008.8

Sample = Tuple[float, float]  # (latitude, longitude) em graus decimais


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos (graus decimais) via haversine."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2.0) ** 2)
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def mode_value(values: Sequence[float], decimals: int = 5) -> Optional[float]:
    """Moda de uma amostra contínua.

    Coordenadas GNSS quase nunca se repetem bit a bit, então arredondamos a
    ``decimals`` casas (≈1,1 m com 5 casas) e tomamos o valor mais frequente.
    Se nenhum valor se repetir, cai para a **mediana** (estimador central
    robusto). Empates de moda são resolvidos pela mediana das modas.
    """
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    rounded = [round(v, decimals) for v in vals]
    counts = Counter(rounded)
    top = max(counts.values())
    if top == 1:
        return statistics.median(vals)
    modes = sorted(v for v, c in counts.items() if c == top)
    return modes[len(modes) // 2]


def mode_position(samples: Sequence[Sample],
                  decimals: int = 5) -> Optional[Sample]:
    """Posição ``(lat, lon)`` pela moda independente de cada coordenada."""
    lats = [s[0] for s in samples if s and s[0] is not None]
    lons = [s[1] for s in samples if s and s[1] is not None]
    if not lats or not lons:
        return None
    return (mode_value(lats, decimals), mode_value(lons, decimals))


@dataclass
class AccuracyPoint:
    """Um ponto medido no ensaio de precisão.

    ``known_distance`` é a distância informada pelo usuário **do trecho** (quanto
    andou desde o ponto anterior). ``measured_distance`` é a distância haversine
    entre a posição do ponto anterior e a posição medida atual (moda das
    amostras) — medição por trecho, sem acúmulo.
    """

    index: int
    known_distance: float
    lat: float
    lon: float
    measured_distance: float
    n_samples: int
    hdop: Optional[float] = None
    sats: Optional[int] = None             # satélites usados na solução (GGA)
    sats_in_view: Optional[int] = None     # satélites em vista (GSV)
    view_breakdown: str = ""               # vistos por constelação, ex. "GP:8 GL:6"
    time_local: Optional[str] = None   # hora local da medição (YYYY-MM-DD HH:MM:SS)
    gnss_utc: Optional[str] = None     # UTC do GNSS na última amostra (hhmmss.sss)
    samples: list = field(default_factory=list)  # amostras brutas [(lat, lon), ...]
    base_lat: Optional[float] = None   # posição de onde a distância foi medida
    base_lon: Optional[float] = None   # (origem ou ponto anterior, conforme o modo)

    @property
    def error(self) -> float:
        """Erro com sinal (m): medido − real (positivo = superestimou)."""
        return self.measured_distance - self.known_distance

    @property
    def abs_error(self) -> float:
        return abs(self.error)

    @property
    def error_pct(self) -> Optional[float]:
        """Erro percentual relativo à distância real (``None`` se real = 0)."""
        if self.known_distance == 0:
            return None
        return self.error / self.known_distance * 100.0


def sample_deviations_m(point: AccuracyPoint) -> List[float]:
    """Distâncias (m) de cada amostra bruta até a posição (moda) do ponto.

    Quantifica a **dispersão/repetibilidade** das amostras daquele ponto — base
    do diagrama de quartis (boxplot) por medida. Lista vazia se o ponto não
    guardou amostras.
    """
    if not point.samples:
        return []
    return [haversine_m(point.lat, point.lon, la, lo)
            for la, lo in point.samples
            if la is not None and lo is not None]


def sample_errors_m(point: AccuracyPoint) -> List[float]:
    """Erro de distância (m) de **cada amostra bruta** do ponto.

    Para cada amostra, mede a distância da base (origem ou ponto anterior) até
    a amostra e subtrai a distância informada — ou seja, o mesmo erro do ponto,
    mas calculado por amostra. Permite montar um histograma rico já com poucos
    pontos (cada ponto contribui com ~N amostras). Lista vazia se faltar base
    ou amostras.
    """
    if not point.samples or point.base_lat is None or point.base_lon is None:
        return []
    return [haversine_m(point.base_lat, point.base_lon, la, lo)
            - point.known_distance
            for la, lo in point.samples
            if la is not None and lo is not None]


def error_stats(points: Sequence[AccuracyPoint]) -> dict:
    """Estatísticas de erro de distância de uma lista de :class:`AccuracyPoint`.

    Retorna um dicionário com ``n`` e, se houver pontos, as métricas de erro em
    metros (média, MAE, mediana, RMS, desvio, mín/máx absolutos) e o erro
    percentual absoluto médio.
    """
    out: dict = {"n": len(points)}
    if not points:
        return out
    errs = [p.error for p in points]
    abserrs = [p.abs_error for p in points]
    out["mean_error"] = statistics.fmean(errs)
    out["mean_abs_error"] = statistics.fmean(abserrs)        # MAE
    out["median_error"] = statistics.median(errs)
    out["rms_error"] = math.sqrt(statistics.fmean([e * e for e in errs]))
    out["std_error"] = statistics.pstdev(errs) if len(errs) > 1 else 0.0
    out["min_abs_error"] = min(abserrs)
    out["max_abs_error"] = max(abserrs)
    pcts = [abs(p.error_pct) for p in points if p.error_pct is not None]
    out["mean_abs_error_pct"] = statistics.fmean(pcts) if pcts else None
    return out
