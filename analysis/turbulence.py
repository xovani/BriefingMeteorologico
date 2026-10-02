from models.weather import RiskLevel, WeatherRisk


def assess_turbulence(sigmets=()):
    relevant = [s for s in sigmets if "TURB" in s.hazard.upper() or "TURB" in s.raw.upper()]
    if relevant:
        severe = any("SEV" in s.raw.upper() for s in relevant)
        text = "SEVERA" if severe else "Intensidade não determinada pelo campo disponível; consultar SIGMET bruto"
        return WeatherRisk(RiskLevel.HIGH, f"Turbulência: {text}. SIGMET relevante ao horário e à altitude.", "ALTA")
    return WeatherRisk(RiskLevel.ATTENTION, "Turbulência: dado específico não disponível. Vento forte não foi convertido em MOD/SEV TURB.", "BAIXA", False)
