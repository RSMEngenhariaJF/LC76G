"""
gps_bypass_tool.py
------------------
Interface gráfica (Tkinter) para teste do módulo GNSS Quectel LC76G.

Permite:
  * Conectar/desconectar a uma porta serial (UART do microcontrolador).
  * Acionar o modo *bypass* enviando o comando `#gps`.
  * Visualizar, em tempo real, o log de dados recebidos (NMEA).
  * Enviar comandos $PAIR/$PQTM prontos ou personalizados (checksum auto).
  * Acompanhar a última posição (latitude/longitude/satélites) decodificada.
  * Salvar e limpar o log.

Execução:
    python gps_bypass_tool.py

Requer: pyserial (pip install pyserial). Tkinter já acompanha o Python.
"""

from __future__ import annotations

import csv
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from . import __version__ as APP_VERSION
from . import accuracy
from . import core
from . import devices
from . import weather

# --- Identificação do projeto (aba "Sobre") -------------------------------
CREATOR = "Rafael da Silva Macêdo"
#: Usuário e URL do GitHub do autor.
GITHUB_USER = "RSMEngenhariaJF"
GITHUB_PROFILE = "https://github.com/RSMEngenhariaJF"
GITHUB_REPO = "https://github.com/RSMEngenhariaJF/LC76G"


def _fmt(value) -> str:
    """Formata número para CSV (vazio se ``None``)."""
    return "" if value is None else f"{value}"


class GpsBypassApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GNSS Test — Quectel LC76G")
        self.root.geometry("900x680")
        self.root.minsize(760, 520)
        # Ícone do aplicativo (satélite). Caminho relativo ao módulo, funciona
        # tanto em desenvolvimento quanto no executável (onedir do PyInstaller).
        try:
            icon = os.path.join(os.path.dirname(__file__), "assets",
                                "gnss_test.ico")
            if os.path.exists(icon):
                self.root.iconbitmap(icon)
        except Exception:
            pass

        # Dispositivo (perfil) selecionado. Define baud, bypass, starts e
        # catálogo de comandos. Trocar de módulo é só escolher outro perfil.
        self.profile = devices.default_profile()
        self._profiles_by_name = {p.name: p for p in devices.list_profiles()}

        # Fila thread-safe: a thread de leitura serial publica eventos aqui e a
        # GUI os consome no laço do Tkinter (via after).
        self._events: "queue.Queue[tuple]" = queue.Queue()
        self.serial = core.SerialManager(
            on_line=lambda line: self._events.put(("rx", line)),
            on_error=lambda msg: self._events.put(("error", msg)),
            on_bytes=lambda data: self._events.put(("bytes", data)),
        )

        self.last_fix = core.GnssFix()
        self._rx_bytes = 0

        # Estado do teste de TTFF (tempo para o primeiro fix).
        self.tracker = core.SatelliteTracker()
        self.test_active = False
        self.test_t0 = None
        self.test_ttff = None
        self.test_kind = None
        self.test_fix_type = None
        self.test_results = []

        # Estado do ensaio de precisão.
        self.acc_collecting = False          # coletando amostras agora?
        self.acc_target = "ref"              # "ref" (origem) ou "point"
        self.acc_samples = []                # [(lat, lon), ...] em coleta
        self.acc_hdops = []                  # hdop por amostra (para média)
        self.acc_sats = []                   # sat. usados por amostra
        self.acc_last_utc = None             # dedupe por época (1 amostra/época)
        self.acc_reference = None            # (lat, lon) da origem
        self.acc_last_pos = None             # (lat, lon) do ponto anterior (base do trecho)
        self.acc_points = []                 # lista de accuracy.AccuracyPoint
        self.acc_pending_known = 0.0         # distância informada do trecho atual
        self.acc_weather = None              # weather.WeatherData do ensaio
        self.acc_tracker = core.SatelliteTracker()  # satélites em vista (GSV)

        self._build_ui()
        self._apply_profile()      # configura baud/bypass/starts/catálogo do perfil
        self._refresh_ports()
        self._poll_events()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        pad = {"padx": 4, "pady": 4}

        # --- Dispositivo ---------------------------------------------------
        dev = ttk.LabelFrame(self.root, text="Dispositivo")
        dev.pack(fill="x", **pad)
        ttk.Label(dev, text="Módulo:").grid(row=0, column=0, sticky="w", **pad)
        self.device_var = tk.StringVar(value=self.profile.name)
        self.device_combo = ttk.Combobox(
            dev, textvariable=self.device_var, width=26, state="readonly",
            values=[p.name for p in devices.list_profiles()])
        self.device_combo.grid(row=0, column=1, sticky="w", **pad)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        self.device_desc_var = tk.StringVar(value=self.profile.description)
        ttk.Label(dev, textvariable=self.device_desc_var,
                  foreground="#555").grid(row=0, column=2, sticky="w", **pad)
        dev.columnconfigure(2, weight=1)
        # Casas decimais de exibição das coordenadas (a conversão preserva 8;
        # aqui o usuário escolhe quantas mostrar — de 6 a 8).
        ttk.Label(dev, text="Casas (exibição):").grid(
            row=0, column=3, sticky="e", **pad)
        self.coord_dec_var = tk.StringVar(value="6")
        ttk.Spinbox(dev, from_=6, to=8, width=4,
                    textvariable=self.coord_dec_var).grid(
            row=0, column=4, sticky="e", **pad)

        # --- Conexão -------------------------------------------------------
        conn = ttk.LabelFrame(self.root, text="Conexão")
        conn.pack(fill="x", **pad)

        ttk.Label(conn, text="Porta:").grid(row=0, column=0, sticky="w", **pad)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_var,
                                       width=28, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="w", **pad)

        ttk.Button(conn, text="↻", width=3,
                   command=self._refresh_ports).grid(row=0, column=2, **pad)

        ttk.Label(conn, text="Baud:").grid(row=0, column=3, sticky="w", **pad)
        self.baud_var = tk.StringVar(value=str(core.DEFAULT_BAUD))
        self.baud_combo = ttk.Combobox(conn, textvariable=self.baud_var, width=10,
                                       values=[str(b) for b in core.BAUD_RATES])
        self.baud_combo.grid(row=0, column=4, sticky="w", **pad)

        self.connect_btn = ttk.Button(conn, text="Conectar",
                                      command=self._toggle_connection)
        self.connect_btn.grid(row=0, column=5, **pad)

        self.status_var = tk.StringVar(value="● Desconectado")
        self.status_lbl = ttk.Label(conn, textvariable=self.status_var,
                                    foreground="#b00020")
        self.status_lbl.grid(row=0, column=6, sticky="e", **pad)
        conn.columnconfigure(6, weight=1)

        # --- Comandos ------------------------------------------------------
        cmd = ttk.LabelFrame(self.root, text="Comandos")
        cmd.pack(fill="x", **pad)

        # Bypass em destaque
        self.bypass_btn = tk.Button(
            cmd, text="BYPASS  #gps", command=self._send_bypass,
            bg="#1565c0", fg="white", activebackground="#0d47a1",
            activeforeground="white", font=("Segoe UI", 11, "bold"),
            relief="raised", padx=12, pady=6, state="disabled")
        self.bypass_btn.grid(row=0, column=0, rowspan=2, sticky="ns", **pad)

        ttk.Label(cmd, text="Comando do bypass:").grid(row=0, column=1, sticky="w", **pad)
        self.bypass_cmd_var = tk.StringVar(value=core.BYPASS_COMMAND)
        ttk.Entry(cmd, textvariable=self.bypass_cmd_var, width=14).grid(
            row=0, column=2, sticky="w", **pad)

        ttk.Label(cmd, text="Terminador:").grid(row=0, column=3, sticky="w", **pad)
        self.ending_var = tk.StringVar(value="CR+LF")
        ttk.Combobox(cmd, textvariable=self.ending_var, width=8, state="readonly",
                     values=list(core.LINE_ENDINGS.keys())).grid(
            row=0, column=4, sticky="w", **pad)

        # Comandos do catálogo
        ttk.Label(cmd, text="Comando rápido:").grid(row=1, column=1, sticky="w", **pad)
        self.catalog_var = tk.StringVar()
        self.catalog_combo = ttk.Combobox(
            cmd, textvariable=self.catalog_var, width=34, state="readonly",
            values=[c.label for c in self.profile.command_catalog])
        self.catalog_combo.grid(row=1, column=2, columnspan=2, sticky="w", **pad)
        self.catalog_combo.bind("<<ComboboxSelected>>", self._on_catalog_select)
        self.send_catalog_btn = ttk.Button(cmd, text="Enviar",
                                           command=self._send_catalog, state="disabled")
        self.send_catalog_btn.grid(row=1, column=4, sticky="w", **pad)

        # Comando personalizado
        ttk.Label(cmd, text="Personalizado:").grid(row=2, column=1, sticky="w", **pad)
        self.custom_var = tk.StringVar()
        custom_entry = ttk.Entry(cmd, textvariable=self.custom_var, width=40)
        custom_entry.grid(row=2, column=2, columnspan=2, sticky="we", **pad)
        custom_entry.bind("<Return>", lambda e: self._send_custom())
        self.auto_chk_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cmd, text="Auto $..*CC", variable=self.auto_chk_var).grid(
            row=2, column=4, sticky="w", **pad)
        self.send_custom_btn = ttk.Button(cmd, text="Enviar",
                                          command=self._send_custom, state="disabled")
        self.send_custom_btn.grid(row=2, column=5, sticky="w", **pad)

        # --- Painel de posição --------------------------------------------
        fix = ttk.LabelFrame(self.root, text="Última posição (RMC/GGA)")
        fix.pack(fill="x", **pad)
        self.fix_var = tk.StringVar(value="Sem dados.")
        ttk.Label(fix, textvariable=self.fix_var, font=("Consolas", 9)).pack(
            anchor="w", padx=8, pady=4)

        # --- Abas: Log e Teste TTFF ----------------------------------------
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, **pad)
        logf = ttk.Frame(self.notebook)
        self.notebook.add(logf, text="Log")

        toolbar = ttk.Frame(logf)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Salvar log…", command=self._save_log).pack(
            side="left", padx=4, pady=4)
        ttk.Button(toolbar, text="Limpar log", command=self._clear_log).pack(
            side="left", padx=4, pady=4)
        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Auto-scroll",
                        variable=self.autoscroll_var).pack(side="left", padx=8)
        self.timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Timestamp",
                        variable=self.timestamp_var).pack(side="left", padx=8)
        self.hex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="HEX (bytes crus)",
                        variable=self.hex_var).pack(side="left", padx=8)
        self.only_resp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Só respostas ($PAIR/$PQTM)",
                        variable=self.only_resp_var).pack(side="left", padx=8)
        self.lines_var = tk.StringVar(value="0 linhas")
        ttk.Label(toolbar, textvariable=self.lines_var).pack(side="right", padx=8)
        self.rxbytes_var = tk.StringVar(value="RX: 0 bytes")
        ttk.Label(toolbar, textvariable=self.rxbytes_var).pack(side="right", padx=8)

        self.log = tk.Text(logf, wrap="none", height=12, state="disabled",
                           font=("Consolas", 9), background="#101418",
                           foreground="#d6dde4")
        self.log.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(logf, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

        self.log.tag_config("tx", foreground="#62d0ff")
        self.log.tag_config("rx", foreground="#b8e6b8")
        self.log.tag_config("error", foreground="#ff7b7b")
        self.log.tag_config("info", foreground="#e6c86e")
        self.log.tag_config("badchk", foreground="#ff7b7b")
        self.log.tag_config("ack", foreground="#ffd54f", font=("Consolas", 9, "bold"))

        self._line_count = 0

        self._build_test_tab()
        self._build_accuracy_tab()
        self._build_about_tab()

    # ----------------------------------------------------- aba de teste ----
    def _build_test_tab(self):
        pad = {"padx": 4, "pady": 4}
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Teste TTFF")

        # Botões de start
        ctrl = ttk.LabelFrame(tab, text="Iniciar teste de aquisição")
        ctrl.pack(fill="x", **pad)
        self.test_hint_var = tk.StringVar()
        ttk.Label(
            ctrl, foreground="#555", textvariable=self.test_hint_var,
            wraplength=560, justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", **pad)

        self.cold_btn = ttk.Button(ctrl, text="Cold start",
                                   command=lambda: self._start_ttff("cold"),
                                   state="disabled")
        self.cold_btn.grid(row=1, column=0, **pad)
        self.warm_btn = ttk.Button(ctrl, text="Warm start",
                                   command=lambda: self._start_ttff("warm"),
                                   state="disabled")
        self.warm_btn.grid(row=1, column=1, **pad)
        self.hot_btn = ttk.Button(ctrl, text="Hot start",
                                  command=lambda: self._start_ttff("hot"),
                                  state="disabled")
        self.hot_btn.grid(row=1, column=2, **pad)
        self.stop_test_btn = ttk.Button(ctrl, text="Parar",
                                        command=self._stop_ttff, state="disabled")
        self.stop_test_btn.grid(row=1, column=3, **pad)

        # Métricas em tempo real
        met = ttk.LabelFrame(tab, text="Métricas em tempo real")
        met.pack(fill="x", **pad)
        self.m_state = self._metric(met, 0, "Estado:", "ocioso")
        self.m_elapsed = self._metric(met, 1, "Tempo decorrido:", "—")
        self.m_ttff = self._metric(met, 2, "TTFF (1º fix):", "—")
        self.m_fixtype = self._metric(met, 3, "Tipo de fix:", "—")
        self.m_used = self._metric(met, 4, "Sat. usados:", "—")
        self.m_view = self._metric(met, 5, "Sat. em vista:", "—")
        self.m_hdop = self._metric(met, 6, "HDOP:", "—")
        self.m_pos = self._metric(met, 7, "Posição:", "—")

        # Tabela de resultados
        res = ttk.LabelFrame(tab, text="Resultados")
        res.pack(fill="both", expand=True, **pad)
        cols = ("n", "tipo", "ttff", "usados", "vista", "lat", "lon",
                "hdop", "fix", "hora")
        titles = ("#", "Tipo", "TTFF (s)", "Sat.usados", "Sat.vistos",
                  "Latitude", "Longitude", "HDOP", "Fix", "Hora")
        widths = (30, 55, 65, 75, 70, 95, 95, 55, 45, 80)
        self.res_tree = ttk.Treeview(res, columns=cols, show="headings", height=6)
        for c, t, w in zip(cols, titles, widths):
            self.res_tree.heading(c, text=t)
            self.res_tree.column(c, width=w, anchor="center")
        self.res_tree.pack(fill="both", expand=True, side="left")
        rscroll = ttk.Scrollbar(res, command=self.res_tree.yview)
        rscroll.pack(side="right", fill="y")
        self.res_tree.configure(yscrollcommand=rscroll.set)

        btns = ttk.Frame(tab)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="Exportar CSV…",
                   command=self._export_results).pack(side="left", padx=4)
        ttk.Button(btns, text="Limpar resultados",
                   command=self._clear_results).pack(side="left", padx=4)

    def _coord_decimals(self) -> int:
        """Casas decimais para exibir coordenadas (6 a 8)."""
        try:
            return max(6, min(8, int(self.coord_dec_var.get())))
        except (ValueError, TypeError):
            return 6

    def _fmt_coord(self, value):
        """Formata uma coordenada com as casas escolhidas (None -> None)."""
        if value is None:
            return None
        return f"{value:.{self._coord_decimals()}f}"

    def _metric(self, parent, row, label, initial):
        ttk.Label(parent, text=label, width=16).grid(
            row=row, column=0, sticky="w", padx=6, pady=2)
        var = tk.StringVar(value=initial)
        ttk.Label(parent, textvariable=var, font=("Consolas", 11, "bold")).grid(
            row=row, column=1, sticky="w", padx=6, pady=2)
        return var

    def _start_ttff(self, kind):
        if not self.serial.is_open:
            messagebox.showwarning(
                "Teste", "Conecte a porta (e ative o bypass, se aplicável) antes.")
            return
        frame = self.profile.start_frame(kind)      # bytes (UBX) ou None
        payload = self.profile.start_payload(kind)  # str (NMEA) ou None
        if frame is not None:                        # dispositivo binário (u-blox)
            try:
                self.serial.write_bytes(frame)
            except Exception as exc:
                self._append("error", f"Falha ao enviar: {exc}")
                return
            self._append("tx", f">> [UBX] {kind} start: {frame.hex(' ').upper()}")
        elif payload:                                # dispositivo NMEA ($PAIR)
            if not self._send_raw(core.build_sentence(payload, self._line_ending())):
                return
        else:
            messagebox.showinfo(
                "Teste",
                f"O dispositivo “{self.profile.name}” não define {kind} start.")
            return
        self.tracker.reset()
        self.test_active = True
        self.test_kind = kind
        self.test_t0 = time.monotonic()
        self.test_ttff = None
        self.test_fix_type = None
        self.m_state.set(f"medindo ({kind})")
        self.m_ttff.set("aguardando fix…")
        self.m_used.set("—")
        self.m_view.set("—")
        self.m_hdop.set("—")
        self.m_pos.set("—")
        self.stop_test_btn.configure(state="normal")
        cmd_desc = "UBX-CFG-RST" if frame is not None else payload
        self._append("info", f"Teste {kind.upper()} START iniciado ({cmd_desc}).")

    def _stop_ttff(self):
        if not self.test_active:
            return
        self.test_active = False
        self.stop_test_btn.configure(state="disabled")
        if self.test_ttff is None:
            self.m_state.set("parado (sem fix)")
            self._append("info", "Teste parado sem obter fix.")
        else:
            self.m_state.set("concluído")

    def _feed_test(self, sentence):
        if not self.test_active or sentence is None:
            return
        self.tracker.feed(sentence)
        # O LC76G emite um GSA por constelação; uma constelação sem satélites
        # contribuindo reporta NavMode=1 (sem fix). Mantém o MELHOR NavMode do
        # ciclo para não apagar um 2D/3D real com o GSA vazio de outra família.
        ft = core.parse_gsa_fix_type(sentence)
        if ft is not None and (self.test_fix_type is None or ft > self.test_fix_type):
            self.test_fix_type = ft
        if self.test_ttff is None and core.is_valid_fix(sentence):
            self.test_ttff = time.monotonic() - self.test_t0
            self._refresh_test_metrics()   # garante sat./posição atualizados
            self.m_ttff.set(f"{self.test_ttff:.1f} s")
            self.m_elapsed.set(f"{self.test_ttff:.1f} s")  # congela o tempo
            self.m_state.set("FIX OBTIDO ✓ (parado)")
            self._record_result()
            self._append("info",
                         f"FIX em {self.test_ttff:.1f} s "
                         f"({self.tracker.total_in_view} sat. vistos, "
                         f"{self.last_fix.satellites_used} usados).")
            # Para o teste: o cronômetro congela no valor do TTFF.
            self.test_active = False
            self.stop_test_btn.configure(state="disabled")
            return
        self._refresh_test_metrics()

    def _refresh_test_metrics(self):
        f = self.last_fix
        fixtype = {1: "sem fix", 2: "2D", 3: "3D"}.get(self.test_fix_type, "—")
        self.m_fixtype.set(fixtype)
        self.m_used.set(str(f.satellites_used) if f.satellites_used is not None else "—")
        per = self.tracker.per_constellation
        breakdown = " ".join(f"{k}:{v}" for k, v in sorted(per.items()))
        self.m_view.set(f"{self.tracker.total_in_view}  ({breakdown})" if per else "—")
        self.m_hdop.set(str(f.hdop) if f.hdop is not None else "—")
        if f.latitude is not None and f.longitude is not None:
            self.m_pos.set(
                f"{self._fmt_coord(f.latitude)}, {self._fmt_coord(f.longitude)}")

    def _record_result(self):
        f = self.last_fix
        fixtype = {1: "sem fix", 2: "2D", 3: "3D"}.get(self.test_fix_type, "—")
        n = len(self.test_results) + 1
        row = {
            "n": n,
            "tipo": self.test_kind,
            "ttff": f"{self.test_ttff:.1f}",
            "usados": f.satellites_used if f.satellites_used is not None else "",
            "vista": self.tracker.total_in_view,
            "lat": self._fmt_coord(f.latitude) if f.latitude is not None else "",
            "lon": self._fmt_coord(f.longitude) if f.longitude is not None else "",
            "hdop": f.hdop if f.hdop is not None else "",
            "fix": fixtype,
            "hora": datetime.now().strftime("%H:%M:%S"),
        }
        self._result_cols = ("n", "tipo", "ttff", "usados", "vista", "lat",
                             "lon", "hdop", "fix", "hora")
        self.test_results.append(row)
        self.res_tree.insert("", "end",
                             values=tuple(row[c] for c in self._result_cols))

    def _export_results(self):
        if not self.test_results:
            messagebox.showinfo("Exportar", "Nenhum resultado para exportar.")
            return
        default = datetime.now().strftime("ttff_lc76g_%Y%m%d_%H%M%S.csv")
        path = filedialog.asksaveasfilename(
            title="Exportar resultados", defaultextension=".csv",
            initialfile=default, filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        cols = ("n", "tipo", "ttff", "usados", "vista", "lat", "lon",
                "hdop", "fix", "hora")
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=cols)
                writer.writeheader()
                writer.writerows(self.test_results)
        except OSError as exc:
            messagebox.showerror("Exportar", f"Falha ao salvar:\n{exc}")
            return
        self._append("info", f"Resultados exportados para {path}")

    def _clear_results(self):
        self.test_results.clear()
        for item in self.res_tree.get_children():
            self.res_tree.delete(item)

    # ------------------------------------------------- aba de precisão ----
    def _build_accuracy_tab(self):
        pad = {"padx": 4, "pady": 4}
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Teste de Precisão")

        # Parâmetros do ensaio
        cfg = ttk.LabelFrame(tab, text="Parâmetros")
        cfg.pack(fill="x", **pad)
        ttk.Label(cfg, text="Amostras por ponto:").grid(
            row=0, column=0, sticky="w", **pad)
        self.acc_n_var = tk.StringVar(value="100")
        ttk.Spinbox(cfg, from_=1, to=10000, width=7,
                    textvariable=self.acc_n_var).grid(row=0, column=1, **pad)
        ttk.Label(cfg, text="Casas decimais da moda:").grid(
            row=0, column=2, sticky="w", **pad)
        self.acc_dec_var = tk.StringVar(value="5")
        ttk.Spinbox(cfg, from_=0, to=8, width=5,
                    textvariable=self.acc_dec_var).grid(row=0, column=3, **pad)
        ttk.Label(cfg, foreground="#555",
                  text="(5 casas ≈ 1,1 m por grupo da moda)").grid(
            row=0, column=4, sticky="w", **pad)
        ttk.Label(cfg, text="Medir distância:").grid(
            row=1, column=0, sticky="w", **pad)
        self.acc_mode_var = tk.StringVar(value="Da origem")
        self.acc_mode_combo = ttk.Combobox(
            cfg, textvariable=self.acc_mode_var, width=24, state="readonly",
            values=["Da origem", "Por trecho (ponto anterior)"])
        self.acc_mode_combo.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        self.acc_mode_combo.bind("<<ComboboxSelected>>", self._on_acc_mode_change)

        # Posição inicial (origem)
        ref = ttk.LabelFrame(tab, text="1) Posição inicial (origem)")
        ref.pack(fill="x", **pad)
        self.acc_ref_btn = ttk.Button(
            ref, text="Marcar posição inicial",
            command=lambda: self._acc_collect("ref"), state="disabled")
        self.acc_ref_btn.grid(row=0, column=0, **pad)
        self.acc_ref_var = tk.StringVar(value="origem não marcada")
        ttk.Label(ref, textvariable=self.acc_ref_var,
                  font=("Consolas", 9)).grid(row=0, column=1, sticky="w", **pad)

        # Adicionar ponto
        addp = ttk.LabelFrame(tab, text="2) Adicionar ponto medido")
        addp.pack(fill="x", **pad)
        self.acc_dist_label_var = tk.StringVar(value="Distância da origem (m):")
        ttk.Label(addp, textvariable=self.acc_dist_label_var).grid(
            row=0, column=0, sticky="w", **pad)
        self.acc_dist_var = tk.StringVar()
        dist_entry = ttk.Entry(addp, textvariable=self.acc_dist_var, width=12)
        dist_entry.grid(row=0, column=1, sticky="w", **pad)
        dist_entry.bind("<Return>", lambda e: self._acc_collect("point"))
        self.acc_point_btn = ttk.Button(
            addp, text="Medir ponto", command=lambda: self._acc_collect("point"),
            state="disabled")
        self.acc_point_btn.grid(row=0, column=2, **pad)
        ttk.Label(addp, foreground="#555",
                  text="(use 0 para medir parado — repetibilidade/deriva)").grid(
            row=1, column=0, columnspan=3, sticky="w", **pad)

        # Progresso da coleta
        prog = ttk.Frame(tab)
        prog.pack(fill="x", **pad)
        self.acc_status_var = tk.StringVar(value="Conecte e ative o bypass; "
                                           "depois marque a posição inicial.")
        ttk.Label(prog, textvariable=self.acc_status_var,
                  foreground="#1565c0").pack(anchor="w", padx=6)
        self.acc_weather_var = tk.StringVar(value="Clima: —")
        ttk.Label(prog, textvariable=self.acc_weather_var,
                  foreground="#555").pack(anchor="w", padx=6)

        # Tabela de pontos
        res = ttk.LabelFrame(tab, text="Pontos medidos")
        res.pack(fill="both", expand=True, **pad)
        cols = ("n", "real", "medida", "erro", "erro_pct", "lat", "lon",
                "hdop", "sats", "vistos", "hora")
        titles = ("#", "Informado (m)", "Medido (m)", "Erro (m)",
                  "Erro (%)", "Latitude", "Longitude", "HDOP", "Sat.usados",
                  "Sat.vistos", "Hora")
        widths = (28, 85, 90, 65, 60, 92, 92, 50, 65, 65, 65)
        self.acc_tree = ttk.Treeview(res, columns=cols, show="headings",
                                     height=6)
        for c, t, w in zip(cols, titles, widths):
            self.acc_tree.heading(c, text=t)
            self.acc_tree.column(c, width=w, anchor="center")
        self.acc_tree.pack(fill="both", expand=True, side="left")
        ascroll = ttk.Scrollbar(res, command=self.acc_tree.yview)
        ascroll.pack(side="right", fill="y")
        self.acc_tree.configure(yscrollcommand=ascroll.set)

        # Ações finais
        btns = ttk.Frame(tab)
        btns.pack(fill="x", **pad)
        self.acc_finish_btn = ttk.Button(
            btns, text="Finalizar ensaio", command=self._finalize_accuracy,
            state="disabled")
        self.acc_finish_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Emitir relatório…",
                   command=self._emit_report).pack(side="left", padx=4)
        ttk.Button(btns, text="Exportar CSV…",
                   command=self._export_accuracy).pack(side="left", padx=4)
        ttk.Button(btns, text="Reiniciar ensaio",
                   command=self._reset_accuracy).pack(side="left", padx=4)

    # ----------------------------------------------------- aba "Sobre" ----
    def _build_about_tab(self):
        pad = {"padx": 8, "pady": 4}
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sobre")
        inner = ttk.Frame(tab)
        inner.place(relx=0.5, rely=0.42, anchor="center")

        # Ícone do app (satélite), se disponível.
        try:
            png = os.path.join(os.path.dirname(__file__), "assets",
                               "gnss_test.png")
            if os.path.exists(png):
                self._about_img = tk.PhotoImage(file=png).subsample(2, 2)
                ttk.Label(inner, image=self._about_img).pack(pady=(0, 6))
        except Exception:
            pass

        ttk.Label(inner, text="GNSS Test", font=("Segoe UI", 20, "bold"),
                  foreground="#1f4e79").pack()
        ttk.Label(inner, text=f"Versão {APP_VERSION}",
                  foreground="#555").pack(pady=(0, 2))
        ttk.Label(inner, justify="center", wraplength=580,
                  text="Ferramenta de teste GNSS — aquisição (TTFF), ensaio de "
                       "precisão e suporte multi-dispositivo (Quectel, u-blox, "
                       "CASIC).").pack(pady=6)

        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(inner, text="Desenvolvido por", foreground="#555").pack()
        ttk.Label(inner, text=CREATOR,
                  font=("Segoe UI", 13, "bold")).pack(pady=(0, 6))

        # Bloco GitHub
        ttk.Label(inner, text="GitHub", foreground="#555").pack()
        self._about_links = []
        for label, url in (("Perfil", GITHUB_PROFILE), ("Repositório", GITHUB_REPO)):
            if not url:
                continue
            lk = ttk.Label(inner, text=f"{label}: {url}", foreground="#1565c0",
                           cursor="hand2", font=("Segoe UI", 10, "underline"))
            lk.pack(pady=1)
            lk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            self._about_links.append(lk)

        ttk.Label(tab, text="© Omnilink", foreground="#999").place(
            relx=0.5, rely=0.97, anchor="s")

    def _acc_mode(self) -> str:
        """Modo de medição: ``"origem"`` (padrão) ou ``"trecho"``."""
        return "trecho" if self.acc_mode_var.get().startswith("Por trecho") \
            else "origem"

    def _on_acc_mode_change(self, _event=None):
        if self._acc_mode() == "trecho":
            self.acc_dist_label_var.set("Andou desde o ponto anterior (m):")
        else:
            self.acc_dist_label_var.set("Distância da origem (m):")

    def _acc_sample_count(self) -> int:
        try:
            return max(1, int(self.acc_n_var.get()))
        except (ValueError, TypeError):
            return 100

    def _acc_decimals(self) -> int:
        try:
            return max(0, min(8, int(self.acc_dec_var.get())))
        except (ValueError, TypeError):
            return 5

    def _acc_set_buttons(self):
        """Habilita/desabilita os controles conforme conexão e estado."""
        connected = self.serial.is_open
        busy = self.acc_collecting
        ref_ok = self.acc_reference is not None
        self.acc_ref_btn.configure(
            state="normal" if (connected and not busy) else "disabled")
        self.acc_point_btn.configure(
            state="normal" if (connected and ref_ok and not busy) else "disabled")
        self.acc_finish_btn.configure(
            state="normal" if (self.acc_points and not busy) else "disabled")
        # Trava o modo de medição depois que o ensaio começa (evita misturar
        # "origem" e "trecho" nos pontos); liberado de novo ao reiniciar.
        lock_mode = busy or bool(self.acc_points)
        self.acc_mode_combo.configure(
            state="disabled" if lock_mode else "readonly")

    def _acc_collect(self, target: str):
        """Inicia a coleta de N amostras para a origem (``ref``) ou um ponto."""
        if not self.serial.is_open:
            messagebox.showwarning("Precisão", "Conecte e ative o bypass antes.")
            return
        if self.acc_collecting:
            return
        if target == "point":
            if self.acc_reference is None:
                messagebox.showwarning("Precisão",
                                       "Marque a posição inicial primeiro.")
                return
            try:
                self.acc_pending_known = float(
                    self.acc_dist_var.get().replace(",", "."))
            except ValueError:
                messagebox.showwarning(
                    "Precisão", "Informe a distância andada (em metros).")
                return
            if self.acc_pending_known < 0:
                messagebox.showwarning("Precisão",
                                       "A distância deve ser ≥ 0.")
                return
        # Inicia coleta.
        self.acc_collecting = True
        self.acc_target = target
        self.acc_samples = []
        self.acc_hdops = []
        self.acc_sats = []
        self.acc_last_utc = None
        self.acc_tracker.reset()
        self._acc_set_buttons()
        alvo = "origem" if target == "ref" else f"ponto ({self.acc_pending_known:g} m)"
        self.acc_status_var.set(
            f"Coletando {alvo}: 0/{self._acc_sample_count()} amostras…")

    def _feed_accuracy(self, sentence):
        if not self.acc_collecting or sentence is None:
            return
        # Conta satélites em vista (GSV) durante toda a coleta, inclusive em
        # sentenças que não são fix.
        self.acc_tracker.feed(sentence)
        if not core.is_valid_fix(sentence):
            return
        f = self.last_fix
        if f.latitude is None or f.longitude is None:
            return
        # Uma amostra por época (dedupe por UTC) para não contar RMC+GGA juntos.
        utc = f.utc
        if utc is not None and utc == self.acc_last_utc:
            return
        self.acc_last_utc = utc
        self.acc_samples.append((f.latitude, f.longitude))
        if f.hdop is not None:
            self.acc_hdops.append(f.hdop)
        if f.satellites_used is not None:
            self.acc_sats.append(f.satellites_used)
        n_target = self._acc_sample_count()
        n = len(self.acc_samples)
        alvo = "origem" if self.acc_target == "ref" else \
            f"ponto ({self.acc_pending_known:g} m)"
        self.acc_status_var.set(f"Coletando {alvo}: {n}/{n_target} amostras…")
        if n >= n_target:
            self._acc_finish_collection()

    def _acc_finish_collection(self):
        self.acc_collecting = False
        decimals = self._acc_decimals()
        pos = accuracy.mode_position(self.acc_samples, decimals)
        n = len(self.acc_samples)
        hdop = (sum(self.acc_hdops) / len(self.acc_hdops)
                if self.acc_hdops else None)
        sats = (round(sum(self.acc_sats) / len(self.acc_sats))
                if self.acc_sats else None)
        if pos is None:
            self.acc_status_var.set("Falha: nenhuma amostra válida coletada.")
            self._acc_set_buttons()
            return
        lat, lon = pos
        if self.acc_target == "ref":
            self.acc_reference = (lat, lon)
            self.acc_last_pos = (lat, lon)   # base para o modo "por trecho"
            self.acc_ref_var.set(
                f"origem: {self._fmt_coord(lat)}, {self._fmt_coord(lon)}  "
                f"(moda de {n} amostras)")
            self.acc_status_var.set(
                "Origem marcada. Informe a distância e meça um ponto.")
            self._append("info",
                         f"Precisão: origem = {self._fmt_coord(lat)}, "
                         f"{self._fmt_coord(lon)} "
                         f"({n} amostras).")
        else:
            # Base da medição conforme o modo selecionado:
            #  • "origem": distância sempre contra a origem fixa (não acumula);
            #  • "trecho": distância contra o ponto anterior.
            if self._acc_mode() == "trecho":
                base_lat, base_lon = self.acc_last_pos
            else:
                base_lat, base_lon = self.acc_reference
            measured = accuracy.haversine_m(base_lat, base_lon, lat, lon)
            idx = len(self.acc_points) + 1
            time_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            in_view = self.acc_tracker.total_in_view or None
            breakdown = " ".join(
                f"{k}:{v}" for k, v in sorted(
                    self.acc_tracker.per_constellation.items()))
            point = accuracy.AccuracyPoint(
                index=idx, known_distance=self.acc_pending_known,
                lat=lat, lon=lon, measured_distance=measured,
                n_samples=n, hdop=hdop, sats=sats, sats_in_view=in_view,
                view_breakdown=breakdown,
                time_local=time_local, gnss_utc=self.last_fix.utc,
                samples=list(self.acc_samples),
                base_lat=base_lat, base_lon=base_lon)
            self.acc_points.append(point)
            self.acc_last_pos = (lat, lon)   # avança a base para o próximo trecho
            pct = point.error_pct
            self.acc_tree.insert("", "end", values=(
                idx, f"{point.known_distance:.2f}", f"{measured:.2f}",
                f"{point.error:+.2f}",
                f"{pct:+.1f}" if pct is not None else "—",
                self._fmt_coord(lat), self._fmt_coord(lon),
                f"{hdop:.2f}" if hdop is not None else "—",
                sats if sats is not None else "—",
                in_view if in_view is not None else "—",
                time_local.split(" ")[1]))
            self.acc_status_var.set(
                f"Ponto {idx} registrado: medido {measured:.2f} m "
                f"(erro {point.error:+.2f} m). Adicione outro ou finalize.")
            self._append("info",
                         f"Precisão: ponto {idx} real={point.known_distance:g} m "
                         f"medido={measured:.2f} m erro={point.error:+.2f} m.")
            self.acc_dist_var.set("")
        self._acc_set_buttons()

    def _finalize_accuracy(self):
        if not self.acc_points:
            messagebox.showinfo("Precisão", "Nenhum ponto medido ainda.")
            return
        # Busca os dados meteorológicos da origem em segundo plano (não trava a
        # interface); o resultado chega via fila de eventos ("weather").
        if self.acc_reference is not None:
            self.acc_weather_var.set("Clima: buscando dados meteorológicos…")
            lat, lon = self.acc_reference
            threading.Thread(target=self._fetch_weather_worker,
                             args=(lat, lon), daemon=True).start()
        stats = accuracy.error_stats(self.acc_points)
        self._show_accuracy_report(stats)

    def _fetch_weather_worker(self, lat, lon):
        wd = weather.fetch_weather(lat, lon)
        self._events.put(("weather", wd))

    def _show_accuracy_report(self, stats: dict):
        """Mostra resumo estatístico + histograma e gráfico de erro percentual."""
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception as exc:  # matplotlib ausente
            messagebox.showerror(
                "Precisão", f"matplotlib indisponível para os gráficos:\n{exc}")
            return

        win = tk.Toplevel(self.root)
        win.title("Resultado do ensaio de precisão")
        win.geometry("860x640")

        # Resumo textual
        pct = stats.get("mean_abs_error_pct")
        pct_txt = f"{pct:.1f}%" if pct is not None else "—"
        resumo = (
            f"Pontos: {stats['n']}   "
            f"Erro médio: {stats['mean_error']:+.2f} m   "
            f"MAE: {stats['mean_abs_error']:.2f} m   "
            f"RMS: {stats['rms_error']:.2f} m   "
            f"Desvio: {stats['std_error']:.2f} m\n"
            f"Erro absoluto mín/máx: {stats['min_abs_error']:.2f} / "
            f"{stats['max_abs_error']:.2f} m   "
            f"Mediana: {stats['median_error']:+.2f} m   "
            f"Erro % abs. médio: {pct_txt}")
        ttk.Label(win, text=resumo, font=("Consolas", 9), justify="left",
                  foreground="#1b5e20").pack(anchor="w", padx=10, pady=8)
        ttk.Label(win, textvariable=self.acc_weather_var, font=("Consolas", 9),
                  foreground="#555").pack(anchor="w", padx=10)

        errors = [p.error for p in self.acc_points]
        pcts = [(p.index, p.error_pct) for p in self.acc_points
                if p.error_pct is not None]
        # Histograma: erro de CADA amostra de todos os pontos (rico já com
        # poucos pontos). Cai para o erro por ponto se não houver amostras.
        sample_errs = [e for p in self.acc_points
                       for e in accuracy.sample_errors_m(p)]
        hist_data = sample_errs if sample_errs else errors

        fig = Figure(figsize=(8.6, 6.6), dpi=100)
        ax1 = fig.add_subplot(2, 2, 1)
        hist_mean = sum(hist_data) / len(hist_data) if hist_data else 0.0
        bins = (min(40, max(10, int(len(hist_data) ** 0.5)))
                if len(hist_data) > 20 else max(3, len(hist_data)))
        ax1.hist(hist_data, bins=bins, color="#1565c0", edgecolor="white")
        ax1.axvline(hist_mean, color="#c62828", linestyle="--",
                    linewidth=1.2, label=f"média {hist_mean:+.2f} m")
        ax1.set_title(f"Histograma do erro ({len(hist_data)} amostras)")
        ax1.set_xlabel("Erro (m)")
        ax1.set_ylabel("Frequência")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)
        # Segundo gráfico: erro percentual por ponto, ou — quando todas as
        # distâncias são 0 (medição parado) — erro absoluto (m) por ponto.
        ax2 = fig.add_subplot(2, 2, 2)
        if pcts:
            idxs = [i for i, _ in pcts]
            ys = [v for _, v in pcts]
            ax2.bar(range(len(ys)), ys, color="#2e7d32", edgecolor="white")
            ax2.set_xticks(range(len(ys)))
            ax2.set_xticklabels([f"P{i}" for i in idxs], fontsize=7)
            ax2.axhline(0, color="#555", linewidth=0.8)
            ax2.set_title("Erro percentual por ponto")
            ax2.set_ylabel("Erro (%)")
        else:
            abserr = [p.abs_error for p in self.acc_points]
            ax2.bar(range(len(abserr)), abserr, color="#2e7d32",
                    edgecolor="white")
            ax2.set_xticks(range(len(abserr)))
            ax2.set_xticklabels([f"P{p.index}" for p in self.acc_points],
                                fontsize=7)
            ax2.set_title("Erro absoluto por ponto (parado)")
            ax2.set_ylabel("Erro (m)")
        ax2.set_xlabel("Ponto")
        ax2.grid(True, alpha=0.3)
        # Terceiro gráfico (largura total): diagrama de quartis (boxplot) da
        # dispersão das amostras de CADA ponto — mediana, IQR e outliers.
        ax3 = fig.add_subplot(2, 1, 2)
        devs = [accuracy.sample_deviations_m(p) for p in self.acc_points]
        data = [d for d in devs if d]
        labels = [f"P{p.index}" for p, d in zip(self.acc_points, devs) if d]
        if data:
            ax3.boxplot(data, showmeans=True)
            ax3.set_xticklabels(labels, fontsize=7)
            ax3.set_title("Dispersão das amostras por ponto (quartis)")
            ax3.set_xlabel("Ponto")
            ax3.set_ylabel("Desvio da posição do ponto (m)")
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, "sem amostras brutas para o boxplot",
                     ha="center", va="center")
            ax3.set_axis_off()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=4)

        def _save_png():
            default = datetime.now().strftime("precisao_lc76g_%Y%m%d_%H%M%S.png")
            path = filedialog.asksaveasfilename(
                title="Salvar gráficos", defaultextension=".png",
                initialfile=default,
                filetypes=[("PNG", "*.png"), ("Todos", "*.*")])
            if path:
                fig.savefig(path, dpi=150, bbox_inches="tight")
                self._append("info", f"Gráficos salvos em {path}")

        ttk.Button(win, text="Salvar gráficos (PNG)…",
                   command=_save_png).pack(pady=6)

    def _ask_report_meta(self):
        """Caixa de diálogo modal para título e responsável. Retorna dict ou None."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Emitir relatório")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        result = {}
        pad = {"padx": 8, "pady": 6}
        ttk.Label(dlg, text="Título da medição:").grid(
            row=0, column=0, sticky="w", **pad)
        title_var = tk.StringVar(
            value=f"Ensaio de precisão — {self.profile.name}")
        e1 = ttk.Entry(dlg, textvariable=title_var, width=44)
        e1.grid(row=0, column=1, **pad)
        ttk.Label(dlg, text="Responsável:").grid(
            row=1, column=0, sticky="w", **pad)
        resp_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=resp_var, width=44).grid(
            row=1, column=1, **pad)

        def _ok():
            result["title"] = title_var.get().strip()
            result["responsible"] = resp_var.get().strip()
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        bar = ttk.Frame(dlg)
        bar.grid(row=2, column=0, columnspan=2, pady=(4, 8))
        ttk.Button(bar, text="Gerar", command=_ok).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancelar", command=_cancel).pack(side="left", padx=6)
        e1.focus_set()
        dlg.bind("<Return>", lambda e: _ok())
        dlg.bind("<Escape>", lambda e: _cancel())
        dlg.grab_set()
        self.root.wait_window(dlg)
        return result if result else None

    def _emit_report(self):
        if not self.acc_points:
            messagebox.showinfo("Relatório", "Nenhum ponto medido ainda.")
            return
        try:
            from . import report
        except ImportError as exc:
            messagebox.showerror(
                "Relatório",
                "Para emitir o relatório em Word é preciso instalar o "
                f"python-docx:\n\npip install python-docx\n\n({exc})")
            return
        meta = self._ask_report_meta()
        if meta is None:
            return
        default = datetime.now().strftime("relatorio_precisao_%Y%m%d_%H%M%S.docx")
        path = filedialog.asksaveasfilename(
            title="Salvar relatório", defaultextension=".docx",
            initialfile=default,
            filetypes=[("Word", "*.docx"), ("Todos", "*.*")])
        if not path:
            return
        stats = accuracy.error_stats(self.acc_points)
        try:
            report.build_precision_report(
                path, title=meta["title"], responsible=meta["responsible"],
                device=self.profile.name, mode=self._acc_mode(),
                reference=self.acc_reference, points=self.acc_points,
                stats=stats, weather=self.acc_weather,
                sample_count=self._acc_sample_count(),
                decimals=self._acc_decimals(), generated_at=datetime.now(),
                coord_decimals=self._coord_decimals())
        except Exception as exc:
            messagebox.showerror("Relatório", f"Falha ao gerar:\n{exc}")
            return
        self._append("info", f"Relatório emitido em {path}")
        if messagebox.askyesno("Relatório",
                               "Relatório gerado com sucesso.\nDeseja abri-lo agora?"):
            try:
                os.startfile(path)  # Windows
            except Exception:
                pass

    def _export_accuracy(self):
        if not self.acc_points:
            messagebox.showinfo("Precisão", "Nenhum ponto para exportar.")
            return
        default = datetime.now().strftime("precisao_lc76g_%Y%m%d_%H%M%S.csv")
        path = filedialog.asksaveasfilename(
            title="Exportar ensaio de precisão", defaultextension=".csv",
            initialfile=default, filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        cols = ("n", "dist_real_m", "dist_medida_m", "erro_m", "erro_pct",
                "lat", "lon", "hdop", "sats_usados", "sats_vistos",
                "vistos_por_constelacao", "amostras", "hora_local", "gnss_utc")
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["# modo_medicao",
                                 "trecho" if self._acc_mode() == "trecho"
                                 else "origem"])
                if self.acc_reference:
                    writer.writerow(
                        ["# origem_lat", self._fmt_coord(self.acc_reference[0]),
                         "origem_lon", self._fmt_coord(self.acc_reference[1])])
                # Metadados meteorológicos do ensaio (uma consulta por ensaio).
                wd = self.acc_weather
                if wd is not None:
                    writer.writerow([
                        "# clima", f"temp_C={_fmt(wd.temperature_c)}",
                        f"umidade_pct={_fmt(wd.humidity_pct)}",
                        f"pressao_sup_hPa={_fmt(wd.surface_pressure_hpa)}",
                        f"pressao_msl_hPa={_fmt(wd.pressure_msl_hpa)}",
                        f"nuvens_pct={_fmt(wd.cloud_cover_pct)}",
                        f"precip_mm={_fmt(wd.precipitation_mm)}",
                        f"vento_kmh={_fmt(wd.wind_speed_kmh)}",
                        f"elevacao_m={_fmt(wd.elevation_m)}",
                        f"kp={_fmt(wd.kp_index)}",
                        f"obs_utc={wd.observed_utc or ''}"])
                writer.writerow(cols)
                for p in self.acc_points:
                    pct = p.error_pct
                    writer.writerow([
                        p.index, f"{p.known_distance:.2f}",
                        f"{p.measured_distance:.2f}", f"{p.error:.2f}",
                        f"{pct:.2f}" if pct is not None else "",
                        self._fmt_coord(p.lat), self._fmt_coord(p.lon),
                        f"{p.hdop:.2f}" if p.hdop is not None else "",
                        p.sats if p.sats is not None else "",
                        p.sats_in_view if p.sats_in_view is not None else "",
                        p.view_breakdown, p.n_samples,
                        p.time_local or "", p.gnss_utc or ""])
        except OSError as exc:
            messagebox.showerror("Precisão", f"Falha ao salvar:\n{exc}")
            return
        self._append("info", f"Ensaio de precisão exportado para {path}")

    def _reset_accuracy(self):
        if self.acc_collecting:
            return
        self.acc_reference = None
        self.acc_last_pos = None
        self.acc_points = []
        self.acc_pending_known = 0.0
        self.acc_weather = None
        self.acc_ref_var.set("origem não marcada")
        self.acc_weather_var.set("Clima: —")
        self.acc_status_var.set("Ensaio reiniciado. Marque a posição inicial.")
        for item in self.acc_tree.get_children():
            self.acc_tree.delete(item)
        self._acc_set_buttons()

    # -------------------------------------------------------------- ações --
    def _refresh_ports(self):
        ports = core.list_serial_ports()
        values = [f"{dev}  —  {desc}" for dev, desc in ports]
        self._port_map = {f"{dev}  —  {desc}": dev for dev, desc in ports}
        self.port_combo["values"] = values
        if values and not self.port_var.get():
            self.port_combo.current(0)
        elif not values:
            self.port_var.set("")

    def _selected_port(self):
        return self._port_map.get(self.port_var.get())

    def _toggle_connection(self):
        if self.serial.is_open:
            self.serial.close()
            self._set_connected(False)
            self._append("info", "Desconectado.")
            return
        port = self._selected_port()
        if not port:
            messagebox.showwarning("Conexão", "Selecione uma porta serial.")
            return
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            messagebox.showwarning("Conexão", "Baud rate inválido.")
            return
        try:
            self.serial.open(port, baud)
        except Exception as exc:
            messagebox.showerror("Conexão", f"Falha ao abrir {port}:\n{exc}")
            return
        self._rx_bytes = 0
        self.rxbytes_var.set("RX: 0 bytes")
        self._set_connected(True)
        self._append("info", f"Conectado a {port} @ {baud} bps.")
        self._append("info", "Dica: clique em BYPASS #gps para o microcontrolador "
                             "repassar os dados do GPS.")

    def _set_connected(self, connected: bool):
        if connected:
            self.status_var.set("● Conectado")
            self.status_lbl.configure(foreground="#1b7e1b")
            self.connect_btn.configure(text="Desconectar")
            state = "normal"
        else:
            self.status_var.set("● Desconectado")
            self.status_lbl.configure(foreground="#b00020")
            self.connect_btn.configure(text="Conectar")
            state = "disabled"
        self.send_catalog_btn.configure(state=state)
        self.send_custom_btn.configure(state=state)
        # Bypass e botões de start respeitam o perfil do dispositivo.
        self._refresh_device_controls()
        if not connected and self.test_active:
            self._stop_ttff()
        # Ensaio de precisão: interrompe coleta ao desconectar e atualiza botões.
        if not connected and self.acc_collecting:
            self.acc_collecting = False
            self.acc_status_var.set("Desconectado durante a coleta — refaça o ponto.")
        self._acc_set_buttons()

    def _on_device_change(self, _event=None):
        """Troca o perfil ativo a partir da caixa de seleção."""
        prof = self._profiles_by_name.get(self.device_var.get())
        if prof is None or prof is self.profile:
            return
        if self.test_active:
            self._stop_ttff()
        self.profile = prof
        self._apply_profile()
        self._append("info", f"Dispositivo selecionado: {prof.name}.")

    def _apply_profile(self):
        """Reconfigura a interface com os parâmetros do perfil ativo."""
        p = self.profile
        self.device_desc_var.set(p.description)
        # Baud rates do dispositivo.
        self.baud_combo.configure(values=[str(b) for b in p.baud_rates])
        self.baud_var.set(str(p.default_baud))
        # Comando de bypass padrão (vazio se o dispositivo não usa bypass).
        self.bypass_cmd_var.set(p.bypass_command or "")
        # Catálogo de comandos rápidos.
        self.catalog_combo.configure(values=[c.label for c in p.command_catalog])
        self.catalog_var.set("")
        # Habilita/desabilita e rotula os controles conforme o perfil.
        self._refresh_device_controls()

    def _refresh_device_controls(self):
        """Estado/rótulo do bypass e dos botões de start (perfil + conexão)."""
        p = self.profile
        connected = self.serial.is_open
        # Bypass: só faz sentido se o dispositivo o define.
        if p.bypass_command:
            self.bypass_btn.configure(
                state="normal" if connected else "disabled")
        else:
            self.bypass_btn.configure(state="disabled")
        # Dica do teste (menciona o bypass do dispositivo, se houver).
        if p.bypass_command:
            hint = f"Requer bypass ativo ({p.bypass_command}). "
        else:
            hint = ""
        self.test_hint_var.set(
            hint + "O start é enviado ao módulo e o cronômetro mede o tempo "
            "até o 1º fix válido.")
        # Botões de cold/warm/hot: rótulo com payload e estado conforme suporte.
        labels = {"cold": "Cold start", "warm": "Warm start", "hot": "Hot start"}
        buttons = {"cold": self.cold_btn, "warm": self.warm_btn,
                   "hot": self.hot_btn}
        for kind, btn in buttons.items():
            payload = p.start_payload(kind)        # NMEA ($PAIR…)
            if payload:
                tag = payload
            elif p.start_frame(kind) is not None:  # binário (UBX)
                tag = "UBX"
            else:
                tag = None
            if tag:
                btn.configure(text=f"{labels[kind]} ({tag})",
                              state="normal" if connected else "disabled")
            else:
                btn.configure(text=f"{labels[kind]} (n/d)", state="disabled")

    def _line_ending(self) -> str:
        return core.LINE_ENDINGS.get(self.ending_var.get(), "\r\n")

    def _send_raw(self, text: str):
        try:
            self.serial.write_line(text)
        except Exception as exc:
            self._append("error", f"Falha ao enviar: {exc}")
            return False
        display = text.replace("\r", "\\r").replace("\n", "\\n")
        self._append("tx", f">> {display}")
        return True

    def _send_bypass(self):
        cmd = self.bypass_cmd_var.get() + self._line_ending()
        self._send_raw(cmd)

    def _on_catalog_select(self, _event=None):
        label = self.catalog_var.get()
        for c in self.profile.command_catalog:
            if c.label == label:
                self.custom_var.set(c.payload)
                break

    def _send_catalog(self):
        label = self.catalog_var.get()
        for c in self.profile.command_catalog:
            if c.label == label:
                self._send_raw(core.build_sentence(c.payload, self._line_ending()))
                return
        messagebox.showinfo("Comando", "Selecione um comando rápido.")

    def _send_custom(self):
        text = self.custom_var.get().strip()
        if not text:
            return
        if self.auto_chk_var.get():
            payload = text.lstrip("$").split("*")[0]
            self._send_raw(core.build_sentence(payload, self._line_ending()))
        else:
            self._send_raw(text + self._line_ending())

    # --------------------------------------------------------------- log ---
    def _append(self, tag: str, text: str):
        prefix = ""
        if self.timestamp_var.get():
            prefix = datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "
        self.log.configure(state="normal")
        self.log.insert("end", prefix + text + "\n", tag)
        self.log.configure(state="disabled")
        if self.autoscroll_var.get():
            self.log.see("end")
        self._line_count += 1
        self.lines_var.set(f"{self._line_count} linhas")

    def _handle_rx(self, line: str):
        sentence = core.parse_nmea(line)
        # Respostas a comandos (proprietárias $PAIR/$PQTM) são destacadas; o
        # NMEA padrão (GGA/RMC/GSV...) é o fluxo contínuo de posição.
        is_response = bool(sentence and sentence.is_proprietary)
        tag = "rx"
        if sentence and sentence.checksum_ok is False:
            tag = "badchk"
        elif is_response:
            tag = "ack"
        # No modo HEX, os bytes crus já são exibidos; evita duplicar a linha.
        if not self.hex_var.get():
            # Filtro "só respostas": oculta o NMEA padrão para ver os ACKs.
            if not (self.only_resp_var.get() and not is_response):
                self._append(tag, line)
        if sentence:
            self._update_fix(sentence)
            self._feed_test(sentence)
            self._feed_accuracy(sentence)

    def _update_fix(self, sentence: core.NmeaSentence):
        fix = None
        if sentence.sentence_type.endswith("RMC"):
            fix = core.parse_rmc(sentence)
        elif sentence.sentence_type.endswith("GGA"):
            fix = core.parse_gga(sentence)
        if not fix:
            return
        # mescla campos não-nulos no estado acumulado
        for attr in vars(fix):
            val = getattr(fix, attr)
            if val is not None and not (attr == "valid" and val is False):
                setattr(self.last_fix, attr, val)
        f = self.last_fix
        lat = self._fmt_coord(f.latitude) or "—"
        lon = self._fmt_coord(f.longitude) or "—"
        self.fix_var.set(
            f"Fix: {'VÁLIDO' if f.valid else 'inválido'}   "
            f"Lat: {lat}   Lon: {lon}   "
            f"Sat: {f.satellites_used if f.satellites_used is not None else '—'}   "
            f"HDOP: {f.hdop if f.hdop is not None else '—'}   "
            f"Alt: {f.altitude if f.altitude is not None else '—'} m   "
            f"UTC: {f.utc or '—'}"
        )

    def _save_log(self):
        content = self.log.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showinfo("Salvar log", "O log está vazio.")
            return
        default = datetime.now().strftime("log_lc76g_%Y%m%d_%H%M%S.txt")
        path = filedialog.asksaveasfilename(
            title="Salvar log", defaultextension=".txt", initialfile=default,
            filetypes=[("Texto", "*.txt"), ("Log", "*.log"), ("Todos", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            messagebox.showerror("Salvar log", f"Falha ao salvar:\n{exc}")
            return
        self._append("info", f"Log salvo em {path}")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._line_count = 0
        self.lines_var.set("0 linhas")

    # ----------------------------------------------------------- eventos ---
    def _poll_events(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "rx":
                    self._handle_rx(payload)
                elif kind == "bytes":
                    self._rx_bytes += len(payload)
                    self.rxbytes_var.set(f"RX: {self._rx_bytes} bytes")
                    if self.hex_var.get():
                        hexstr = " ".join(f"{b:02X}" for b in payload)
                        self._append("rx", "HEX " + hexstr)
                elif kind == "error":
                    self._append("error", payload)
                    self.serial.close()
                    self._set_connected(False)
                elif kind == "weather":
                    self.acc_weather = payload
                    self.acc_weather_var.set(
                        f"Clima: {weather.format_summary(payload)}")
                    self._append("info",
                                 f"Clima do ensaio: "
                                 f"{weather.format_summary(payload)}")
        except queue.Empty:
            pass
        # Cronômetro ao vivo do teste em andamento.
        if self.test_active and self.test_t0 is not None:
            self.m_elapsed.set(f"{time.monotonic() - self.test_t0:.1f} s")
        self.root.after(50, self._poll_events)

    def on_close(self):
        try:
            self.serial.close()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # tema nativo no Windows
    except tk.TclError:
        pass
    app = GpsBypassApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
