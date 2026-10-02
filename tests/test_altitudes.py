from datetime import datetime, timezone

from analysis.recommendation import favorable_altitudes
from analysis.route_analysis import analyze_altitude
from models.flight_plan import RoutePoint
from models.weather import RiskLevel, VerticalLevel, VerticalProfile
from utils.units import meters_to_feet


def test_altitudes_reuse_profile_and_differ():
    now = datetime.now(timezone.utc)
    points = [RoutePoint("P", 0, 0, 0, 9000, now)]
    profiles = [VerticalProfile(0, 0, now, (VerticalLevel(1500, 4, 50, 10, 10, 90),
        VerticalLevel(2500, -5, 90, 95, 20, 90), VerticalLevel(4500, -15, 40, 5, 30, 90)), 2000, weather_code=0)]
    low = analyze_altitude(points, profiles, meters_to_feet(1500), False)
    high = analyze_altitude(points, profiles, meters_to_feet(2500), False)
    assert low.risk.level == RiskLevel.LOW and high.risk.level == RiskLevel.HIGH
    assert favorable_altitudes([low, high]) == [low.altitude_ft]
    assert favorable_altitudes([low, high], route_complete=False) == []


def test_missing_profile_not_favorable():
    now = datetime.now(timezone.utc)
    result = analyze_altitude([RoutePoint("P", 0, 0, 0, 9000, now)], [None], 9000, False)
    assert result.coverage_percent == 0
    assert favorable_altitudes([result]) == []
