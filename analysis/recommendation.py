from models.weather import RiskLevel


def favorable_altitudes(analyses, route_complete=True, sigmet_available=True):
    # No favourable recommendation with incomplete profiles or missing route/alert checks.
    if not route_complete or not sigmet_available:
        return []
    eligible = [a for a in analyses if a.coverage_percent == 100 and a.risk.available and a.risk.confidence != "BAIXA"]
    if not eligible:
        return []
    best = min(a.risk.level for a in eligible)
    if best == RiskLevel.HIGH:
        return []
    return [a.altitude_ft for a in eligible if a.risk.level == best]
