"""Manual real API verification; never collected by pytest."""
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.aircraft import AircraftCategory, AircraftProfile
from models.flight_plan import FlightPlan
from reports.report_generator import save_report
from services.flight_analyzer import FlightAnalyzer
from services.navigation import parse_route
from utils.logger import configure_logging


def main():
    configure_logging()
    analyzer = FlightAnalyzer()
    for icao in ("SBSP", "KJFK", "BIKF", "BGKK"):
        airport = analyzer.aviation.get_airport_weather(icao)
        print(icao, "METAR:", bool(airport.metar), "TAF:", bool(airport.taf), "Avisos:", airport.messages, flush=True)
    directory = Path(__file__).resolve().parents[1] / "manual_results"
    directory.mkdir(exist_ok=True)
    for name, route in (("sbsp_sbgr", "SBSP DCT SBGR"),
                        ("bgkk_bikf", "BGKK DCT NASOP UT592 NONRO DCT XRAY DCT GIRUG GIRU4M BIKF")):
        plan = FlightPlan(parse_route(route), AircraftProfile.generic(AircraftCategory.PROP, False),
                          9000, datetime.now(timezone.utc))
        result = analyzer.analyze_flight(plan, lambda text: print(text, flush=True))
        for suffix in (".txt", ".md"):
            save_report(result.report, directory / (name + suffix))
        planned = next(a for a in result.altitudes if a.altitude_ft == 9000)
        print(name, "pontos:", len(result.route_points), "cobertura:", planned.coverage_percent,
              "risco:", planned.risk.level.label, "avisos:", result.messages, flush=True)
        assert all(p.weather is None or p.weather.cloud_top_ft is None for p in planned.points)


if __name__ == "__main__":
    main()
