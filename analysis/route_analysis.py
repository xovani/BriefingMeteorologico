from dataclasses import replace

from analysis.convection import assess_convection
from analysis.icing import assess_icing
from analysis.sigmet import sigmets_at_altitude
from analysis.turbulence import assess_turbulence
from analysis.wind import wind_components
from models.weather import AltitudeAnalysis, RiskLevel, RouteWeatherPoint, WeatherRisk
from services.atmospheric_weather import interpolate_profile
from utils.geo import bearing


def analyze_altitude(points, profiles, altitude_ft, fiki, matches=(), endpoint_phenomena=None):
    samples = []
    endpoint_phenomena = endpoint_phenomena or {}
    for index, (point, profile) in enumerate(zip(points, profiles)):
        weather = interpolate_profile(profile, altitude_ft) if profile else None
        relevant = sigmets_at_altitude(matches, index, altitude_ft)
        icing_official = any("ICE" in s.hazard.upper() or "ICING" in s.raw.upper() for s in relevant)
        # A cell cannot be considered avoided solely by flying above/below its reported layer.
        convection_official = any(("TS" in m.sigmet.hazard.upper() or "CONV" in m.sigmet.hazard.upper()
                                   or "TS" in m.sigmet.raw.upper()) and index in m.point_indices for m in matches)
        phenomena = endpoint_phenomena.get(index, "")
        icing = assess_icing(weather, fiki, phenomena, icing_official)
        convection = assess_convection(weather, phenomena, convection_official)
        turbulence = assess_turbulence(relevant)
        heading, headwind, crosswind = None, None, None
        if len(points) > 1:
            start, end = (points[index], points[index + 1]) if index < len(points) - 1 else (points[index - 1], points[index])
            heading = bearing((start.latitude, start.longitude), (end.latitude, end.longitude))
        if weather and heading is not None and weather.wind_direction_deg is not None and weather.wind_speed_kt is not None:
            headwind, crosswind = wind_components(heading, weather.wind_direction_deg, weather.wind_speed_kt)
        samples.append(RouteWeatherPoint(replace(point, altitude_ft=altitude_ft), weather, icing, convection,
                                         turbulence, heading, headwind, crosswind))
    sufficient = sum(s.weather is not None and s.weather.temperature_c is not None and s.weather.cloud_cover_percent is not None for s in samples)
    coverage = sufficient / len(samples) * 100 if samples else 0
    # Turbulence absence remains explicit but does not alone decide icing-based ranking.
    risks = [risk for sample in samples for risk in (sample.icing, sample.convection, sample.turbulence) if risk.available]
    if not risks:
        overall = WeatherRisk(RiskLevel.ATTENTION, "Dados insuficientes para avaliar a altitude.", "BAIXA", False)
    else:
        worst = max(risks, key=lambda risk: risk.level)
        incomplete = coverage < 100
        overall = WeatherRisk(max(worst.level, RiskLevel.ATTENTION if incomplete else RiskLevel.LOW),
                              worst.reason + (" Há pontos sem dados: avaliação parcial." if incomplete else ""),
                              "BAIXA" if incomplete else worst.confidence, True)
    return AltitudeAnalysis(altitude_ft, tuple(samples), overall, coverage)
