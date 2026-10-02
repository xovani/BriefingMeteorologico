"""Great-circle geometry on a spherical Earth, distances in nautical miles."""
import math
from datetime import timedelta

from models.flight_plan import RoutePoint

EARTH_RADIUS_NM = 3440.065


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = lat2 - lat1, math.radians(b[1] - a[1])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_NM * 2 * math.asin(math.sqrt(min(1, max(0, value))))


def bearing(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    return math.degrees(math.atan2(math.sin(dlon) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))) % 360


def interpolate_great_circle(a, b, fraction: float) -> tuple[float, float]:
    if not 0 <= fraction <= 1:
        raise ValueError("Fração geográfica fora de 0–1.")
    if fraction == 0:
        return a
    if fraction == 1:
        return b
    angle = haversine(a, b) / EARTH_RADIUS_NM
    if angle < 1e-10:
        return a
    if abs(math.sin(angle)) < 1e-10:
        raise ValueError("Trecho antipodal não possui direção única.")
    weights = (math.sin((1 - fraction) * angle) / math.sin(angle), math.sin(fraction * angle) / math.sin(angle))
    vectors = []
    for lat, lon in (a, b):
        lat, lon = math.radians(lat), math.radians(lon)
        vectors.append((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)))
    x, y, z = (weights[0] * vectors[0][i] + weights[1] * vectors[1][i] for i in range(3))
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def generate_route_points(anchors, altitude_ft, departure_utc, speed_kt, interval_nm=50):
    if speed_kt <= 0 or interval_nm <= 0:
        raise ValueError("Velocidade e intervalo devem ser positivos.")
    if not anchors:
        return []
    points, accumulated = [], 0.0
    name, lat, lon = anchors[0]
    points.append(RoutePoint(name, lat, lon, 0, altitude_ft, departure_utc))
    for start, end in zip(anchors, anchors[1:]):
        a, b = start[1:], end[1:]
        distance = haversine(a, b)
        count = max(1, math.ceil(distance / interval_nm))
        for index in range(1, count + 1):
            coordinate = interpolate_great_circle(a, b, index / count)
            cumulative = accumulated + distance * index / count
            label = end[0] if index == count else f"{start[0]} → {end[0]} / P{index}"
            points.append(RoutePoint(label, *coordinate, cumulative, altitude_ft,
                                     departure_utc + timedelta(hours=cumulative / speed_kt)))
        accumulated += distance
    return points
