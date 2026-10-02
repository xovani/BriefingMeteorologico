from datetime import datetime, timezone
from pathlib import Path

from analysis.clouds import cloud_description
from analysis.recommendation import favorable_altitudes
from config import EDUCATIONAL_NOTICE
from models.weather import RiskLevel


def value(number, unit='', digits=0):
    return 'não disponível' if number is None else f'{number:.{digits}f}{unit}'


def ft(number):
    return 'não disponível' if number is None else f'{number:,.0f} ft'.replace(',', '.')


def utc(time):
    return time.strftime('%d/%m/%Y %H:%M UTC') if time else 'não disponível'


def ceiling(summary):
    if summary is None:
        return None
    heights = [c.base_ft_agl for c in summary.clouds if c.cover in ('BKN', 'OVC') and c.base_ft_agl is not None]
    if summary.vertical_visibility_ft is not None:
        heights.append(summary.vertical_visibility_ft)
    return min(heights) if heights else None


def conditions_text(summary):
    if summary is None:
        return ['Condições não disponíveis.']
    direction = 'variável' if summary.wind_direction == 'VRB' else value(summary.wind_direction, '°')
    wind = f'Vento: {direction} / {value(summary.wind_speed_kt, " kt")}'
    if summary.gust_kt is not None:
        wind += f'; rajadas {summary.gust_kt:g} kt'
    visibility = value(summary.visibility_km, ' km', 1) + (' ou mais' if summary.visibility_at_least else '')
    layers = [f'{c.cover}: {ft(c.base_ft_agl)} acima do aeroporto' + (f' ({c.cloud_type})' if c.cloud_type else '') for c in summary.clouds]
    if not layers and 'CAVOK' in summary.raw:
        layers.append('CAVOK: sem nuvens significativas baixas reportadas; não informa topo')
    elif not layers and 'NCD' in summary.raw:
        layers.append('NCD: sensor não detectou nuvens; isso não garante céu limpo em toda a altitude')
    translations = [('FZRA', 'chuva congelante'), ('FZDZ', 'garoa congelante'), ('TS', 'trovoada'),
                    ('RA', 'chuva'), ('SN', 'neve'), ('DZ', 'garoa'), ('FG', 'nevoeiro'), ('BR', 'névoa')]
    phenomena = [label for code, label in translations if code in summary.phenomena]
    if any(c.cloud_type == 'CB' for c in summary.clouds):
        phenomena.append('cumulonimbus (CB)')
    return [wind, 'Visibilidade: ' + visibility, 'Camadas: ' + ('; '.join(layers) or 'não disponíveis'),
            'Teto: ' + (ft(ceiling(summary)) + ' acima do aeroporto' if ceiling(summary) is not None else 'não determinado nos dados disponíveis'),
            'Fenômenos: ' + (', '.join(phenomena) + f' [{summary.phenomena}]' if phenomena else (summary.phenomena or 'nenhum código significativo informado'))]


def taf_text(at):
    if at is None:
        return ['Grupo relevante não determinado.']
    lines = [at.note]
    if at.prevailing:
        lines += ['Condição predominante:', *conditions_text(at.prevailing)]
    for group in at.alternatives:
        probability = f'{group.probability}%' if group.probability else ''
        end = group.transition_end_utc if group.change == 'BECMG' and group.transition_end_utc else group.end_utc
        lines += [f'Possibilidade {group.change} {probability}: {utc(group.start_utc)} até {utc(end)}', *conditions_text(group.conditions)]
    return lines


def arrival_trend(current, at):
    if not current or not at or not at.prevailing:
        return 'Comparação com o METAR não determinada: dados ou grupo de chegada indisponíveis.'
    worsens = []
    for forecast in [at.prevailing, *(g.conditions for g in at.alternatives)]:
        if current.visibility_km is not None and forecast.visibility_km is not None and forecast.visibility_km < current.visibility_km - 1:
            worsens.append('redução de visibilidade')
        if ceiling(current) is not None and ceiling(forecast) is not None and ceiling(forecast) < ceiling(current):
            worsens.append('teto mais baixo')
        if any(code in forecast.phenomena for code in ('TS', 'FZRA', 'FZDZ')) or any(c.cloud_type == 'CB' for c in forecast.clouds):
            worsens.append('fenômenos perigosos na previsão')
        if forecast.gust_kt is not None and forecast.gust_kt > (current.gust_kt or current.wind_speed_kt or 0) + 5:
            worsens.append('rajadas mais fortes')
    return 'Possível piora na chegada: ' + ', '.join(dict.fromkeys(worsens)) + '.' if worsens else 'Não foi identificada piora nos indicadores comparáveis; isso não garante condições favoráveis.'


def airport_text(airport, at):
    lines = ['DADO OFICIAL — METAR', airport.metar_raw or f'METAR não disponível para {airport.icao}.']
    if airport.metar:
        metar = airport.metar
        lines += ['Observação: ' + utc(metar.observed_utc), *conditions_text(metar),
                  f'Temperatura: {value(metar.temperature_c, "°C", 1)} | Ponto de orvalho: {value(metar.dewpoint_c, "°C", 1)}',
                  'QNH: ' + value(metar.qnh_hpa, ' hPa', 1)]
        if metar.observed_utc and (datetime.now(timezone.utc) - metar.observed_utc).total_seconds() > 7200:
            lines.append('Observação com mais de duas horas: pode não representar o tempo atual.')
    lines += ['', 'DADO OFICIAL — TAF', airport.taf_raw or f'TAF não disponível para {airport.icao}.']
    if airport.taf:
        lines.append(f'Validade: {utc(airport.taf.start_utc)} até {utc(airport.taf.end_utc)}')
    return lines + ['Previsão relevante no horário estimado:', *taf_text(at), *airport.messages]


def generate_report(result):
    plan = result.plan
    planned = next((a for a in result.altitudes if a.altitude_ft == plan.cruise_altitude_ft), None)
    lines = ['BRIEFING METEOROLÓGICO', '=' * 65, 'ALTITUDE INFORMADA: ' + ft(plan.cruise_altitude_ft),
             'AVALIAÇÃO: ' + (planned.risk.level.label if planned and planned.risk.available else 'AMARELO — ATENÇÃO / DADOS INSUFICIENTES'),
             'Principal motivo: ' + (planned.risk.reason if planned else 'Dados insuficientes.'),
             'Confiança da avaliação derivada: ' + (planned.risk.confidence if planned else 'BAIXA'), '',
             'Rota informada: ' + plan.route.raw,
             'Rota geográfica analisada: ' + (' → '.join(p.name for p in result.route_points if ' / P' not in p.name) or 'não resolvida'),
             f'Aeronave: {plan.aircraft.name} / ' + ('FIKI / EQUIPADA' if plan.aircraft.fiki else 'NÃO-FIKI'),
             'Saída: ' + utc(plan.departure_utc), 'Chegada estimada: ' + utc(result.eta_utc),
             f'Velocidade usada na ETA: {plan.aircraft.cruise_speed:g} KTAS', '',
             'DADO OFICIAL: METAR, TAF e SIGMET publicados e distribuídos pelo AWC.',
             'DADO DE MODELO: Open-Meteo, previsão horária aproximada na posição e altitude.',
             'Dados meteorológicos: https://open-meteo.com/ — CC BY 4.0: https://creativecommons.org/licenses/by/4.0/',
             'Dados processados: interpolação vertical e avaliações derivadas realizadas pelo programa.',
             'INFERÊNCIA DO PROGRAMA: avaliação heurística de riscos; não é previsão oficial de gelo.']
    if not result.route_complete:
        lines.append('ATENÇÃO: geometria parcial/aproximada; trechos não resolvidos não foram verificados.')
    if not result.sigmet_available:
        lines.append('ATENÇÃO: cobertura de SIGMETs não determinada para todo o voo.')
    if planned:
        weather = [p.weather for p in planned.points if p.weather]
        freezes = [w.freezing_level_ft for w in weather if w.freezing_level_ft is not None]
        temps = [w.temperature_c for w in weather if w.temperature_c is not None]
        lines += [f'Cobertura de temperatura/nuvens: {planned.coverage_percent:.0f}% dos pontos analisados',
                  'Freezing level mínimo/máximo: ' + (f'{ft(min(freezes))} / {ft(max(freezes))}' if freezes else 'não disponível'),
                  'Temperatura prevista no cruzeiro: ' + (f'{min(temps):+.1f}°C a {max(temps):+.1f}°C' if temps else 'não disponível')]
    for label, icao, at in [('ORIGEM', plan.route.origin, result.departure_taf), ('DESTINO', plan.route.destination, result.arrival_taf)]:
        lines += ['', '=' * 65, f'{label} — {icao}', '=' * 65]
        airport = result.airports.get(icao)
        if airport:
            lines += airport_text(airport, at)
            if label == 'DESTINO':
                lines.append(arrival_trend(airport.metar, at))
        else:
            lines.append('Dados do aeroporto não disponíveis.')
    lines += ['', '=' * 65, 'ROTA — DADO DE MODELO E INFERÊNCIAS', '=' * 65,
              'Modelo na hora mais próxima da ETA (diferença máxima de 30 minutos).',
              'Cobertura percentual na altitude não equivale a FEW/SCT/BKN/OVC.',
              'Topo das nuvens não disponível diretamente. Base modelada não disponível diretamente.',
              'Precipitação, rajadas e pressão abaixo são da superfície; não indicam essas condições em cruzeiro.']
    if planned:
        for sample in planned.points:
            point, w = sample.point, sample.weather
            lines += ['', f'{point.name} | {point.cumulative_distance_nm:.0f} NM | ETA {utc(point.estimated_time_utc)}',
                      f'Posição: {point.latitude:.4f}, {point.longitude:.4f}']
            if w:
                lines += [f'Modelo válido: {utc(w.valid_time_utc)} | Temperatura: {value(w.temperature_c, "°C", 1)}',
                          'Freezing level: ' + ft(w.freezing_level_ft),
                          f'Nuvens na altitude: {value(w.cloud_cover_percent, "%")} — {cloud_description(w.cloud_cover_percent)}',
                          f'Umidade na altitude: {value(w.relative_humidity_percent, "%")}',
                          f'Vento em altitude: {value(w.wind_direction_deg, "°")} / {value(w.wind_speed_kt, " kt")}',
                          f'Superfície: precipitação {value(w.precipitation_mm, " mm/h", 1)}; rajadas {value(w.gust_surface_kt, " kt")}; pressão {value(w.pressure_hpa, " hPa")}']
                if sample.headwind_kt is not None:
                    kind = 'proa' if sample.headwind_kt >= 0 else 'cauda'
                    lines.append(f'Componente aproximada: {abs(sample.headwind_kt):.0f} kt de {kind}; transversal {abs(sample.crosswind_kt):.0f} kt; rumo verdadeiro {sample.heading_deg:.0f}°')
                lines += [note for note in w.notes if 'Perfil' in note or 'terreno' in note]
            else:
                lines.append('Atmosfera não disponível neste ponto.')
            lines += [f'GELO: {sample.icing.level.label} — {sample.icing.reason} Confiança: {sample.icing.confidence}',
                      f'CONVECÇÃO: {sample.convection.level.label} — {sample.convection.reason}', sample.turbulence.reason]
    lines += ['', '=' * 65, 'SIGMET — DADO OFICIAL', '=' * 65]
    if result.sigmets:
        for match in result.sigmets:
            s = match.sigmet
            lines += [f'SIGMET {s.identifier} — {s.hazard}', 'Próximo do corredor nos horários estimados; interseção exata não garantida.',
                      f'Base/topo: {ft(s.base_ft)} / {ft(s.top_ft)}', f'Validade: {utc(s.start_utc)} até {utc(s.end_utc)}',
                      s.raw or 'Mensagem bruta não disponibilizada no produto retornado.']
    else:
        lines.append('Nenhum SIGMET relevante identificado nos dados e horários consultados; ausência de alerta não exclui perigo.' if result.sigmet_available else 'SIGMETs: cobertura não determinada; dados insuficientes para afirmar ausência de alertas.')
    lines += ['', '=' * 65, 'ALTITUDES COMPARADAS — MODELO / INFERÊNCIA', '=' * 65,
              'ALTITUDE | TEMP (faixa) | NUVENS (máx.) | GELO (pior) | VENTO (máx.) | AVALIAÇÃO | DADOS']
    for altitude in result.altitudes:
        weather = [p.weather for p in altitude.points if p.weather]
        temps = [w.temperature_c for w in weather if w.temperature_c is not None]
        clouds = [w.cloud_cover_percent for w in weather if w.cloud_cover_percent is not None]
        winds = [w.wind_speed_kt for w in weather if w.wind_speed_kt is not None]
        icing = max((p.icing.level for p in altitude.points), default=RiskLevel.ATTENTION)
        temp = f'{min(temps):+.1f} a {max(temps):+.1f}°C' if temps else 'não disponível'
        lines.append(f'{ft(altitude.altitude_ft)} | {temp} | {value(max(clouds) if clouds else None, "%")} | {icing.label} | {value(max(winds) if winds else None, " kt")} | {altitude.risk.level.label} | {altitude.coverage_percent:.0f}%')
    lines += ['', 'CONCLUSÃO', 'A avaliação considera apenas os dados meteorológicos disponíveis.']
    if planned:
        lines += [f'Sua altitude planejada de {ft(plan.cruise_altitude_ft)}: {planned.risk.level.label}.', planned.risk.reason]
    favorable = favorable_altitudes(result.altitudes, result.route_complete, result.sigmet_available)
    if favorable:
        lines.append('Altitudes meteorologicamente mais favoráveis entre as analisadas: ' + ', '.join(ft(a) for a in favorable) + '.')
    else:
        lines.append('Não foi possível destacar uma altitude mais favorável com confiança: riscos altos ou dados/rota/alertas incompletos.')
    lines += ['A comparação não constitui seleção de altitude para voar. Dados específicos de turbulência podem estar ausentes.',
              'FIKI não protege contra toda condição de gelo; respeite severidade, duração e limitações da aeronave.',
              'Verifique terreno, MEA/MORA, espaço aéreo, regras IFR/VFR, oxigênio, performance, combustível e limitações da aeronave.',
              '', 'LIMITAÇÕES E DADOS AUSENTES', *dict.fromkeys(result.messages), '', EDUCATIONAL_NOTICE]
    return '\n'.join(lines)


def save_report(report: str, path: Path) -> None:
    content = f'# Briefing meteorológico\n\n```text\n{report}\n```\n' if path.suffix.lower() == '.md' else report
    path.write_text(content, encoding='utf-8')
