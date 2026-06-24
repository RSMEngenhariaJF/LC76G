# Guia de Instalação e Distribuição — Ferramenta de Teste GNSS LC76G

Este documento explica como **executar**, **empacotar** (gerar o executável) e
**distribuir** o programa (pasta solta ou instalador), além de personalização e
solução de problemas.

> Versão do app: 1.0.0 · Plataforma alvo: Windows 10/11 (64 bits)

---

## Sumário

1. [Visão geral das formas de uso](#1-visão-geral)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Opção A — Rodar pelo Python (desenvolvimento)](#3-opção-a--rodar-pelo-python)
4. [Opção B — Gerar o executável (PyInstaller)](#4-opção-b--gerar-o-executável)
5. [Opção C — Gerar o instalador (Inno Setup)](#5-opção-c--gerar-o-instalador)
6. [Como distribuir ao usuário final](#6-como-distribuir)
7. [Personalização (ícone, versão, modo debug)](#7-personalização)
8. [Solução de problemas](#8-solução-de-problemas)
9. [Arquivos de build do projeto](#9-arquivos-de-build)

---

## 1. Visão geral

Há três formas de usar/entregar o programa:

| Forma | Para quem | Precisa de Python? |
|-------|-----------|--------------------|
| **A. Python** | Desenvolvimento e testes | Sim |
| **B. Executável (pasta)** | Usuário final (cópia simples) | **Não** |
| **C. Instalador** | Usuário final (instalação padrão) | **Não** |

As opções B e C usam o **PyInstaller** para empacotar o Python e todas as
bibliotecas dentro do próprio aplicativo, então o usuário final **não precisa
instalar nada**.

---

## 2. Pré-requisitos

Para **gerar** o executável/instalador (na máquina de build):

- **Windows 64 bits**.
- **Python 3.8+** (recomendado 3.11), com `pip`. Tkinter já acompanha o Python
  no Windows.
- Dependências do projeto (instaladas automaticamente pelo script de build):
  `pyserial`, `matplotlib`, `python-docx`.
- **PyInstaller** (instalado automaticamente pelo script de build).
- (Opcional) **Inno Setup** para gerar o instalador: <https://jrsoftware.org/isdl.php>
- (Opcional) **UPX** para compactar o executável e reduzir o tamanho:
  <https://upx.github.io/>

O **usuário final** (quem só vai usar) não precisa de nada disso.

---

## 3. Opção A — Rodar pelo Python

Na raiz do projeto:

```bash
pip install -r requirements.txt
python main.py
```

Ou, instalando como pacote (habilita o comando `lc76g-gnss`):

```bash
pip install -e .
lc76g-gnss
```

---

## 4. Opção B — Gerar o executável

### 4.1. Forma simples (script pronto)

Na raiz do projeto, no **PowerShell**:

```powershell
./build_exe.ps1
```

O script:
1. instala as dependências e o PyInstaller;
2. roda o `lc76g_gnss.spec`;
3. gera a pasta **`dist\GNSS-Test\`** contendo o **`GNSS-Test.exe`** e todas
   as bibliotecas (~90 MB no total).

### 4.2. Forma manual

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean lc76g_gnss.spec
```

### 4.3. Resultado

```
dist/
└── GNSS-Test/
    ├── GNSS-Test.exe         <- aplicativo (clique para abrir)
    └── _internal/            <- bibliotecas embutidas (não apagar)
```

> A pasta `build/` que aparece é apenas intermediária e pode ser apagada.
> A entregável é a pasta `dist\GNSS-Test`.

### 4.4. Teste rápido

Dê um duplo clique em `dist\GNSS-Test\GNSS-Test.exe`. A janela deve abrir sem
precisar de Python instalado.

---

## 5. Opção C — Gerar o instalador

Cria um instalador único (`.exe`) com atalhos no Menu Iniciar/Área de trabalho e
desinstalador — a forma mais profissional de entregar.

1. **Gere antes o executável** (Opção B) — o instalador empacota a pasta
   `dist\GNSS-Test`.
2. Instale o **Inno Setup**: <https://jrsoftware.org/isdl.php>
3. Compile o script `installer.iss`:
   - **pela interface:** abra `installer.iss` no *Inno Setup Compiler* e clique
     em **Compile**; ou
   - **pela linha de comando:**
     ```powershell
     & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
     ```
4. O instalador final sai em **`Output\GNSS-Test-Setup.exe`**.

Esse é o arquivo que você envia ao usuário. Ao executá-lo, ele instala o
programa, cria os atalhos e registra o desinstalador no Painel de Controle.

---

## 6. Como distribuir

| Cenário | O que enviar | Como o usuário usa |
|---------|--------------|--------------------|
| **Cópia simples** | A pasta `dist\GNSS-Test` compactada (.zip) | Extrai e roda `GNSS-Test.exe` |
| **Instalação padrão** | O arquivo `Output\GNSS-Test-Setup.exe` | Executa o instalador e usa pelo atalho |

Em ambos os casos **não é necessário instalar Python** na máquina do usuário.

> **Driver USB-serial:** o programa fala com a placa por uma porta serial
> (COM). Em alguns conversores USB-serial (CH340, CP210x, FTDI) o usuário pode
> precisar instalar o **driver do conversor** uma única vez — isso é do hardware,
> não do programa.

---

## 7. Personalização

Tudo no `lc76g_gnss.spec` (executável) e `installer.iss` (instalador):

- **Ícone do app:** crie/obtenha um arquivo `.ico` e ajuste no `lc76g_gnss.spec`:
  ```python
  icon="caminho/para/icone.ico",
  ```
  E no `installer.iss`, se quiser ícone no instalador:
  `SetupIconFile=caminho\para\icone.ico`.
- **Nome/versão/empresa:** edite as `#define` no topo do `installer.iss`
  (`MyAppName`, `MyAppVersion`, `MyAppPublisher`).
- **Versão "debug" (com terminal):** para ver mensagens de erro em campo, gere
  uma variante com console mudando no `lc76g_gnss.spec`:
  ```python
  console=True,
  ```
  e rode o build de novo (de preferência com outro `name` para não sobrescrever).
- **Reduzir tamanho:** instale o UPX e mantenha `upx=True` no spec.

---

## 8. Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Antivírus bloqueia o `.exe` | Falso-positivo comum com PyInstaller | Liberar/assinar o executável; preferir o instalador assinado |
| “Failed to execute script” | Dependência não embutida | Conferir `hiddenimports`/`datas` no spec; rebuildar com `--clean` |
| Gráficos não aparecem | matplotlib não embutido | Garantir matplotlib instalado antes do build |
| Relatório Word falha | `python-docx` não embutido | O spec já inclui (`collect_data_files("docx")`); rebuildar |
| Não lista portas COM | `pyserial` não embutido | O spec já inclui os submódulos de `serial`; rebuildar |
| App não abre, sem erro | Erro silencioso (modo windowed) | Gerar versão `console=True` para ver a mensagem |
| Janela não abre em outra máquina | Falta de runtime do Windows | Instalar o **Microsoft Visual C++ Redistributable** (x64) |

Dica geral: ao mudar dependências, sempre rebuild com `--clean` para evitar
cache antigo:
```powershell
python -m PyInstaller --noconfirm --clean lc76g_gnss.spec
```

---

## 9. Arquivos de build

| Arquivo | Papel |
|---------|-------|
| `lc76g_gnss.spec` | Configuração do PyInstaller (entrada `main.py`, `pathex=src`, dados do docx, submódulos do serial, exclusões). |
| `build_exe.ps1` | Automatiza a geração do executável. |
| `installer.iss` | Script do Inno Setup para o instalador. |
| `requirements.txt` | Dependências de runtime. |
| `pyproject.toml` | Metadados do pacote (também permite `pip install -e .`). |

---

### Resumo rápido

```powershell
# 1) Executável
./build_exe.ps1
#    -> dist\GNSS-Test\GNSS-Test.exe

# 2) Instalador (após o passo 1, com Inno Setup instalado)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
#    -> Output\GNSS-Test-Setup.exe
```
