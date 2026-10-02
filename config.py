from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    # One-file resources are temporary; persist logs in a user-writable location.
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "BriefingMeteorologico"
else:
    DATA_DIR = ROOT
LOG_DIR = DATA_DIR / "logs"
ROUTE_SAMPLE_INTERVAL_NM = 50.0
API_TIMEOUT_SECONDS = 20
CACHE_TTL_SECONDS = 300
PROP_CRUISE_SPEED_KT = 160
JET_CRUISE_SPEED_KT = 430
PROP_ALTITUDES_FT = (5000, 7000, 9000, 11000, 13000, 15000, 17000)
JET_ALTITUDES_FT = (25000, 29000, 33000, 37000, 41000)
EDUCATIONAL_NOTICE = "Ferramenta educacional para simulação. Não utilizar como única fonte para operações aéreas reais."
AWC_BASE_URL = "https://aviationweather.gov/api/data"
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "MSFS2024-Educational-WeatherBriefing/1.0 (local desktop simulator)"
CLOUD_SIGNIFICANT_PERCENT = 50
ROUTE_SIGMET_CORRIDOR_NM = 25.0
NAV_CORRIDOR_NM = 250.0
NAV_AMBIGUITY_MARGIN_NM = 30.0
PRESSURE_LEVELS_HPA = (1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150)
OPEN_METEO_BATCH_SIZE = 10
