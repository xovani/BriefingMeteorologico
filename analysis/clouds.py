def cloud_description(percent):
    if percent is None:
        return "cobertura na altitude não disponível"
    if percent <= 25:
        return "pouca cobertura"
    if percent <= 50:
        return "cobertura parcial"
    if percent <= 75:
        return "cobertura significativa"
    return "cobertura extensa"
