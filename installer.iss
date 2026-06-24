; Script do Inno Setup para gerar o instalador da Ferramenta de Teste GNSS LC76G.
;
; Pré-requisito: gerar antes o executável com PyInstaller (build_exe.ps1),
; produzindo dist\LC76G-GNSS\.
;
; Como usar:
;   1. Instale o Inno Setup (https://jrsoftware.org/isdl.php).
;   2. Abra este arquivo no Inno Setup Compiler e clique em "Compile"
;      (ou rode:  ISCC.exe installer.iss).
;   3. O instalador sai em Output\LC76G-GNSS-Setup.exe

#define MyAppName "GNSS Test"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Omnilink"
#define MyAppExeName "GNSS-Test.exe"
#define MyAppIcon "src\lc76g_gnss\assets\gnss_test.ico"

[Setup]
AppId={{B2E7B6B0-6C2E-4E1B-9C7A-LC76GGNSS0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\GNSS Test
DefaultGroupName=GNSS Test
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=GNSS-Test-Setup
SetupIconFile={#MyAppIcon}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
; Empacota toda a pasta gerada pelo PyInstaller.
Source: "dist\GNSS-Test\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: nowait postinstall skipifsilent
