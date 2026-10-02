from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests

from models.weather import MetarSummary, TafPeriod, TafSummary
from services.aviation_weather import normalize_conditions, normalize_taf, taf_at_time
from services.http_client import JsonClient


def test_metar_structured_normalization():
    summary = normalize_conditions({"wdir": 200, "wspd": 15, "wgst": 25,
        "visib": 6.21, "temp": 8, "dewp": 5, "altim": 975,
        "wxString": "-FZRA TSRA SN", "clouds": [{"cover": "BKN", "base": 4500, "type": "CB"}]},
        "BIKF 011800Z 20015G25KT 9999 SCT020 BKN045 08/05 Q0975")
    assert summary.visibility_km == pytest.approx(10)
    assert summary.visibility_at_least
    assert summary.qnh_hpa == 975
    assert summary.clouds[0].base_ft_agl == 4500
    assert "FZRA" in summary.phenomena


def test_taf_normalization_and_arrival_tempo():
    taf = normalize_taf({"rawTAF": "TAF", "validTimeFrom": 0, "validTimeTo": 7200,
                        "fcsts": [{"timeFrom": 0, "timeTo": 7200, "wspd": 10},
                                  {"timeFrom": 1000, "timeTo": 3000, "fcstChange": "TEMPO", "wxString": "TSRA"}]})
    at = taf_at_time(taf, datetime.fromtimestamp(2000, timezone.utc))
    assert at.prevailing.wind_speed_kt == 10
    assert at.alternatives[0].conditions.phenomena == "TSRA"
    assert taf_at_time(taf, datetime.fromtimestamp(9000, timezone.utc)).prevailing is None


def test_becmg_persists_after_transition():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    taf = TafSummary("", start, start + timedelta(hours=12), (
        TafPeriod(start, start + timedelta(hours=12), "INICIAL", MetarSummary("", wind_speed_kt=10)),
        TafPeriod(start + timedelta(hours=2), start + timedelta(hours=4), "BECMG",
                  MetarSummary("", wind_speed_kt=25), transition_end_utc=start + timedelta(hours=4))))
    assert taf_at_time(taf, start + timedelta(hours=3)).alternatives
    assert taf_at_time(taf, start + timedelta(hours=5)).prevailing.wind_speed_kt == 25


def test_204_and_cache():
    session = Mock()
    session.get.return_value.status_code = 204
    clock = Mock(return_value=100)
    client = JsonClient(session, clock=clock)
    assert client.get("https://example.test/metar", {}).data == []
    assert client.get("https://example.test/metar", {}).status == 204
    assert session.get.call_count == 1
    clock.return_value = 401
    client.get("https://example.test/metar", {})
    assert session.get.call_count == 2


def test_timeout():
    session = Mock()
    session.get.side_effect = requests.Timeout("timeout")
    result = JsonClient(session).get("https://example.test", {})
    assert result.error and result.data is None


@pytest.mark.parametrize("status", [400, 403, 404, 429, 500, 502, 504])
def test_http_errors(status):
    session = Mock()
    response = Mock(status_code=status, headers={})
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    session.get.return_value = response
    assert JsonClient(session).get("https://example.test", {}).status == status
