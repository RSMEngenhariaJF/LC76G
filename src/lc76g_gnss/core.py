"""
gps_core.py
-----------
Núcleo (sem dependência de interface gráfica) para comunicação com o módulo
GNSS Quectel LC76G através de um microcontrolador que repassa os dados via
UART (modo *bypass* acionado pelo comando `#gps`).

Este módulo concentra toda a lógica testável:
  * Cálculo e verificação de checksum NMEA 0183 (XOR).
  * Montagem de sentenças NMEA / comandos $PAIR e $PQTM.
  * Parsing de sentenças recebidas (RMC, GGA, GSV, PAIR001, etc.).
  * Conversão de coordenadas ddmm.mmmm -> graus decimais.
  * Catálogo de comandos suportados pelo módulo.
  * Gerenciador de porta serial (SerialManager) com thread de leitura.

A separação permite testar o protocolo sem hardware conectado.

Referências: Quectel LC26G&LC26G-T&LC76G&LC86G GNSS Protocol Specification V1.5.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Constantes de protocolo
# ---------------------------------------------------------------------------

#: Comando enviado ao microcontrolador para entrar em modo bypass com o GPS.
BYPASS_COMMAND = "#gps"

#: Terminadores de linha possíveis para os comandos.
LINE_ENDINGS = {
    "Nenhum": "",
    "CR": "\r",
    "LF": "\n",
    "CR+LF": "\r\n",
}

#: Baud rates suportados pelo LC76G (UART ajustável de 9600 a 921600 bps).
BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

#: Baud rate padrão de fábrica do módulo LC76G.
DEFAULT_BAUD = 115200


# ---------------------------------------------------------------------------
# Checksum NMEA
# ---------------------------------------------------------------------------

def nmea_checksum(payload: str) -> str:
    """Calcula o checksum NMEA (XOR de 8 bits) do texto entre `$` e `*`.

    Retorna dois caracteres hexadecimais em maiúsculas, ex.: ``"38"``.
    """
    chk = 0
    for ch in payload:
        chk ^= ord(ch)
    return f"{chk:02X}"


def build_sentence(payload: str, line_ending: str = "\r\n") -> str:
    """Monta uma sentença NMEA completa a partir do *payload*.

    `payload` é o conteúdo entre `$` e `*` (sem eles), ex.: ``"PAIR002"``.
    Retorna algo como ``"$PAIR002*38\\r\\n"``.
    """
    return f"${payload}*{nmea_checksum(payload)}{line_ending}"


def split_sentence(line: str):
    """Separa uma sentença NMEA em (payload, checksum_informado).

    Aceita linhas com ou sem `$` inicial e com ou sem checksum.
    Retorna ``(payload, checksum)`` onde ``checksum`` é ``None`` se ausente.
    """
    s = line.strip()
    if s.startswith("$"):
        s = s[1:]
    if "*" in s:
        payload, _, chk = s.partition("*")
        chk = chk.strip()[:2].upper() if chk.strip() else None
        return payload, chk
    return s, None


def verify_checksum(line: str) -> Optional[bool]:
    """Verifica o checksum de uma sentença NMEA.

    Retorna ``True``/``False`` se houver checksum, ou ``None`` se a sentença
    não contiver checksum para validar.
    """
    payload, chk = split_sentence(line)
    if chk is None:
        return None
    return nmea_checksum(payload).upper() == chk.upper()


# ---------------------------------------------------------------------------
# Conversão de coordenadas
# ---------------------------------------------------------------------------

def dm_to_decimal(value: str, hemisphere: str,
                  ndigits: int = 8) -> Optional[float]:
    """Converte coordenada NMEA ``ddmm.mmmm`` / ``dddmm.mmmm`` em graus decimais.

    `hemisphere` é ``N``/``S``/``E``/``W``. Retorna ``None`` para entrada vazia
    ou inválida (campos vazios são comuns quando não há fix).

    ``ndigits`` controla o arredondamento (padrão 8 casas ≈ 1 mm, abaixo da
    resolução de campo do NMEA — preserva toda a precisão disponível; a
    exibição reduz para o número de casas escolhido pelo usuário).
    """
    if not value or not hemisphere:
        return None
    try:
        dot = value.index(".")
    except ValueError:
        # Sem ponto decimal: assume os 2 últimos dígitos como minutos.
        if len(value) < 3:
            return None
        dot = len(value) - 2
    deg_len = dot - 2  # minutos sempre ocupam 2 dígitos antes do ponto
    if deg_len < 0:
        return None
    try:
        degrees = int(value[:deg_len]) if deg_len > 0 else 0
        minutes = float(value[deg_len:])
    except ValueError:
        return None
    decimal = degrees + minutes / 60.0
    if hemisphere.upper() in ("S", "W"):
        decimal = -decimal
    return round(decimal, ndigits)


# ---------------------------------------------------------------------------
# Parsing de sentenças
# ---------------------------------------------------------------------------

@dataclass
class NmeaSentence:
    """Resultado estruturado do parsing de uma sentença NMEA."""

    raw: str
    payload: str
    fields: list
    checksum: Optional[str]
    checksum_ok: Optional[bool]
    talker: str            # ex.: "GN", "GP" ou "P" (proprietária)
    sentence_type: str     # ex.: "RMC", "GGA", "PAIR", "PQTM..."
    is_proprietary: bool


def parse_nmea(line: str) -> Optional[NmeaSentence]:
    """Faz o parsing genérico de uma sentença NMEA.

    Retorna ``None`` se a linha estiver vazia. Não lança exceção para linhas
    malformadas — apenas preenche o que conseguir.
    """
    if line is None:
        return None
    raw = line.rstrip("\r\n")
    if not raw.strip():
        return None

    payload, chk = split_sentence(raw)
    fields = payload.split(",")
    address = fields[0] if fields else ""

    is_proprietary = address.startswith("P")
    if is_proprietary:
        talker = "P"
        sentence_type = address  # ex.: PAIR001, PQTMVERNO
    else:
        talker = address[:2]
        sentence_type = address[2:]

    checksum_ok = None
    if chk is not None:
        checksum_ok = nmea_checksum(payload).upper() == chk.upper()

    return NmeaSentence(
        raw=raw,
        payload=payload,
        fields=fields,
        checksum=chk,
        checksum_ok=checksum_ok,
        talker=talker,
        sentence_type=sentence_type,
        is_proprietary=is_proprietary,
    )


@dataclass
class GnssFix:
    """Posição/estado extraído de sentenças RMC e/ou GGA."""

    valid: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    utc: Optional[str] = None
    date: Optional[str] = None
    speed_knots: Optional[float] = None
    course: Optional[float] = None
    altitude: Optional[float] = None
    satellites_used: Optional[int] = None
    hdop: Optional[float] = None
    quality: Optional[int] = None


def _to_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_rmc(sentence: NmeaSentence) -> Optional[GnssFix]:
    """Extrai dados de uma sentença RMC já parseada.

    Formato: $..RMC,UTC,Status,Lat,N/S,Lon,E/W,SOG,COG,Date,...
    """
    if not sentence.sentence_type.endswith("RMC"):
        return None
    f = sentence.fields
    if len(f) < 10:
        return None
    fix = GnssFix()
    fix.utc = f[1] or None
    fix.valid = (f[2] == "A")
    fix.latitude = dm_to_decimal(f[3], f[4])
    fix.longitude = dm_to_decimal(f[5], f[6])
    fix.speed_knots = _to_float(f[7])
    fix.course = _to_float(f[8])
    fix.date = f[9] or None
    return fix


def parse_gsv(sentence: NmeaSentence):
    """Extrai (talker, satélites_em_vista, msg_num, total_msgs) de um GSV.

    Formato: $xxGSV,<TotalMsgs>,<MsgNum>,<SatsInView>,...
    Retorna ``None`` se não for GSV. ``satélites_em_vista`` é por constelação
    (mesmo valor repetido em todas as mensagens daquele talker).
    """
    if not sentence.sentence_type.endswith("GSV"):
        return None
    f = sentence.fields
    if len(f) < 4:
        return None
    return (sentence.talker, _to_int(f[3]), _to_int(f[2]), _to_int(f[1]))


def parse_gsa_fix_type(sentence: NmeaSentence):
    """Retorna o tipo de fix de um GSA: 1 = sem fix, 2 = 2D, 3 = 3D.

    Formato: $xxGSA,<OpMode>,<NavMode>,<sats...>. ``NavMode`` é o campo 2.
    Retorna ``None`` se não for GSA.
    """
    if not sentence.sentence_type.endswith("GSA"):
        return None
    f = sentence.fields
    if len(f) < 3:
        return None
    return _to_int(f[2])


def is_valid_fix(sentence: NmeaSentence) -> bool:
    """Indica se a sentença representa um fix válido (para medir TTFF).

    Considera RMC com Status = A ou GGA com Quality > 0.
    """
    if sentence.sentence_type.endswith("RMC"):
        fix = parse_rmc(sentence)
        return bool(fix and fix.valid)
    if sentence.sentence_type.endswith("GGA"):
        fix = parse_gga(sentence)
        return bool(fix and fix.valid)
    return False


def parse_gga(sentence: NmeaSentence) -> Optional[GnssFix]:
    """Extrai dados de uma sentença GGA já parseada.

    Formato: $..GGA,UTC,Lat,N/S,Lon,E/W,Quality,NumSat,HDOP,Alt,M,...
    """
    if not sentence.sentence_type.endswith("GGA"):
        return None
    f = sentence.fields
    if len(f) < 10:
        return None
    fix = GnssFix()
    fix.utc = f[1] or None
    fix.latitude = dm_to_decimal(f[2], f[3])
    fix.longitude = dm_to_decimal(f[4], f[5])
    fix.quality = _to_int(f[6])
    fix.valid = (fix.quality is not None and fix.quality > 0)
    fix.satellites_used = _to_int(f[7])
    fix.hdop = _to_float(f[8])
    fix.altitude = _to_float(f[9])
    return fix


class SatelliteTracker:
    """Acumula a contagem de satélites em vista por constelação (via GSV).

    Cada talker (GP, GL, GA, GB...) reporta seu próprio total em vista; o total
    geral é a soma entre constelações. Use ``feed`` com cada NmeaSentence e leia
    ``total_in_view`` / ``per_constellation``.
    """

    def __init__(self):
        self.per_constellation = {}

    def feed(self, sentence: NmeaSentence) -> bool:
        """Atualiza a contagem se a sentença for GSV. Retorna True se atualizou."""
        gsv = parse_gsv(sentence)
        if gsv is None:
            return False
        talker, in_view, _msg_num, _total = gsv
        if in_view is not None:
            self.per_constellation[talker] = in_view
            return True
        return False

    @property
    def total_in_view(self) -> int:
        return sum(self.per_constellation.values())

    def reset(self):
        self.per_constellation.clear()


# ---------------------------------------------------------------------------
# Estrutura de comando
# ---------------------------------------------------------------------------
# A definição dos comandos de cada módulo fica na biblioteca de dispositivos
# (pacote `lc76g_gnss.devices`), um arquivo por família de hardware. Aqui mora
# apenas a estrutura genérica `Command` e o atalho de montagem.

@dataclass
class Command:
    """Descreve um comando rápido enviável ao módulo."""

    label: str       # texto exibido na interface
    payload: str     # conteúdo entre $ e * (checksum calculado ao enviar)
    description: str


def build_command(payload: str, line_ending: str = "\r\n") -> str:
    """Atalho para montar a sentença completa de um comando do catálogo."""
    return build_sentence(payload, line_ending)


# ---------------------------------------------------------------------------
# Gerenciador de porta serial
# ---------------------------------------------------------------------------

def list_serial_ports():
    """Lista as portas seriais disponíveis como ``[(device, descricao), ...]``.

    Importa pyserial sob demanda para que o núcleo possa ser importado em
    ambientes sem a biblioteca (ex.: parte dos testes).
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [(p.device, p.description) for p in list_ports.comports()]


class SerialManager:
    """Encapsula a porta serial e uma thread de leitura por linhas.

    Os dados recebidos são entregues via callback ``on_line(texto)`` e os
    erros via ``on_error(mensagem)``. O *factory* de serial pode ser injetado
    para permitir testes sem hardware.
    """

    def __init__(self, on_line: Callable[[str], None],
                 on_error: Optional[Callable[[str], None]] = None,
                 serial_factory: Optional[Callable] = None,
                 on_bytes: Optional[Callable[[bytes], None]] = None):
        self._on_line = on_line
        self._on_error = on_error or (lambda msg: None)
        # Callback opcional com os bytes crus recebidos (para visão HEX/contagem).
        self._on_bytes = on_bytes or (lambda data: None)
        self._serial_factory = serial_factory
        self._serial = None
        self._reader: Optional[threading.Thread] = None
        self._running = threading.Event()
        #: Tempo (s) sem novos bytes após o qual um buffer parcial é entregue.
        self.idle_flush = 0.4

    @property
    def is_open(self) -> bool:
        return self._serial is not None and getattr(self._serial, "is_open", False)

    def open(self, port: str, baudrate: int = DEFAULT_BAUD, timeout: float = 0.2):
        """Abre a porta e inicia a thread de leitura."""
        if self.is_open:
            self.close()
        if self._serial_factory is not None:
            self._serial = self._serial_factory(port, baudrate, timeout)
        else:
            import serial  # importado sob demanda
            self._serial = serial.Serial(port=port, baudrate=baudrate,
                                         timeout=timeout)
        self._running.set()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self):
        """Para a leitura e fecha a porta."""
        self._running.clear()
        if self._reader is not None:
            self._reader.join(timeout=1.0)
            self._reader = None
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def write_bytes(self, data: bytes):
        """Envia bytes crus pela porta (ex.: comandos binários UBX)."""
        if not self.is_open:
            raise RuntimeError("Porta serial não está aberta.")
        self._serial.write(data)
        try:
            self._serial.flush()
        except Exception:
            pass

    def write_line(self, text: str):
        """Envia texto pela porta (codificado em ASCII/latin-1)."""
        self.write_bytes(text.encode("latin-1", errors="replace"))

    def _read_loop(self):
        buffer = b""
        last_rx = None  # instante do último byte recebido (para flush por ociosidade)
        while self._running.is_set():
            try:
                chunk = self._serial.read(256)
            except Exception as exc:  # porta desconectada, etc.
                if self._running.is_set():
                    self._on_error(f"Erro de leitura: {exc}")
                break
            if chunk:
                self._on_bytes(chunk)
                buffer += chunk
                last_rx = time.monotonic()
                while b"\n" in buffer:
                    line, _, buffer = buffer.partition(b"\n")
                    text = line.decode("latin-1", errors="replace").rstrip("\r")
                    if text:
                        self._on_line(text)
            elif buffer and last_rx is not None and \
                    (time.monotonic() - last_rx) >= self.idle_flush:
                # Resposta sem terminador (ex.: prompt/ACK do microcontrolador):
                # entrega o que houver para o usuário não ficar "no escuro".
                text = buffer.decode("latin-1", errors="replace").rstrip("\r")
                buffer = b""
                last_rx = None
                if text:
                    self._on_line(text)
        # entrega resto do buffer ao encerrar
        if buffer:
            text = buffer.decode("latin-1", errors="replace").strip()
            if text:
                self._on_line(text)
