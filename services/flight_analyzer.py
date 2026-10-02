import logging
from dataclasses import replace
import time
from datetime import datetime, timezone

from analysis.route_analysis import analyze_altitude
from analysis.sigmet import match_sigmets
from config import JET_ALTITUDES_FT, PROP_ALTITUDES_FT, ROUTE_SAMPLE_INTERVAL_NM
from models.aircraft import AircraftCategory
from models.weather import FlightAnalysis, RiskLevel, WeatherRisk
from reports.report_generator import generate_report
from services.atmospheric_weather import AtmosphericWeatherService
from services.aviation_weather import AviationWeatherService, taf_at_time
from services.http_client import JsonClient
from services.navigation import NavigationService
from utils.geo import generate_route_points

logger = logging.getLogger(__name__)


def condition_phenomena(condition):
    return " ".join([condition.phenomena, *(c.cloud_type or "" for c in condition.clouds)]) if condition else ""


def airport_phenomena(airport, taf_at, passage):
    values = []
    if taf_at:
        values.append(condition_phenomena(taf_at.prevailing))
        values.extend(condition_phenomena(p.conditions) for p in taf_at.alternatives)
    if airport and airport.metar and airport.metar.observed_utc and passage:
        if abs((passage - airport.metar.observed_utc).total_seconds()) <= 90 * 60:
            values.append(condition_phenomena(airport.metar))
    return " ".join(values)


class FlightAnalyzer:
    def __init__(self, aviation=None, navigation=None, atmosphere=None):
        client = JsonClient()
        self.aviation = aviation or AviationWeatherService(client)
        self.navigation = navigation or NavigationService(client)
        self.atmosphere = atmosphere or AtmosphericWeatherService()

    def analyze_flight(self, plan, progress=lambda text: None):
        started = time.monotonic()
        if plan.departure_utc.tzinfo is None or plan.departure_utc.utcoffset() is None:
            raise ValueError("A saída deve possuir fuso UTC explícito.")
        if not 0 < plan.cruise_altitude_ft <= plan.aircraft.max_altitude or plan.aircraft.cruise_speed <= 0:
            raise ValueError("Altitude ou velocidade incompatível com o perfil.")
        result = FlightAnalysis(plan)
        progress("Consultando METAR/TAF…")
        for icao in dict.fromkeys((plan.route.origin, plan.route.destination, *plan.alternates)):
            result.airports[icao] = self.aviation.get_airport_weather(icao)
        progress("Resolvendo rota…")
        anchors, messages, result.route_complete = self.navigation.resolve_route(plan.route)
        result.messages.extend(messages)
        result.route_points = generate_route_points(anchors, plan.cruise_altitude_ft, plan.departure_utc,
                                                    plan.aircraft.cruise_speed, ROUTE_SAMPLE_INTERVAL_NM)
        logger.info("Quantidade de pontos da rota: %d", len(result.route_points))
        if len(result.route_points) > 1:
            result.eta_utc = result.route_points[-1].estimated_time_utc
        # Latest issued TAF may start later than today's departure. Ask for the
        # documented validity-time query before declaring that ETA uncovered.
        for icao, passage in ((plan.route.origin, plan.departure_utc), (plan.route.destination, result.eta_utc)):
            airport = result.airports[icao]
            taf = airport.taf
            covered = taf and taf.start_utc and taf.end_utc and passage and taf.start_utc <= passage < taf.end_utc
            if passage and not covered:
                replacement = self.aviation.get_taf(icao, at_time=passage)
                if replacement and replacement.start_utc and replacement.end_utc and replacement.start_utc <= passage < replacement.end_utc:
                    result.airports[icao] = replace(airport, taf=replacement, taf_raw=replacement.raw,
                        messages=tuple(m for m in airport.messages if not m.startswith("TAF não disponível")))
        result.departure_taf = taf_at_time(result.airports[plan.route.origin].taf, plan.departure_utc)
        result.arrival_taf = taf_at_time(result.airports[plan.route.destination].taf, result.eta_utc)
        result.messages.append("ETA aproximada com velocidade constante; sem correção de vento, subida, descida ou procedimentos.")
        progress("Consultando SIGMET…")
        sigmets, error = self.aviation.get_sigmets()
        result.sigmet_available = error is None
        if error:
            result.messages.append("Não foi possível verificar SIGMETs. " + error)
        else:
            result.sigmets, messages = match_sigmets(sigmets, result.route_points)
            result.messages.extend(messages)
            if messages:
                result.sigmet_available = False
        result.messages.append("SIGMETs são os disponíveis no momento da consulta; ausência de aviso não garante ausência de perigo na hora do voo.")
        if abs((plan.departure_utc - datetime.now(timezone.utc)).total_seconds()) > 4 * 3600:
            result.sigmet_available = False
            result.messages.append("Voo distante do horário atual: os SIGMETs atuais não garantem cobertura futura. Consulte novamente perto da saída.")
        if result.route_points:
            profiles, messages = self.atmosphere.get_profiles(result.route_points, progress)
            result.messages.extend(messages)
        else:
            profiles = []
            result.messages.append("Sem coordenadas de origem e destino: atmosfera da rota e ETA não puderam ser avaliadas.")
        endpoint = {0: airport_phenomena(result.airports[plan.route.origin], result.departure_taf, plan.departure_utc)}
        if result.route_points:
            last = len(result.route_points) - 1
            endpoint[last] = endpoint.get(last, "") + " " + airport_phenomena(result.airports[plan.route.destination], result.arrival_taf, result.eta_utc)
        progress("Analisando altitude…")
        candidates = PROP_ALTITUDES_FT if plan.aircraft.category == AircraftCategory.PROP else JET_ALTITUDES_FT
        altitudes = sorted(set([plan.cruise_altitude_ft, *(a for a in candidates if a <= plan.aircraft.max_altitude)]))
        for altitude in altitudes:
            result.altitudes.append(analyze_altitude(result.route_points, profiles, altitude, plan.aircraft.fiki, result.sigmets, endpoint))
        incomplete = (not result.route_complete or not result.sigmet_available
                      or result.departure_taf.prevailing is None or result.arrival_taf.prevailing is None)
        if incomplete:
            result.messages.append("Avaliação geral parcial: rota, alertas ou previsão nos aeroportos não cobrem completamente o voo.")
            result.altitudes = [replace(a, risk=WeatherRisk(max(a.risk.level, RiskLevel.ATTENTION),
                a.risk.reason + " A avaliação geral permanece parcial por dados/rota/alertas incompletos.",
                "BAIXA", a.risk.available)) for a in result.altitudes]
        progress("Gerando briefing…")
        result.report = generate_report(result)
        logger.info("Análise finalizada em %.1f segundos", time.monotonic() - started)
        return result


_default_analyzer = None


def analyze_flight(flight_plan, progress=lambda text: None):
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = FlightAnalyzer()
    return _default_analyzer.analyze_flight(flight_plan, progress)
