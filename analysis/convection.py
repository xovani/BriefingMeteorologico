from models.weather import RiskLevel, WeatherRisk

LATERAL_DEVIATION = "Planejar desvio lateral. Não utilizar mudança de altitude como estratégia principal para atravessar células convectivas."


def assess_convection(weather, phenomena="", official_convection=False):
    if official_convection or "TS" in phenomena or "CB" in phenomena:
        return WeatherRisk(RiskLevel.HIGH, "Indicação convectiva em produto oficial relevante. " + LATERAL_DEVIATION, "ALTA")
    if weather is None or weather.weather_code is None:
        return WeatherRisk(RiskLevel.ATTENTION, "Dados insuficientes para avaliar convecção neste ponto.", "BAIXA", False)
    if weather.weather_code in (95, 96, 99):
        return WeatherRisk(RiskLevel.HIGH, "O modelo indica trovoada na região do ponto; não localiza precisamente a célula. " + LATERAL_DEVIATION)
    if weather.precipitation_mm is not None and weather.precipitation_mm >= 5:
        return WeatherRisk(RiskLevel.ATTENTION, "Precipitação forte modelada; verificar células e radar. Este indicador não comprova tempestade.")
    if weather.cape_j_kg is not None and weather.cape_j_kg >= 1000:
        return WeatherRisk(RiskLevel.ATTENTION, "Energia potencial convectiva elevada no modelo; isoladamente não indica tempestade.")
    return WeatherRisk(RiskLevel.LOW, "Nenhum sinal significativo nos dados consultados; células pequenas podem não ser representadas.")
