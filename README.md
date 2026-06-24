# GNSS Test — Ferramenta de Teste GNSS (Bypass via UART)

Software com interface gráfica para testar módulos GNSS (**Quectel LC76G** e
família, **u-blox**, **CASIC/AT6558**). A comunicação pode passar por um
microcontrolador que repassa os dados via UART; o comando **`#gps`** coloca o
microcontrolador em modo *bypass*, conectando a porta serial diretamente ao
módulo GPS (saída NMEA 0183 V4.10). Dispositivos u-blox/CASIC conectam direto.

**Autor:** Rafael da Silva Macêdo · **GitHub:** <https://github.com/RSMEngenhariaJF>

## Estrutura do projeto

Layout *src* padrão de projeto Python estruturado:

```
LC76G/
├── main.py                     # ponto de entrada (python main.py)
├── pyproject.toml              # metadados e empacotamento
├── requirements.txt            # dependências (pyserial, matplotlib, python-docx)
├── lc76g_gnss.spec             # build do executável (PyInstaller)
├── build_exe.ps1               # script p/ gerar o .exe
├── installer.iss               # script do instalador (Inno Setup)
├── src/
│   └── lc76g_gnss/             # pacote da aplicação
│       ├── core.py             # primitivas NMEA, parsing, serial (sem GUI)
│       ├── accuracy.py         # ensaio de precisão: haversine, moda, estatísticas
│       ├── weather.py          # clima (Open-Meteo) + Kp (NOAA), opcional
│       ├── ublox_proto.py      # protocolo binário UBX (UBX-CFG-RST)
│       ├── report.py           # relatório do ensaio em Word (.docx)
│       ├── app.py              # interface gráfica (Tkinter)
│       ├── assets/             # ícone do app (gnss_test.ico / .png)
│       └── devices/            # biblioteca modular de dispositivos
│           ├── base.py         # DeviceProfile
│           ├── quectel.py      # LC26G/LC76G/LC86G + catálogo $PAIR
│           ├── ublox.py        # NEO-6M/M10/Beitian (UBX-CFG-RST)
│           ├── casic.py        # AT6558 (CASIC/ZKW, comandos $PCAS)
│           └── generic.py      # receptor NMEA genérico
├── scripts/
│   ├── simulate_nmea.py        # demonstração do parser sem hardware
│   └── make_icon.py            # gera o ícone do app (satélite)
├── tests/                      # test_core/devices/accuracy/weather/report
└── docs/                       # guia de distribuição, relatórios e CSVs
                                #   (datasheets de terceiros não versionados)
```

## Instalação

```bash
pip install -r requirements.txt
```

Tkinter já acompanha a instalação padrão do Python no Windows. Opcionalmente,
para instalar como pacote (e habilitar o comando `lc76g-gnss`):

```bash
pip install -e .
```

## Execução

```bash
python main.py
# ou, se instalado com "pip install -e .":
lc76g-gnss
```

### Fluxo de uso
1. Selecione a **porta** serial e o **baud rate** (padrão do LC76G: `115200`).
2. Clique em **Conectar**.
3. Clique no botão **BYPASS #gps** para acionar o modo bypass do microcontrolador
   (envia `#gps` + terminador, configuráveis na interface).
4. Acompanhe as sentenças NMEA chegando na área de **Log**. Sentenças com
   checksum inválido aparecem em vermelho.
5. O painel **Última posição** mostra latitude/longitude/satélites decodificados
   de RMC/GGA.
6. Use **Salvar log…** para gravar em arquivo e **Limpar log** para zerar.

## Funcionalidades implementadas

**Conexão**
- Listagem automática das portas seriais (com descrição) e botão de atualizar.
- Baud rate selecionável (9600–921600); padrão 115200.
- Conectar/Desconectar com indicador de status colorido.

**Bypass**
- Botão dedicado **#gps** em destaque.
- Comando do bypass e terminador (Nenhum/CR/LF/CR+LF) configuráveis.

**Comandos**
- Catálogo de 11 comandos prontos do LC76G (versão, power on/off, hot/warm/cold
  start, fix rate, salvar/restaurar config, baud rate).
- Campo de comando personalizado com cálculo automático do checksum (`$...*CC`).

**Log**
- Área de log em tempo real com timestamp opcional e auto-scroll.
- TX (envios) e RX (recebidos) diferenciados por cor; erros e checksum inválido
  destacados; contador de linhas.
- Salvar em arquivo (.txt) e limpar.

**Decodificação**
- Parsing de NMEA padrão e proprietário ($PAIR/$PQTM).
- Validação de checksum XOR.
- Extração de posição de RMC e GGA, com conversão de coordenadas para graus
  decimais. A conversão **preserva até 8 casas decimais** (~1 mm, abaixo da
  resolução de campo do NMEA — sem perda); a **exibição é ajustável de 6 a 8
  casas** ("Casas (exibição)" no painel Dispositivo). 6 casas ≈ 0,11 m; 7 ≈
  1,1 cm; 8 ≈ 1,1 mm. Aplica-se aos painéis, tabelas, CSV e relatório.

**Aba "Teste TTFF" (métricas de aquisição)**
- Botões Cold / Warm / Hot start (`$PAIR006` / `$PAIR005` / `$PAIR004`).
- Cronômetro do **TTFF** (tempo até o 1º fix válido) iniciado no envio do start.
- Métricas em tempo real: tipo de fix (2D/3D via GSA), satélites usados (GGA),
  satélites em vista por constelação (GSV), HDOP e posição.
- Tabela de resultados acumulados e exportação para **CSV**.

> Para medir a aquisição do zero use **Cold start (`$PAIR006`)**: apaga tempo,
> posição, almanaque e efemérides. Envie sempre **após** o bypass (`#gps`).
> Cold/Warm/Hot start usam, respectivamente, `$PAIR006`/`$PAIR005`/`$PAIR004`.

**Aba "Teste de Precisão" (erro de distância)**
- **1) Posição inicial:** o botão coleta *N* amostras (padrão 100) e fixa a
  origem pela **moda** das latitudes/longitudes (mais robusta a outliers).
- **Modo de medição (selecionável):** **Da origem** (padrão) mede cada ponto
  contra a origem fixa — informe a distância total desde a origem; ou **Por
  trecho**, que mede contra o ponto anterior — informe quanto andou desde o
  último ponto. O modo trava após o 1º ponto (reinicie para trocar).
- **2) Adicionar ponto:** informe a distância (conforme o modo) e meça; outras
  *N* amostras são coletadas, a posição é obtida pela moda e a **distância
  medida** (haversine) é comparada com a informada. O erro (m e %) é registrado
  na tabela. No modo "Da origem", cada ponto é medido independentemente — não
  acumula; o valor só cresce se você realmente se afastar.
- **Medição parado (distância 0):** informe `0` para medir sem se mover — o erro
  vira a **deriva/repetibilidade** do receptor (erro % fica indefinido e o
  relatório passa a mostrar o erro absoluto em metros por ponto).
- **Finalizar ensaio:** calcula o desempenho (erro médio, MAE, RMS, desvio,
  mín/máx, mediana e erro % absoluto médio) e exibe três gráficos (matplotlib):
  **histograma do erro**, **erro percentual por ponto** e um **diagrama de
  quartis (boxplot) da dispersão das amostras de cada ponto** — mediana, IQR e
  outliers da repetibilidade em cada medida. Opção de salvar os gráficos em PNG;
  os pontos também podem ser exportados em **CSV**.
- **Hora de cada ponto:** cada medição registra a **hora local** e o **UTC do
  GNSS** (na tabela e no CSV), para correlação temporal posterior.
- **Dados meteorológicos (automático ao finalizar):** busca o clima da posição
  da origem via **Open-Meteo** (temperatura, umidade, pressão de superfície e
  ao nível do mar, nuvens, precipitação, vento, elevação) e o **índice Kp** da
  **NOAA SWPC** (distúrbio ionosférico). Aparece no relatório e no cabeçalho do
  CSV. APIs gratuitas e sem chave; se não houver internet, os campos ficam
  vazios sem travar o ensaio. As condições atmosféricas ajudam a explicar
  variações de erro (atraso troposférico/ionosférico) entre ensaios.
- **Emitir relatório (Word .docx):** um botão abre uma caixa de diálogo para
  **título da medição** e **responsável** e gera um relatório com cabeçalho
  (data/hora), resumo descritivo, condições meteorológicas, estatísticas de
  erro, **gráficos**, tabela de pontos (com **satélites usados e em vista ponto
  a ponto**, incluindo o detalhamento por constelação), um **glossário técnico**
  das siglas (TTFF, HDOP, RMS, Kp, NMEA…) e um **anexo com os dados brutos**
  (todas as amostras de cada ponto). Requer `python-docx`.
- Parâmetros ajustáveis: nº de amostras por ponto e casas decimais da moda
  (5 casas ≈ 1,1 m por grupo). A 1 Hz, 100 amostras levam ~100 s por ponto.

## Dispositivos (modular)

A lista de comandos é **modular por dispositivo**, organizada como **um arquivo
por família** no pacote [`src/lc76g_gnss/devices/`](src/lc76g_gnss/devices/).
Cada módulo é descrito por um `DeviceProfile` ([`base.py`](src/lc76g_gnss/devices/base.py)),
que reúne baud rates, comando de bypass, comandos de cold/warm/hot start e o
catálogo de comandos rápidos. Na interface, a caixa **Dispositivo** seleciona o
módulo — ao trocar, a ferramenta reconfigura baud, bypass, botões de start e
catálogo automaticamente. Modos não suportados aparecem como **(n/d)** e ficam
desabilitados.

Perfis incluídos:
- **Quectel** `LC76G`, `LC26G`, `LC86G` ([`quectel.py`](src/lc76g_gnss/devices/quectel.py)) —
  mesma família `$PAIR`/`$PQTM`, com bypass `#gps`.
- **u-blox** `GY-GPS6MV2` (NEO-6M), `u-blox M10 (UBX-M10050)`, `Beitian BN-220`,
  `Beitian BN-880`, `Beitian BK-359` e `u-blox (genérico)`
  ([`ublox.py`](src/lc76g_gnss/devices/ublox.py)) — conexão direta (USB-TTL,
  padrão 9600 bps); cold/warm/hot via **UBX-CFG-RST** binário
  ([`ublox_proto.py`](src/lc76g_gnss/ublox_proto.py)); comandos rápidos `$PUBX`.
- **CASIC/ZKW** `AT6558` ([`casic.py`](src/lc76g_gnss/devices/casic.py)) —
  multi-GNSS; reinício e config por comandos **NMEA `$PCAS`** (não UBX).
- **`Genérico (NMEA)`** ([`generic.py`](src/lc76g_gnss/devices/generic.py)) — só leitura.

> Os comandos de start variam por família: **NMEA** (`$PAIR` da Quectel,
> `$PCAS` do AT6558) ou **binário** (`UBX-CFG-RST` do u-blox). A interface envia
> o formato certo conforme o perfil e rotula o botão como `(PAIR006)`,
> `(PCAS10,2)` ou `(UBX)`.

> **Beitian BK-359:** adicionado como u-blox-compatível; confirme o chipset — se
> não for u-blox, os comandos UBX de reinício podem não ter efeito (a leitura
> NMEA funciona normalmente).

**Adicionar uma nova família de dispositivos:**

```python
# 1) crie src/lc76g_gnss/devices/<fabricante>.py
from .base import DeviceProfile
from ..core import Command

MEU_GPS = DeviceProfile(
    id="MEU_GPS", name="Meu GPS", description="…",
    start_commands={"cold": "…", "warm": "…", "hot": "…"},
    command_catalog=[Command("Rótulo", "PAYLOAD", "descrição")],
    bypass_command="#gps",        # ou None se acesso direto
)
PROFILES = [MEU_GPS]

# 2) registre em src/lc76g_gnss/devices/__init__.py (some a _ALL_PROFILES)
```

## Testes

```bash
python -m unittest discover -s tests -v
# ou, com pytest:
python -m pytest tests -v
```

Cobertura (97 testes): `tests/test_core.py` (núcleo), `tests/test_devices.py`
(dispositivos), `tests/test_accuracy.py` (ensaio de precisão),
`tests/test_weather.py` (clima/Kp, sem rede), `tests/test_report.py` (relatório
Word) e `tests/test_ublox_proto.py` (quadros binários UBX):

| Grupo | O que valida |
|-------|--------------|
| `TestChecksum` | Checksum XOR confere com exemplos do manual (PAIR002/004/864, PQTMVERNO, RMC). |
| `TestBuildSentence` | Montagem `$payload*CC` com/sem terminador e ida-e-volta válida. |
| `TestSplitAndVerify` | Separação payload/checksum e verificação (válido, inválido, ausente, case). |
| `TestCoordinateConversion` | ddmm.mmmm → graus decimais, sinais S/W, campos vazios. |
| `TestParseNmea` | Identifica talker, tipo, proprietária vs padrão, flag de checksum. |
| `TestParseFix` | Extrai posição de RMC/GGA, trata "sem fix", rejeita tipo cruzado. |
| `TestSerialManager` | Abrir/fechar, escrita codificada, erro sem porta, leitura quebrada em linhas (com porta serial falsa). |
| `TestRegistry` / `TestQuectelFamily` | Registro de perfis, ids/nomes únicos, família $PAIR compartilha catálogo/starts. |
| `TestProfilesProduceValidSentences` | Todo start/comando de cada perfil gera NMEA com checksum válido. |
| `TestHaversine` / `TestModeValue` / `TestModePosition` | Distância geodésica e posição pela moda das amostras. |
| `TestAccuracyPoint` / `TestErrorStats` | Erro com sinal/percentual e estatísticas (média, MAE, RMS, desvio). |
| `TestParsing` / `TestFetch` / `TestFormatSummary` | Parsing de Open-Meteo/Kp, busca com falha de rede graciosa, resumo. |
| `TestReport` | Glossário presente e geração do .docx (com e sem clima). |
| `TestUbloxDevices` / `TestCfgRstFrames` | Perfil GY-GPS6MV2 e quadros UBX-CFG-RST (cold/warm/hot) corretos. |

## Distribuição (executável / instalador)

Para entregar o programa a quem não tem Python, gere um **executável Windows**
com **PyInstaller** e, opcionalmente, um **instalador** com **Inno Setup**.

**1) Gerar o executável** (na raiz do projeto, PowerShell):

```powershell
./build_exe.ps1
```

Isso instala as dependências + PyInstaller e roda o spec [`lc76g_gnss.spec`](lc76g_gnss.spec),
produzindo a pasta **`dist\GNSS-Test\`** com o **`GNSS-Test.exe`** (aplicativo
de janela, sem console) e todas as bibliotecas embutidas (~90 MB). Para
distribuir “solto”, basta **compactar e enviar a pasta `dist\GNSS-Test`
inteira** — o usuário roda o `.exe` direto, sem instalar nada.

**2) Gerar um instalador** (opcional, recomendado para distribuição):

- Instale o [Inno Setup](https://jrsoftware.org/isdl.php);
- Compile [`installer.iss`](installer.iss) (abra no Inno Setup Compiler →
  *Compile*, ou rode `ISCC.exe installer.iss`);
- Sai um instalador único em **`Output\GNSS-Test-Setup.exe`**, com atalhos no
  Menu Iniciar / Área de trabalho e desinstalador.

> O spec usa o layout `src/` (via `pathex=["src"]`) e já inclui os dados do
> `python-docx`, os submódulos do `pyserial` e o matplotlib. Para um ícone
> próprio, aponte um `.ico` no campo `icon=` do spec. UPX é opcional (reduz o
> tamanho se instalado).

## Verificação sem hardware

```bash
python scripts/simulate_nmea.py
```

Alimenta sentenças de exemplo no parser e imprime tipo, checksum e posição.

## Referências

- Quectel LC76G Series GNSS Specification V1.1
- Quectel LC26G/LC76G/LC86G GNSS Protocol Specification V1.5 (comandos $PAIR/$PQTM)
