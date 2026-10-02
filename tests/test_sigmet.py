from datetime import datetime, timedelta, timezone

from analysis.sigmet import match_sigmets, sigmets_at_altitude
from models.flight_plan import RoutePoint
from models.weather import Sigmet


def test_sigmet_space_time_and_altitude():
    now = datetime.now(timezone.utc)
    point = RoutePoint("P", 0, 0, 0, 9000, now)
    polygon = {"type": "Polygon", "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]]}
    sigmet = Sigmet("A", "ICE", "SEV ICE", now - timedelta(hours=1), now + timedelta(hours=1), 5000, 11000, polygon)
    matches, messages = match_sigmets([sigmet], [point])
    assert matches and not messages
    assert sigmets_at_altitude(matches, 0, 9000)
    assert not sigmets_at_altitude(matches, 0, 15000)
    future = RoutePoint("P", 0, 0, 0, 9000, now + timedelta(hours=3))
    assert not match_sigmets([sigmet], [future])[0]
    remote = RoutePoint("P", 10, 10, 0, 9000, now)
    assert not match_sigmets([sigmet], [remote])[0]


def test_sigmet_missing_geometry_does_not_claim_crossing():
    now = datetime.now(timezone.utc)
    matches, messages = match_sigmets([Sigmet("A", "TS", "", now, now + timedelta(hours=1), None, None)], [])
    assert not matches and messages
