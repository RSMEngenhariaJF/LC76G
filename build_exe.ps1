# Gera o executável (onedir) do GNSS Test com PyInstaller.
#
# Uso (PowerShell, na raiz do projeto):
#     ./build_exe.ps1
#
# Saída: dist\GNSS-Test\GNSS-Test.exe

$ErrorActionPreference = "Stop"

Write-Host "==> Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

Write-Host "==> Gerando executavel..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean lc76g_gnss.spec

$exe = "dist\GNSS-Test\GNSS-Test.exe"
if (Test-Path $exe) {
    Write-Host "==> Pronto: $exe" -ForegroundColor Green
    Write-Host "    Distribua a pasta dist\GNSS-Test inteira, ou gere o" -ForegroundColor Green
    Write-Host "    instalador com Inno Setup (installer.iss)." -ForegroundColor Green
} else {
    Write-Error "Falha: executavel nao encontrado."
}
