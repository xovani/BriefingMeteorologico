"""Syntactic route parser. No navigation database or coordinate claims yet."""
import re
import logging

from config import AWC_BASE_URL, NAV_AMBIGUITY_MARGIN_NM, NAV_CORRIDOR_NM
from models.flight_plan import ParsedRoute
from services.http_client import JsonClient
from utils.geo import haversine, interpolate_great_circle
from utils.time import number

logger = logging.getLogger(__name__)

ICAO = re.compile(r"[A-Z]{4}")
AIRWAY = re.compile(r"(?:U?[ABGHJLMNPQRTVWY])[0-9]{1,4}[A-Z]?")
PROCEDURE = re.compile(r"[A-Z]{2,6}[0-9][A-Z0-9]{0,2}")
WAYPOINT = re.compile(r"[A-Z]{2,5}")
INSTRUCTIONS = {"DCT"}


def parse_route(text: str) -> ParsedRoute:
    tokens = text.upper().split()
    if len(tokens) < 2:
        raise ValueError("Informe ao menos os aeroportos de origem e destino (códigos ICAO).")
    if not ICAO.fullmatch(tokens[0]) or not ICAO.fullmatch(tokens[-1]):
        raise ValueError("Origem e destino devem ser códigos ICAO de quatro letras.")
    waypoints, airways, procedures, unresolved, ordered = [], [], [], [], []
    for token in tokens[1:-1]:
        if token in INSTRUCTIONS:
            continue
        ordered.append(token)
        if AIRWAY.fullmatch(token):
            airways.append(token)
        elif PROCEDURE.fullmatch(token):
            procedures.append(token)
        elif WAYPOINT.fullmatch(token):
            waypoints.append(token)
        else:
            unresolved.append(token)
    return ParsedRoute(" ".join(tokens), tokens[0], tokens[-1], waypoints,
                       airways, procedures, unresolved, ordered)


class NavigationService:
    def __init__(self, client=None):
        self.client = client or JsonClient()

    def candidates(self, product, identifier):
        result = self.client.get(f"{AWC_BASE_URL}/{product}", {"ids": identifier, "format": "json"})
        candidates = []
        for item in result.data if isinstance(result.data, list) else []:
            if not isinstance(item, dict) or item.get("icaoId" if product == "airport" else "id") != identifier:
                continue
            lat, lon = number(item.get("lat")), number(item.get("lon"))
            if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                value = (identifier, lat, lon)
                if value not in candidates:
                    candidates.append(value)
        return candidates, result.error

    def resolve_route(self, route):
        messages = []
        endpoints = []
        for identifier in (route.origin, route.destination):
            candidates, error = self.candidates("airport", identifier)
            if len(candidates) != 1:
                messages.append(f"Aeroporto {identifier} não pôde ser resolvido com segurança." + (f" {error}" if error else ""))
                endpoints.append(None)
            else:
                endpoints.append(candidates[0])
        if not all(endpoints):
            return [], messages, False
        origin, destination = endpoints
        direct = haversine(origin[1:], destination[1:])
        corridor = [interpolate_great_circle(origin[1:], destination[1:], i / max(1, int(direct / 25) + 1))
                    for i in range(max(1, int(direct / 25) + 1) + 1)]
        anchors = [origin]
        complete = not (route.unresolved_tokens or route.airways or route.procedures)
        for token in route.route_tokens:
            if token not in route.waypoints:
                continue
            product = "fix" if len(token) == 5 else "navaid" if len(token) == 3 else None
            candidates, error = self.candidates(product, token) if product else ([], None)
            ranked = []
            for candidate in candidates:
                if min(haversine(candidate[1:], p) for p in corridor) <= NAV_CORRIDOR_NM:
                    score = haversine(anchors[-1][1:], candidate[1:]) + haversine(candidate[1:], destination[1:])
                    ranked.append((score, candidate))
            ranked.sort()
            if ranked and (len(ranked) == 1 or ranked[1][0] - ranked[0][0] >= NAV_AMBIGUITY_MARGIN_NM):
                anchors.append(ranked[0][1])
            else:
                complete = False
                message = f"Waypoint {token} não pôde ser resolvido com segurança."
                messages.append(message + (f" {error}" if error else ""))
                logger.warning(message)
        anchors.append(destination)
        for token in route.airways:
            messages.append(f"Aerovia {token} não expandida: conectados os pontos conhecidos antes e depois por grande círculo.")
        for token in route.procedures:
            messages.append(f"Procedimento {token} não expandido; seus fixes não foram adivinhados.")
        for token in route.unresolved_tokens:
            messages.append(f"Token {token} não reconhecido; excluído da geometria.")
        return anchors, messages, complete
