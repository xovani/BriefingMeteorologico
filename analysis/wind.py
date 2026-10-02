import math


def wind_components(heading_deg, wind_direction_deg, wind_speed_kt):
    """Positive longitudinal = headwind; lateral magnitude shown separately."""
    angle = math.radians(wind_direction_deg - heading_deg)
    return wind_speed_kt * math.cos(angle), wind_speed_kt * math.sin(angle)
