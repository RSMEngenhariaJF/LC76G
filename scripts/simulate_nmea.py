"""
simulate_nmea.py
----------------
Demonstração funcional do núcleo (lc76g_gnss.core) SEM hardware: alimenta um fluxo de
sentenças NMEA de exemplo no parser e imprime o resultado, validando checksum,
decodificação de posição e identificação de comandos.

Uso:
    python scripts/simulate_nmea.py
"""

import os
import sys

# Permite executar diretamente sem instalar o pacote (adiciona ./src ao path).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from lc76g_gnss import core

SAMPLE = [
    "$PQTMVERNO,LC76GABNR02A01S,2022/09/14,11:47:03*3D",
    "$PAIR001,004,0*3F",
    "$GNRMC,040143.000,A,3149.334166,N,11706.941670,E,0.01,0.00,010522,,,D,V*0E",
    "$GNGGA,040143.000,3149.334166,N,11706.941670,E,2,36,0.48,61.496,M,,M,,*5E",
    "$GNRMC,,V,,,,,,,,,,N,V*37",          # sem fix
    "$PAIR002*FF",                          # checksum propositalmente errado
]


def main():
    print("=== Demonstração de parsing NMEA (lc76g_gnss.core) ===\n")
    for raw in SAMPLE:
        s = core.parse_nmea(raw)
        chk = {True: "OK", False: "ERRO", None: "ausente"}[s.checksum_ok]
        kind = "proprietária" if s.is_proprietary else f"padrão ({s.talker})"
        print(f"{raw}")
        print(f"   tipo={s.sentence_type:10s} {kind:18s} checksum={chk}")
        if s.sentence_type.endswith("RMC"):
            fix = core.parse_rmc(s)
            print(f"   -> fix válido={fix.valid} lat={fix.latitude} "
                  f"lon={fix.longitude} vel={fix.speed_knots} kn")
        elif s.sentence_type.endswith("GGA"):
            fix = core.parse_gga(s)
            print(f"   -> qualidade={fix.quality} sat={fix.satellites_used} "
                  f"hdop={fix.hdop} alt={fix.altitude} m")
        print()


if __name__ == "__main__":
    main()
