"""Open-Meteo hourly pressure profiles; no surface-temperature substitution."""
import math
from datetime import timedelta

from config import OPEN_METEO_BASE_URL, OPEN_METEO_BATCH_SIZE, PRESSURE_LEVELS_HPA
from models.weather import AtmosphericWeather, VerticalLevel, VerticalProfile
from services.http_client import JsonClient
from utils.time import number, utc_datetime
from utils.units import feet_to_meters, meters_to_feet

LEVEL_VARIABLES = ("temperature", "relative_humidity", "cloud_cover", "wind_speed", "wind_direction", "geopotential_height")
SURFACE_VARIABLES = ("freezing_level_height", "precipitation", "weather_code", "cape",
                     "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "surface_pressure", "wind_gusts_10m")


def vertical_interpolate(heights, values, target_m):
    """Linear interpolation between actual geopotential heights; never extrapolates."""
    pairs = sorted((h, v) for h, v in zip(heights, values) if h is not None and v is not None)
    if not pairs or target_m < pairs[0][0] or target_m > pairs[-1][0]:
        return None
    for height, value in pairs:
        if abs(target_m - height) < 1e-6:
            return value
    for (lower, low_value), (upper, high_value) in zip(pairs, pairs[1:]):
        if lower < target_m < upper:
            fraction = (target_m - lower) / (upper - lower)
            return low_value + fraction * (high_value - low_value)
    return None


def wind_vectors(direction, speed):
    if direction is None or speed is None:
        return None, None
    return -speed * math.sin(math.radians(direction)), -speed * math.cos(math.radians(direction))


def interpolate_profile(profile: VerticalProfile, altitude_ft: int) -> AtmosphericWeather:
    height = feet_to_meters(altitude_ft)
    levels = profile.levels
    heights = [level.height_m for level in levels]
    interpolate = lambda field: vertical_interpolate(heights, [getattr(level, field) for level in levels], height)
    vectors = [wind_vectors(level.wind_direction_deg, level.wind_speed_kt) for level in levels]
    u = vertical_interpolate(heights, [v[0] for v in vectors], height)
    v = vertical_interpolate(heights, [v[1] for v in vectors], height)
    speed = math.hypot(u, v) if u is not None and v is not None else None
    direction = math.degrees(math.atan2(-u, -v)) % 360 if speed is not None and speed > 1e-6 else None
    temperature, cloud = interpolate("temperature_c"), interpolate("cloud_percent")
    humidity = interpolate("humidity_percent")
    notes = ["Topo das nuvens não disponível diretamente.", "Base das nuvens na rota não disponível diretamente."]
    if temperature is None or cloud is None:
        notes.append("Perfil vertical incompleto nesta altitude; sem extrapolação ou substituição por dados da superfície.")
    if profile.terrain_m is not None and height <= profile.terrain_m:
        temperature, cloud, speed, direction = None, None, None, None
        humidity = None
        notes.append("Altitude igual ou inferior ao terreno do modelo neste ponto; verifique terreno e MEA/MORA.")
    return AtmosphericWeather(profile.latitude, profile.longitude, profile.time_utc, altitude_ft,
        temperature_c=temperature, freezing_level_ft=meters_to_feet(profile.freezing_level_m) if profile.freezing_level_m is not None else None,
        cloud_cover_percent=cloud, wind_direction_deg=direction, wind_speed_kt=speed,
        precipitation_mm=profile.precipitation_mm, relative_humidity_percent=humidity,
        weather_code=profile.weather_code, cape_j_kg=profile.cape_j_kg,
        pressure_hpa=profile.surface_pressure_hpa, gust_surface_kt=profile.gust_surface_kt,
        cloud_cover_low_percent=profile.cloud_low, cloud_cover_mid_percent=profile.cloud_mid,
        cloud_cover_high_percent=profile.cloud_high, notes=tuple(notes))


def profile_from_response(data, point) -> VerticalProfile | None:
    hourly = data.get("hourly") or {}
    if not isinstance(hourly, dict) or point.estimated_time_utc is None:
        return None
    times = [utc_datetime(t) for t in hourly.get("time", [])]
    candidates = [(abs((time - point.estimated_time_utc).total_seconds()), index, time)
                  for index, time in enumerate(times) if time is not None]
    if not candidates:
        return None
    offset, index, valid_time = min(candidates)
    if offset > 1800:
        return None

    def value(variable):
        values = hourly.get(variable) or []
        return number(values[index]) if len(values) > index else None

    pressure = value("surface_pressure")
    terrain = number(data.get("elevation"))
    levels = []
    for level in PRESSURE_LEVELS_HPA:
        height = value(f"geopotential_height_{level}hPa")
        if height is None or (terrain is not None and height < terrain) or (pressure is not None and level > pressure):
            continue
        fields = [value(f"{field}_{level}hPa") for field in LEVEL_VARIABLES[:-1]]
        levels.append(VerticalLevel(height, *fields))
    code = value("weather_code")
    return VerticalProfile(point.latitude, point.longitude, valid_time, tuple(levels),
                           value("freezing_level_height"), value("precipitation"), int(code) if code is not None else None,
                           value("cape"), pressure, value("wind_gusts_10m"), value("cloud_cover_low"),
                           value("cloud_cover_mid"), value("cloud_cover_high"), terrain)


class AtmosphericWeatherService:
    def __init__(self, client=None):
        self.client = client or JsonClient()

    def get_profiles(self, points, progress=lambda text: None):
        profiles = [None] * len(points)
        messages = []
        variables = list(SURFACE_VARIABLES) + [f"{field}_{level}hPa" for level in PRESSURE_LEVELS_HPA for field in LEVEL_VARIABLES]
        for start in range(0, len(points), OPEN_METEO_BATCH_SIZE):
            batch = points[start:start + OPEN_METEO_BATCH_SIZE]
            progress(f"Consultando atmosfera… pontos {start + 1}–{start + len(batch)} de {len(points)}")
            params = {"latitude": ",".join(f"{p.latitude:.4f}" for p in batch),
                      "longitude": ",".join(f"{p.longitude:.4f}" for p in batch),
                      "hourly": ",".join(variables), "timezone": "GMT", "wind_speed_unit": "kn",
                      "temperature_unit": "celsius", "precipitation_unit": "mm", "models": "best_match",
                      # Include the nearest hourly forecast across UTC date boundaries.
                      "start_date": (min(p.estimated_time_utc for p in batch) - timedelta(minutes=30)).strftime("%Y-%m-%d"),
                      "end_date": (max(p.estimated_time_utc for p in batch) + timedelta(minutes=30)).strftime("%Y-%m-%d")}
            result = self.client.get(OPEN_METEO_BASE_URL, params)
            if result.error:
                messages.append(f"Atmosfera indisponível nos pontos {start + 1}–{start + len(batch)}. {result.error}")
                continue
            data = result.data if isinstance(result.data, list) else [result.data]
            if len(data) != len(batch):
                messages.append("Quantidade de perfis retornados inesperada; lote não utilizado.")
                continue
            for offset, (point, response) in enumerate(zip(batch, data)):
                if isinstance(response, dict):
                    profiles[start + offset] = profile_from_response(response, point)
                if profiles[start + offset] is None:
                    messages.append(f"Previsão no horário estimado não disponível para {point.name}.")
        return profiles, messages
