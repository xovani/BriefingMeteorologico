from config import CLOUD_SIGNIFICANT_PERCENT
from models.weather import RiskLevel, WeatherRisk


def assess_icing(weather, fiki: bool, phenomena="", official_icing=False) -> WeatherRisk:
    if "FZRA" in phenomena or "FZDZ" in phenomena:
        return WeatherRisk(RiskLevel.HIGH, "Chuva ou garoa congelante indicada em produto oficial: risco elevado, inclusive para aeronaves FIKI.", "ALTA")
    if official_icing:
        return WeatherRisk(RiskLevel.HIGH, "SIGMET de gelo relevante ao ponto, horário e altitude; não implica gelo observado na aeronave.", "ALTA")
    if weather is not None and weather.weather_code in (56, 57, 66, 67):
        return WeatherRisk(RiskLevel.HIGH, "O modelo indica chuva ou garoa congelante na superfície deste ponto. Atenção especial na saída/chegada; não comprova esse fenômeno em cruzeiro.")
    if weather is None or weather.temperature_c is None or weather.cloud_cover_percent is None:
        return WeatherRisk(RiskLevel.ATTENTION, "Dados insuficientes para avaliar formação de gelo nesta altitude.", "BAIXA", False)
    temperature, cloud = weather.temperature_c, weather.cloud_cover_percent
    moisture = weather.relative_humidity_percent is not None and weather.relative_humidity_percent >= 85
    precipitation = weather.precipitation_mm is not None and weather.precipitation_mm > 0.2
    above_freezing = weather.freezing_level_ft is not None and weather.altitude_ft >= weather.freezing_level_ft
    # Broad conservative mixed-phase window. Does not predict liquid water or actual icing.
    if -25 <= temperature <= 0 and cloud >= CLOUD_SIGNIFICANT_PERCENT:
        stronger = (cloud >= 75 and (moisture or precipitation or above_freezing)) or not fiki
        level = RiskLevel.HIGH if stronger else RiskLevel.ATTENTION
        reason = "Temperatura abaixo ou igual a 0°C e cobertura significativa de nuvens: condições favoráveis à formação de gelo."
        if above_freezing:
            reason += " Altitude acima do nível de congelamento modelado."
        if precipitation:
            reason += " Precipitação prevista na superfície reforça a atenção; não comprova precipitação em cruzeiro."
        if not fiki:
            reason += " Avaliação conservadora para aeronave não-FIKI; esta altitude não é meteorologicamente favorável nesse trecho."
        return WeatherRisk(level, reason)
    if temperature <= 0 and (cloud >= 25 or moisture or precipitation):
        return WeatherRisk(RiskLevel.ATTENTION, "Temperatura negativa e indícios de umidade: possibilidade de gelo, com incerteza sobre água líquida super-resfriada.")
    return WeatherRisk(RiskLevel.LOW, "O modelo não indica combinação significativa de frio e nuvens neste ponto; isso não exclui gelo localizado.")
