from dataclasses import dataclass
from enum import Enum

from config import JET_CRUISE_SPEED_KT, PROP_CRUISE_SPEED_KT


class AircraftCategory(str, Enum):
    PROP = "HÉLICE"
    JET = "JATO"


@dataclass(frozen=True)
class AircraftProfile:
    name: str
    category: AircraftCategory
    max_altitude: int
    typical_cruise_altitude: int
    fiki: bool
    cruise_speed: float

    @classmethod
    def generic(cls, category: AircraftCategory, fiki: bool) -> "AircraftProfile":
        jet = category == AircraftCategory.JET
        return cls(category.value, category, 41000 if jet else 17000,
                   33000 if jet else 9000, fiki,
                   JET_CRUISE_SPEED_KT if jet else PROP_CRUISE_SPEED_KT)
