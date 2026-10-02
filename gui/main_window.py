import logging
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import EDUCATIONAL_NOTICE, LOG_DIR
from models.aircraft import AircraftCategory, AircraftProfile
from models.flight_plan import FlightPlan
from reports.report_generator import save_report
from services.flight_analyzer import FlightAnalyzer
from models.weather import RiskLevel
from services.navigation import parse_route

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Planejamento meteorológico de voo • MSFS 2024")
        self.geometry("1080x800")
        self.minsize(800, 650)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        panel = ctk.CTkScrollableFrame(self)
        panel.grid(row=0, column=0, padx=20, pady=15, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Briefing meteorológico", font=("Segoe UI", 25, "bold")).grid(row=0, sticky="w")
        ctk.CTkLabel(panel, text="Dados oficiais e previsões de modelo • uso educacional").grid(row=1, sticky="w")
        options = ctk.CTkFrame(panel)
        options.grid(row=2, sticky="ew", pady=12)
        self.category = ctk.StringVar(value="HÉLICE")
        self.protection = ctk.StringVar(value="NÃO-FIKI")
        ctk.CTkLabel(options, text="TIPO DE AERONAVE").grid(row=0, column=0, padx=15, sticky="w")
        ctk.CTkLabel(options, text="PROTEÇÃO CONTRA GELO").grid(row=0, column=2, padx=25, sticky="w")
        for column, value in enumerate(("HÉLICE", "JATO")):
            ctk.CTkRadioButton(options, text=value, variable=self.category, value=value).grid(row=1, column=column, padx=15, pady=10)
        for column, value in enumerate(("NÃO-FIKI", "FIKI / EQUIPADA"), start=2):
            ctk.CTkRadioButton(options, text=value, variable=self.protection, value=value).grid(row=1, column=column, padx=15, pady=10)
        ctk.CTkLabel(panel, text="PLANO DE VOO").grid(row=3, sticky="w")
        self.route = ctk.CTkTextbox(panel, height=85)
        self.route.grid(row=4, sticky="ew", pady=(4, 10))
        self.route.insert("1.0", "BGKK DCT NASOP UT592 NONRO DCT XRAY DCT GIRUG GIRU4M BIKF")
        fields = ctk.CTkFrame(panel)
        fields.grid(row=5, sticky="ew")
        now = datetime.now(timezone.utc)
        self.altitude = self._field(fields, 0, "ALTITUDE (ft)", "9000")
        self.date = self._field(fields, 1, "SAÍDA UTC (AAAA-MM-DD)", now.strftime("%Y-%m-%d"))
        self.time = self._field(fields, 2, "HORA UTC (HH:MM)", now.strftime("%H:%M"))
        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=6, sticky="ew", pady=12)
        self.analyze_button = ctk.CTkButton(buttons, text="ANALISAR VOO", command=self.analyze)
        self.analyze_button.pack(side="left")
        self.save_button = ctk.CTkButton(buttons, text="SALVAR RELATÓRIO", command=self.save_report, state="disabled")
        self.save_button.pack(side="left", padx=12)
        self.status = ctk.CTkLabel(panel, text="Aguardando análise.", wraplength=900, justify="left")
        self.status.grid(row=7, sticky="w")
        self.output = ctk.CTkTextbox(panel, height=300, font=("Consolas", 13), wrap="word")
        self.output.grid(row=8, sticky="ew", pady=8)
        self.output.configure(state="disabled")
        ctk.CTkLabel(panel, text="Legenda: VERDE — BAIXO  |  AMARELO — ATENÇÃO  |  VERMELHO — ALTO").grid(row=9, sticky="w")
        ctk.CTkLabel(panel, text=EDUCATIONAL_NOTICE, wraplength=900, justify="left").grid(row=10, sticky="w", pady=8)
        self.report = ""
        self.events = queue.Queue()
        self.analyzer = FlightAnalyzer()
        self.busy = False
        self.closed = False
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll_events)

    @staticmethod
    def _field(parent, column: int, label: str, value: str):
        ctk.CTkLabel(parent, text=label).grid(row=0, column=column, padx=15, sticky="w")
        entry = ctk.CTkEntry(parent, width=200)
        entry.grid(row=1, column=column, padx=15, pady=(0, 12))
        entry.insert(0, value)
        return entry

    def analyze(self) -> None:
        if self.busy:
            return
        try:
            route = parse_route(self.route.get("1.0", "end"))
            aircraft = AircraftProfile.generic(AircraftCategory(self.category.get()), self.protection.get() != "NÃO-FIKI")
            try:
                altitude = int(self.altitude.get())
            except ValueError:
                raise ValueError("Informe a altitude em pés usando apenas um número inteiro.") from None
            if not 0 < altitude <= aircraft.max_altitude:
                raise ValueError(f"Informe altitude entre 1 e {aircraft.max_altitude} ft para este perfil.")
            try:
                departure = datetime.strptime(f"{self.date.get().strip()} {self.time.get().strip()}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                raise ValueError("Informe uma saída UTC válida no formato AAAA-MM-DD e HH:MM.") from None
            plan = FlightPlan(route, aircraft, altitude, departure)
        except ValueError as exc:
            messagebox.showerror("Revise os campos", str(exc), parent=self)
            return
        self.busy = True
        self.report = ""
        self.analyze_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.status.configure(text="Consultando METAR/TAF…", text_color="#eab308")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        threading.Thread(target=self.run_analysis, args=(plan,), daemon=True).start()

    def run_analysis(self, plan):
        # Worker never calls Tk, including after(). Main thread consumes the queue.
        try:
            result = self.analyzer.analyze_flight(plan, lambda text: self.events.put(("progress", text)))
            self.events.put(("result", result))
        except Exception:
            logger.exception("Falha na análise do voo")
            self.events.put(("error", f"Não foi possível concluir a análise. Verifique sua conexão com a internet. Consulte {LOG_DIR / 'app.log'} para detalhes."))

    def poll_events(self):
        if self.closed:
            return
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    self.status.configure(text=data)
                elif kind == "result":
                    self.report = data.report
                    self.output.configure(state="normal")
                    self.output.insert("1.0", self.report)
                    for tag, color in (("low", "#86efac"), ("attention", "#fde047"), ("high", "#fca5a5")):
                        self.output.tag_config(tag, foreground=color)
                    for index, line in enumerate(self.report.splitlines(), 1):
                        tag = "high" if "VERMELHO" in line else "attention" if "AMARELO" in line else "low" if "VERDE" in line else None
                        if tag:
                            self.output.tag_add(tag, f"{index}.0", f"{index}.end")
                    self.output.configure(state="disabled")
                    planned = next(a for a in data.altitudes if a.altitude_ft == data.plan.cruise_altitude_ft)
                    level = planned.risk.level
                    partial = not data.route_complete or not data.sigmet_available or planned.coverage_percent < 100
                    if partial:
                        level = max(level, RiskLevel.ATTENTION)
                    colors = ("#86efac", "#fde047", "#fca5a5")
                    self.status.configure(text=level.label + (" • análise parcial; consulte as limitações." if partial else " • briefing concluído."), text_color=colors[level])
                    self.save_button.configure(state="normal")
                    self.finish_analysis()
                else:
                    self.status.configure(text="Análise não concluída.", text_color="#fca5a5")
                    messagebox.showerror("Erro na análise", data, parent=self)
                    self.finish_analysis()
        except queue.Empty:
            pass
        self.after(100, self.poll_events)

    def finish_analysis(self):
        self.busy = False
        self.analyze_button.configure(state="normal")

    def close(self):
        self.closed = True
        self.destroy()

    def save_report(self) -> None:
        filename = filedialog.asksaveasfilename(parent=self, defaultextension=".txt", initialfile="briefing.txt",
                                               filetypes=[("Texto", "*.txt"), ("Markdown", "*.md")])
        if filename:
            try:
                save_report(self.report, Path(filename))
                self.status.configure(text="Relatório salvo.")
            except OSError:
                logger.exception("Falha ao salvar relatório")
                messagebox.showerror("Erro ao salvar", "Não foi possível salvar o relatório no local escolhido.", parent=self)
