from dataclasses import dataclass, field
from datetime import datetime

from models.aircraft import AircraftProfile


@dataclass(frozen=True)
class ParsedRoute:
    raw: str
    origin: str
    destination: str
    waypoints: list[str] = field(default_factory=list)
    airways: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    unresolved_tokens: list[str] = field(default_factory=list)
    # Preserves order for future coordinate resolution; these are candidates only.
    route_tokens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlightPlan:
    route: ParsedRoute
    aircraft: AircraftProfile
    cruise_altitude_ft: int
    departure_utc: datetime
    alternates: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoutePoint:
    name: str
    latitude: float
    longitude: float
    cumulative_distance_nm: float
    altitude_ft: int
    estimated_time_utc: datetime | None = None
