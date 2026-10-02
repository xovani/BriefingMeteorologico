from datetime import datetime, timezone

import pytest

from analysis.convection import assess_convection
from analysis.icing import assess_icing
from analysis.turbulence import assess_turbulence
from analysis.wind import wind_components
from models.weather import AtmosphericWeather, RiskLevel


def weather(temp=-5, cloud=60, humidity=70, freezing=None):
    return AtmosphericWeather(0, 0, datetime.now(timezone.utc), 9000, temperature_c=temp,
                              cloud_cover_percent=cloud, relative_humidity_percent=humidity,
                              freezing_level_ft=freezing, weather_code=0)


def test_low_icing():
    assert assess_icing(weather(5, 20), False).level == RiskLevel.LOW


def test_attention_icing():
    assert assess_icing(weather(), True).level == RiskLevel.ATTENTION


def test_high_and_non_fiki():
    assert assess_icing(weather(-5, 95, 90, 6000), True).level == RiskLevel.HIGH
    assert assess_icing(weather(), False).level == RiskLevel.HIGH
    assert "não-FIKI" in assess_icing(weather(), False).reason


@pytest.mark.parametrize("phenomena", ["FZRA", "FZDZ"])
def test_freezing_precipitation(phenomena):
    assert assess_icing(None, True, phenomena).level == RiskLevel.HIGH


def test_missing_is_not_green():
    risk = assess_icing(None, False)
    assert not risk.available and risk.level == RiskLevel.ATTENTION


def test_convection_and_turbulence_separate():
    assert assess_convection(weather(), "TSRA CB").level == RiskLevel.HIGH
    assert not assess_turbulence().available


def test_wind_components():
    assert wind_components(90, 90, 30) == pytest.approx((30, 0))
    assert wind_components(90, 270, 30) == pytest.approx((-30, 0), abs=1e-9)
