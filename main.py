"""
main.py
-------
Ponto de entrada da ferramenta de teste GNSS. Executa a interface gráfica.

Uso:
    python main.py

(Alternativamente, após instalar o pacote: ``lc76g-gnss``.)
"""

import os
import sys

# Permite rodar sem instalar o pacote: adiciona ./src ao caminho de importação.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from lc76g_gnss.app import main

if __name__ == "__main__":
    main()
