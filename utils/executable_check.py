"""Opt-in verification of the real packaged GUI, dependencies and live HTTPS."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import certifi
import pyproj

from config import LOG_DIR
from gui.main_window import MainWindow
from reports.report_generator import save_report


def verify_executable(diagnostic_path: Path) -> None:
    diagnostic_path = diagnostic_path.resolve()
    diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
    window = MainWindow()
    result = {"frozen": bool(getattr(sys, "frozen", False)),
              "executable": sys.executable, "bundle": str(getattr(sys, "_MEIPASS", "")),
              "certificates_present": Path(certifi.where()).is_file(),
              "projection_database_present": (Path(pyproj.datadir.get_data_dir()) / "proj.db").is_file(),
              "log_path": str(LOG_DIR / "app.log"), "heartbeat": 0,
              "completed_utc": None, "ok": False}
    original_analyze = window.analyzer.analyze_flight
    analysis = []

    def capture(plan, progress):
        value = original_analyze(plan, progress)
        analysis.append(value)
        return value

    window.analyzer.analyze_flight = capture
    window.route.delete("1.0", "end")
    window.route.insert("1.0", "SBSP DCT SBGR")

    def finish(error=None):
        if window.closed:
            return
        if error:
            result["error"] = str(error)
        result["completed_utc"] = datetime.now(timezone.utc).isoformat()
        diagnostic_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        window.close()

    def callback_error(exc_type, exc_value, tb):
        finish(f"{exc_type.__name__}: {exc_value}")

    def heartbeat():
        if window.busy:
            result["heartbeat"] += 1
        if not window.closed:
            window.after(100, heartbeat)

    def check():
        if window.closed:
            return
        if window.busy:
            window.after(200, check)
            return
        try:
            if not analysis:
                raise RuntimeError("Análise não concluída")
            briefing = analysis[0]
            planned = next(a for a in briefing.altitudes if a.altitude_ft == 9000)
            result.update({"route_points": len(briefing.route_points),
                           "atmosphere_coverage_percent": planned.coverage_percent,
                           "metar_origin": bool(briefing.airports["SBSP"].metar),
                           "metar_destination": bool(briefing.airports["SBGR"].metar),
                           "messages": briefing.messages})
            for suffix in (".txt", ".md"):
                save_report(window.report, diagnostic_path.with_suffix(suffix))
            result["ok"] = (result["certificates_present"] and result["projection_database_present"]
                            and result["heartbeat"] > 2 and planned.coverage_percent == 100
                            and result["metar_origin"] and result["metar_destination"])
            finish(None if result["ok"] else "Verificação incompleta; consulte os campos do diagnóstico")
        except Exception as exc:
            finish(exc)

    window.report_callback_exception = callback_error
    window.after(100, heartbeat)
    window.after(300, window.analyze)
    window.after(600, check)
    window.after(180000, lambda: finish("Tempo limite da verificação excedido"))
    window.mainloop()
    if not result["ok"]:
        raise SystemExit(1)
