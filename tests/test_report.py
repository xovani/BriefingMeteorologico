from datetime import datetime, timezone
from unittest.mock import Mock

from config import EDUCATIONAL_NOTICE
from models.aircraft import AircraftCategory, AircraftProfile
from models.flight_plan import FlightPlan
from models.weather import AirportWeather, FlightAnalysis, VerticalLevel, VerticalProfile
from reports.report_generator import generate_report, save_report
from services.flight_analyzer import FlightAnalyzer
from services.navigation import parse_route


def test_report_with_partial_data_never_claims_real_values():
    plan = FlightPlan(parse_route('BGKK DCT BIKF'), AircraftProfile.generic(AircraftCategory.PROP, False),
                      9000, datetime(2026, 10, 1, tzinfo=timezone.utc))
    report = generate_report(FlightAnalysis(plan))
    assert EDUCATIONAL_NOTICE in report
    assert 'DADOS INSUFICIENTES' in report
    assert 'Topo das nuvens não disponível diretamente' in report
    assert 'NÃO-FIKI' in report
    assert 'DADOS SIMULADOS' not in report


def test_save_txt_and_markdown(tmp_path):
    for suffix in ('.txt', '.md'):
        path = tmp_path / ('briefing' + suffix)
        save_report('Condição: ATENÇÃO', path)
        assert 'Condição: ATENÇÃO' in path.read_text(encoding='utf-8')


def test_complete_mock_analysis_and_missing_taf():
    now = datetime.now(timezone.utc)
    plan = FlightPlan(parse_route('SBSP DCT SBGR'), AircraftProfile.generic(AircraftCategory.PROP, False), 9000, now)
    aviation, navigation, atmosphere = Mock(), Mock(), Mock()
    aviation.get_airport_weather.side_effect = lambda icao: AirportWeather(icao, messages=(f'TAF não disponível para {icao}.',))
    aviation.get_sigmets.return_value = ([], None)
    aviation.get_taf.return_value = None
    navigation.resolve_route.return_value = ([('SBSP', -23.62, -46.65), ('SBGR', -23.43, -46.47)], [], True)
    def profiles(points, progress):
        return [VerticalProfile(p.latitude, p.longitude, p.estimated_time_utc, (
            VerticalLevel(1000, 10, 40, 5, 10, 180), VerticalLevel(6000, -10, 50, 10, 25, 220)),
            4000, weather_code=0) for p in points], []
    atmosphere.get_profiles.side_effect = profiles
    result = FlightAnalyzer(aviation, navigation, atmosphere).analyze_flight(plan)
    assert result.eta_utc > now
    assert len(result.altitudes) == 7
    assert 'TAF não disponível' in result.report
    assert 'Temperatura prevista no cruzeiro' in result.report
    assert 'Topo das nuvens não disponível diretamente' in result.report
    assert atmosphere.get_profiles.call_count == 1
