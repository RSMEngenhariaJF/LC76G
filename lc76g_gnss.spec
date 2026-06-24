# -*- mode: python ; coding: utf-8 -*-
"""
Especificação do PyInstaller para a Ferramenta de Teste GNSS LC76G.

Gera um aplicativo Windows (modo "onedir": pasta com .exe + dependências) sem
console, pronto para ser empacotado em instalador (ver installer.iss).

Build:
    python -m PyInstaller --noconfirm --clean lc76g_gnss.spec
Saída:
    dist/GNSS-Test/GNSS-Test.exe
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Dados/módulos que o PyInstaller não detecta sozinho:
datas = []
datas += collect_data_files("docx")          # template default.docx do python-docx
datas += [                                    # ícone do app (janela em runtime)
    ("src/lc76g_gnss/assets/gnss_test.ico", "lc76g_gnss/assets"),
    ("src/lc76g_gnss/assets/gnss_test.png", "lc76g_gnss/assets"),
]

hiddenimports = []
hiddenimports += collect_submodules("serial")  # pyserial (serial.tools.list_ports)

# Backends/bibliotecas grandes que não usamos — reduz o tamanho do pacote.
excludes = ["PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "IPython",
            "pytest", "notebook", "tornado"]

a = Analysis(
    ["main.py"],
    pathex=["src"],            # encontra o pacote lc76g_gnss no layout src/
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ["serial.tools.list_ports"],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GNSS-Test",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,             # aplicativo de janela (sem terminal)
    icon="src/lc76g_gnss/assets/gnss_test.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GNSS-Test",
)
