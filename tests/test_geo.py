from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from services.http_client import ApiResult
from services.navigation import NavigationService, parse_route
from utils.geo import generate_route_points, haversine, interpolate_great_circle
from utils.units import feet_to_meters, meters_to_feet


def test_units():
    assert meters_to_feet(304.8) == pytest.approx(1000)
    assert feet_to_meters(1000) == pytest.approx(304.8)


def test_haversine():
    assert haversine((0, 0), (0, 1)) == pytest.approx(60.04, abs=0.1)
    assert haversine((0, 179), (0, -179)) == pytest.approx(120.08, abs=0.1)
    assert haversine((0, 0), (0, 0)) == 0


def test_geographic_interpolation():
    assert interpolate_great_circle((0, 0), (0, 2), 0.5) == pytest.approx((0, 1))
    assert abs(interpolate_great_circle((0, 179), (0, -179), 0.5)[1]) == pytest.approx(180)


def test_points_distance_and_eta():
    departure = datetime(2026, 10, 1, tzinfo=timezone.utc)
    points = generate_route_points([("A", 0, 0), ("B", 0, 2)], 9000, departure, 160, 50)
    assert len(points) == 4
    assert points[-1].name == "B"
    assert points[-1].estimated_time_utc == departure + timedelta(hours=points[-1].cumulative_distance_nm / 160)
    assert all(haversine((a.latitude, a.longitude), (b.latitude, b.longitude)) <= 50.01
               for a, b in zip(points, points[1:]))


def test_unresolved_waypoint_keeps_endpoints():
    client = Mock()
    client.get.side_effect = [ApiResult([{"icaoId": "SBSP", "lat": -23.62, "lon": -46.65}]),
                              ApiResult([{"icaoId": "SBGR", "lat": -23.43, "lon": -46.47}]), ApiResult([])]
    anchors, messages, complete = NavigationService(client).resolve_route(parse_route("SBSP ABCDE SBGR"))
    assert len(anchors) == 2 and not complete
    assert any("ABCDE" in msg for msg in messages)


def test_ambiguous_fix_not_first_global_result():
    client = Mock()
    client.get.side_effect = [ApiResult([{"icaoId": "AAAA", "lat": 0, "lon": 0}]),
        ApiResult([{"icaoId": "BBBB", "lat": 0, "lon": 5}]),
        ApiResult([{"id": "ABCDE", "lat": 50, "lon": 80}, {"id": "ABCDE", "lat": 0, "lon": 2}])]
    anchors, _, _ = NavigationService(client).resolve_route(parse_route("AAAA ABCDE BBBB"))
    assert anchors[1] == ("ABCDE", 0, 2)
