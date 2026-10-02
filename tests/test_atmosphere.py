from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from models.flight_plan import RoutePoint
from models.weather import VerticalLevel, VerticalProfile
from services.atmospheric_weather import interpolate_profile, profile_from_response, vertical_interpolate
from utils.units import meters_to_feet
from services.atmospheric_weather import AtmosphericWeatherService
from services.http_client import ApiResult


@pytest.mark.parametrize("hour, minute, forecast, start_date, end_date", [
    (23, 50, "2026-10-02T00:00", "2026-10-01", "2026-10-02"),
    (0, 10, "2026-10-01T00:00", "2026-09-30", "2026-10-01"),
])
def test_forecast_window_crosses_midnight(hour, minute, forecast, start_date, end_date):
    client = Mock()
    client.get.return_value = ApiResult({"hourly": {"time": [forecast]}})
    point = RoutePoint("P", 0, 0, 0, 9000,
                       datetime(2026, 10, 1, hour, minute, tzinfo=timezone.utc))
    profiles, messages = AtmosphericWeatherService(client).get_profiles([point])
    params = client.get.call_args.args[1]
    assert params["start_date"] == start_date
    assert params["end_date"] == end_date
    assert profiles[0].time_utc == datetime.fromisoformat(forecast).replace(tzinfo=timezone.utc)
    assert not messages


def test_vertical_interpolation():
    assert vertical_interpolate([2000, 3000], [-1, -7], 2750) == pytest.approx(-5.5)
    assert vertical_interpolate([2000, 3000], [-1, -7], 3500) is None
    assert vertical_interpolate([2000], [None], 2000) is None


def test_wind_interpolated_as_vector_not_angle():
    profile = VerticalProfile(0, 0, datetime.now(timezone.utc), (
        VerticalLevel(2000, -1, 80, 90, 20, 350), VerticalLevel(3000, -7, 90, 100, 20, 10)), 1800)
    weather = interpolate_profile(profile, meters_to_feet(2500))
    assert min(abs(weather.wind_direction_deg), abs(weather.wind_direction_deg - 360)) < 0.01
    assert weather.temperature_c == -4
    assert weather.freezing_level_ft == pytest.approx(meters_to_feet(1800))
    assert weather.cloud_top_ft is None and weather.cloud_base_ft is None


def test_outside_time_does_not_use_current_weather():
    point = RoutePoint("P", 0, 0, 0, 9000, datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert profile_from_response({"hourly": {"time": ["2026-10-01T12:00"]}}, point) is None


def test_actual_geopotential_heights_and_terrain_filter():
    point = RoutePoint("P", 0, 0, 0, 9000, datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc))
    profile = profile_from_response({"elevation": 1000, "hourly": {"time": ["2026-10-01T12:00"],
        "geopotential_height_1000hPa": [100], "geopotential_height_700hPa": [2850],
        "temperature_700hPa": [-7], "surface_pressure": [850]}}, point)
    assert len(profile.levels) == 1
    assert profile.levels[0].height_m == 2850
