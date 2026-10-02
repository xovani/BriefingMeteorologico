from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from analysis.convection import assess_convection
from analysis.icing import assess_icing
from models.weather import AtmosphericWeather, RiskLevel
from services.aviation_weather import AviationWeatherService, normalize_conditions, normalize_taf, taf_at_time
from services.http_client import ApiResult, JsonClient


def test_ndv_visibility_not_lost():
    summary = normalize_conditions({}, 'BGKK 012250Z AUTO 23007KT 9999NDV NCD 05/01 Q0988')
    assert summary.visibility_km == pytest.approx(10)


def test_tempo_inherits_wind_from_prevailing():
    taf = normalize_taf({'validTimeFrom': 0, 'validTimeTo': 7200, 'fcsts': [
        {'timeFrom': 0, 'timeTo': 7200, 'wdir': 200, 'wspd': 10, 'wgst': 20, 'wxString': '-RA'},
        {'timeFrom': 1000, 'timeTo': 3000, 'fcstChange': 'TEMPO', 'visib': 2}]})
    at = taf_at_time(taf, datetime.fromtimestamp(2000, timezone.utc))
    assert at.alternatives[0].conditions.wind_speed_kt == 10
    assert at.alternatives[0].conditions.gust_kt == 20
    assert at.alternatives[0].conditions.phenomena == '-RA'


@pytest.mark.parametrize('probability', [30, 40])
def test_prob_groups(probability):
    taf = normalize_taf({'validTimeFrom': 0, 'validTimeTo': 7200, 'fcsts': [
        {'timeFrom': 0, 'timeTo': 7200, 'wspd': 10},
        {'timeFrom': 1000, 'timeTo': 3000, 'fcstChange': 'PROB', 'probability': probability, 'wxString': 'FZDZ'}]})
    at = taf_at_time(taf, datetime.fromtimestamp(2000, timezone.utc))
    assert at.alternatives[0].probability == probability
    assert at.prevailing.wind_speed_kt == 10


def test_fm_replaces_prevailing():
    taf = normalize_taf({'validTimeFrom': 0, 'validTimeTo': 7200, 'fcsts': [
        {'timeFrom': 0, 'timeTo': 3600, 'wspd': 10},
        {'timeFrom': 3600, 'timeTo': 7200, 'fcstChange': 'FM', 'wspd': 25}]})
    assert taf_at_time(taf, datetime.fromtimestamp(4000, timezone.utc)).prevailing.wind_speed_kt == 25


def test_absent_taf_and_metar_service_continues():
    client = Mock()
    client.get.return_value = ApiResult([], status=204)
    airport = AviationWeatherService(client).get_airport_weather('BGKK')
    assert airport.taf is None and airport.metar is None
    assert len(airport.messages) == 2


def test_taf_query_for_validity_uses_documented_date():
    client = Mock()
    client.get.return_value = ApiResult([], status=204)
    AviationWeatherService(client).get_taf('SBSP', datetime(2026, 10, 1, 23, tzinfo=timezone.utc))
    params = client.get.call_args.args[1]
    assert params['date'] == '2026-10-01T23:00:00Z' and params['time'] == 'valid'


@pytest.mark.parametrize('code', [56, 57, 66, 67])
def test_modeled_freezing_precipitation_special_severity(code):
    weather = AtmosphericWeather(0, 0, datetime.now(timezone.utc), 9000, weather_code=code)
    risk = assess_icing(weather, True)
    assert risk.level == RiskLevel.HIGH
    assert 'modelo' in risk.reason and 'superfície' in risk.reason


def test_cape_is_not_a_confirmed_storm():
    weather = AtmosphericWeather(0, 0, datetime.now(timezone.utc), 9000, weather_code=0, cape_j_kg=2000)
    risk = assess_convection(weather)
    assert risk.level == RiskLevel.ATTENTION
    assert 'isoladamente não indica tempestade' in risk.reason


def test_sigmet_icing_priority_even_without_profile():
    risk = assess_icing(None, True, official_icing=True)
    assert risk.level == RiskLevel.HIGH and risk.available
    assert risk.confidence == 'ALTA'


def test_rate_limit_blocks_followup_requests():
    import requests
    session = Mock()
    response = Mock(status_code=429, headers={'Retry-After': '120'})
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    session.get.return_value = response
    client = JsonClient(session, clock=lambda: 100)
    assert client.get('https://example.test', {}).status == 429
    assert client.get('https://example.test', {'ids': 'OTHER'}).status == 429
    assert session.get.call_count == 1
