from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    ATTENTION = 1
    HIGH = 2

    @property
    def label(self) -> str:
        return ("VERDE — BAIXO", "AMARELO — ATENÇÃO", "VERMELHO — ALTO")[self.value]


@dataclass(frozen=True)
class WeatherRisk:
    level: RiskLevel
    reason: str
    confidence: str = "MÉDIA"
    available: bool = True


@dataclass(frozen=True)
class CloudLayer:
    cover: str
    base_ft_agl: float | None
    cloud_type: str | None = None


@dataclass(frozen=True)
class MetarSummary:
    raw: str
    observed_utc: datetime | None = None
    wind_direction: float | str | None = None
    wind_speed_kt: float | None = None
    gust_kt: float | None = None
    visibility_km: float | None = None
    visibility_at_least: bool = False
    temperature_c: float | None = None
    dewpoint_c: float | None = None
    qnh_hpa: float | None = None
    clouds: tuple[CloudLayer, ...] = ()
    phenomena: str = ""
    vertical_visibility_ft: float | None = None


@dataclass(frozen=True)
class TafPeriod:
    start_utc: datetime
    end_utc: datetime
    change: str
    conditions: MetarSummary
    probability: int | None = None
    transition_end_utc: datetime | None = None
    inherit_phenomena: bool = False


@dataclass(frozen=True)
class TafSummary:
    raw: str
    start_utc: datetime | None
    end_utc: datetime | None
    periods: tuple[TafPeriod, ...]


@dataclass(frozen=True)
class TafAtTime:
    prevailing: MetarSummary | None
    alternatives: tuple[TafPeriod, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Sigmet:
    identifier: str
    hazard: str
    raw: str
    start_utc: datetime | None
    end_utc: datetime | None
    base_ft: float | None
    top_ft: float | None
    geometry: dict | None = None


@dataclass(frozen=True)
class SigmetMatch:
    sigmet: Sigmet
    point_indices: tuple[int, ...]


@dataclass(frozen=True)
class AirportWeather:
    icao: str
    metar_raw: str | None = None
    taf_raw: str | None = None
    metar: MetarSummary | None = None
    taf: TafSummary | None = None
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class AtmosphericWeather:
    latitude: float
    longitude: float
    valid_time_utc: datetime
    altitude_ft: int
    temperature_c: float | None = None
    freezing_level_ft: float | None = None
    cloud_cover_percent: float | None = None
    cloud_base_ft: float | None = None
    cloud_top_ft: float | None = None
    wind_direction_deg: float | None = None
    wind_speed_kt: float | None = None
    precipitation_mm: float | None = None
    relative_humidity_percent: float | None = None
    weather_code: int | None = None
    cape_j_kg: float | None = None
    pressure_hpa: float | None = None
    gust_surface_kt: float | None = None
    cloud_cover_low_percent: float | None = None
    cloud_cover_mid_percent: float | None = None
    cloud_cover_high_percent: float | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerticalLevel:
    height_m: float
    temperature_c: float | None
    humidity_percent: float | None
    cloud_percent: float | None
    wind_speed_kt: float | None
    wind_direction_deg: float | None


@dataclass(frozen=True)
class VerticalProfile:
    latitude: float
    longitude: float
    time_utc: datetime
    levels: tuple[VerticalLevel, ...]
    freezing_level_m: float | None = None
    precipitation_mm: float | None = None
    weather_code: int | None = None
    cape_j_kg: float | None = None
    surface_pressure_hpa: float | None = None
    gust_surface_kt: float | None = None
    cloud_low: float | None = None
    cloud_mid: float | None = None
    cloud_high: float | None = None
    terrain_m: float | None = None


@dataclass(frozen=True)
class RouteWeatherPoint:
    point: "RoutePoint"
    weather: AtmosphericWeather | None
    icing: WeatherRisk
    convection: WeatherRisk
    turbulence: WeatherRisk
    heading_deg: float | None = None
    headwind_kt: float | None = None
    crosswind_kt: float | None = None


@dataclass(frozen=True)
class AltitudeAnalysis:
    altitude_ft: int
    points: tuple[RouteWeatherPoint, ...]
    risk: WeatherRisk
    coverage_percent: float


@dataclass
class FlightAnalysis:
    plan: "FlightPlan"
    airports: dict[str, AirportWeather] = field(default_factory=dict)
    route_points: list["RoutePoint"] = field(default_factory=list)
    altitudes: list[AltitudeAnalysis] = field(default_factory=list)
    sigmets: list[SigmetMatch] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    eta_utc: datetime | None = None
    arrival_taf: TafAtTime | None = None
    departure_taf: TafAtTime | None = None
    sigmet_available: bool = False
    route_complete: bool = False
    report: str = ""


from models.flight_plan import FlightPlan, RoutePoint  # noqa: E402
