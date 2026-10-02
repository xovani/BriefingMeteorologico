"""AWC OpenAPI v4: official structured METAR/TAF/SIGMET products."""
from dataclasses import replace
import logging
import re

from config import AWC_BASE_URL
from models.weather import (AirportWeather, CloudLayer, MetarSummary, Sigmet,
                            TafAtTime, TafPeriod, TafSummary)
from services.http_client import JsonClient
from utils.time import number, utc_datetime

logger = logging.getLogger(__name__)


def normalize_conditions(data: dict, raw: str = "") -> MetarSummary:
    vis = data.get("visib")
    visibility = number(str(vis).replace("+", "")) if vis is not None else None
    clouds = tuple(CloudLayer(str(c.get("cover") or "?"), number(c.get("base")), c.get("type"))
                   for c in (data.get("clouds") or []) if isinstance(c, dict))
    # AWC visib is statute miles; raw international 9999 means >= 10 km.
    at_least = "+" in str(vis)
    if re.search(r"\b9999(?:NDV)?\b|\bCAVOK\b", raw):
        visibility, at_least = 10 / 1.609344, True
    direction = data.get("wdir")
    if direction != "VRB":
        direction = number(direction)
    return MetarSummary(raw, utc_datetime(data.get("obsTime")), direction,
                        number(data.get("wspd")), number(data.get("wgst")),
                        visibility * 1.609344 if visibility is not None else None,
                        at_least, number(data.get("temp")), number(data.get("dewp")),
                        number(data.get("altim")), clouds,
                        str(data.get("wxString") or ""), number(data.get("vertVis")))


def normalize_taf(data: dict) -> TafSummary:
    periods = []
    for group in data.get("fcsts") or []:
        if not isinstance(group, dict):
            continue
        start, end = utc_datetime(group.get("timeFrom")), utc_datetime(group.get("timeTo"))
        if start is None or end is None or start >= end:
            continue
        periods.append(TafPeriod(start, end, group.get("fcstChange") or "INICIAL",
                                 normalize_conditions(group), group.get("probability"),
                                 utc_datetime(group.get("timeBec")), group.get("wxString") is None))
    return TafSummary(data.get("rawTAF") or "", utc_datetime(data.get("validTimeFrom")),
                      utc_datetime(data.get("validTimeTo")), tuple(periods))


def merge_conditions(previous: MetarSummary | None, current: MetarSummary, inherit_phenomena=False) -> MetarSummary:
    if previous is None:
        return current
    # Change groups may omit unchanged fields. Empty decoded wxString means no weather.
    return replace(current,
                   wind_direction=current.wind_direction if current.wind_direction is not None else previous.wind_direction,
                   wind_speed_kt=current.wind_speed_kt if current.wind_speed_kt is not None else previous.wind_speed_kt,
                   gust_kt=current.gust_kt if current.wind_speed_kt is not None else previous.gust_kt,
                   visibility_km=current.visibility_km if current.visibility_km is not None else previous.visibility_km,
                   visibility_at_least=current.visibility_at_least if current.visibility_km is not None else previous.visibility_at_least,
                   clouds=current.clouds or previous.clouds,
                   phenomena=previous.phenomena if inherit_phenomena else current.phenomena)


def taf_at_time(taf: TafSummary | None, target) -> TafAtTime:
    if taf is None:
        return TafAtTime(None, note="TAF não disponível.")
    if target is None:
        return TafAtTime(None, note="Horário de passagem não disponível; grupo relevante não determinado.")
    if taf.start_utc is None or taf.end_utc is None or not taf.start_utc <= target < taf.end_utc:
        return TafAtTime(None, note="Horário previsto fora da validade do TAF disponível.")
    prevailing = None
    alternatives = []
    for period in sorted(taf.periods, key=lambda p: p.start_utc):
        if period.start_utc > target:
            continue
        if period.change in ("TEMPO", "PROB", "PROB30", "PROB40") or period.probability:
            if target < period.end_utc:
                alternatives.append(period)
        elif period.change == "BECMG":
            if target < (period.transition_end_utc or period.end_utc):
                alternatives.append(period)
            else:
                prevailing = merge_conditions(prevailing, period.conditions, period.inherit_phenomena)
        elif period.change in ("INICIAL", "FM"):
            prevailing = period.conditions
    alternatives = [replace(p, conditions=merge_conditions(prevailing, p.conditions, p.inherit_phenomena)) for p in alternatives]
    return TafAtTime(prevailing, tuple(alternatives),
                     "TEMPO/PROB são possibilidades; BECMG indica transição, sem horário exato da mudança."
                     if alternatives else ("Grupo predominante aproximado na ETA." if prevailing else "Grupo não determinado com segurança."))


class AviationWeatherService:
    def __init__(self, client=None):
        self.client = client or JsonClient()
        self.last_errors = {}

    def _get(self, product, icao, at_time=None):
        params = {"ids": icao, "format": "json"}
        if at_time is not None:
            params["date"] = at_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["time"] = "valid"
        result = self.client.get(f"{AWC_BASE_URL}/{product}", params)
        self.last_errors[(product, icao)] = result.error
        if not isinstance(result.data, list):
            return None
        matches = [d for d in result.data if isinstance(d, dict) and d.get("icaoId") == icao]
        return matches[0] if matches else None

    def get_metar(self, icao: str) -> MetarSummary | None:
        icao = icao.upper()
        data = self._get("metar", icao)
        return normalize_conditions(data, data.get("rawOb") or "") if data else None

    def get_taf(self, icao: str, at_time=None) -> TafSummary | None:
        data = self._get("taf", icao.upper(), at_time)
        return normalize_taf(data) if data else None

    def get_airport_weather(self, icao: str) -> AirportWeather:
        icao = icao.upper()
        metar, taf = self.get_metar(icao), self.get_taf(icao)
        messages = []
        for product, available in (("metar", metar), ("taf", taf)):
            if available is None:
                error = self.last_errors.get((product, icao))
                messages.append(f"{product.upper()} não disponível para {icao}." + (f" {error}" if error else ""))
                logger.warning(messages[-1])
        return AirportWeather(icao, metar.raw if metar else None, taf.raw if taf else None,
                              metar, taf, tuple(messages))

    def get_sigmets(self):
        result = self.client.get(f"{AWC_BASE_URL}/sigmet", {"format": "geojson"})
        if result.error:
            return [], result.error
        if result.status == 204:
            return [], None
        if not isinstance(result.data, dict) or not isinstance(result.data.get("features"), list):
            return [], "Resposta SIGMET inválida; cobertura de alertas não determinada."
        sigmets = []
        for feature in result.data["features"]:
            if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
                return sigmets, "SIGMET com estrutura incompleta; cobertura de alertas não determinada."
            props = feature.get("properties") or {}
            sigmets.append(Sigmet(str(props.get("seriesId") or feature.get("id") or "?"),
                                  str(props.get("hazard") or ""), props.get("rawSigmet") or "",
                                  utc_datetime(props.get("validTimeFrom")), utc_datetime(props.get("validTimeTo")),
                                  number(props.get("base")), number(props.get("top")), feature.get("geometry")))
        return sigmets, None


_default_service = AviationWeatherService()
get_metar = _default_service.get_metar
get_taf = _default_service.get_taf
get_airport_weather = _default_service.get_airport_weather
