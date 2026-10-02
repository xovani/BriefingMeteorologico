# Planejamento meteorológico de voo — MSFS 2024

Aplicação desktop local em Python, com interface em português. Recebe um plano
de voo e consulta dados reais para produzir um briefing educacional. Distingue
**dado oficial** (METAR/TAF/SIGMET), **dado de modelo** (Open-Meteo) e
**inferência do programa** (avaliação heurística de riscos). Não usa dados simulados
no fluxo da aplicação. Não requer conta ou chave para as fontes implementadas.

## Requisitos e instalação no Windows

### Executável pronto (sem instalar Python)

Para usar sem Python, abra **Releases** neste repositorio e baixe
`BriefingMeteorologico-Windows-x64.zip`. Extraia o ZIP e abra
`BriefingMeteorologico.exe` com dois cliques. Ele inclui Python, Tkinter,
CustomTkinter, bibliotecas geometricas, dados de projecao e certificados HTTPS.
Preserve os avisos de licenca distribuidos no ZIP. Nao precisa copiar o `.venv`
ou instalar dependencias. A primeira abertura pode levar alguns segundos para
extrair os recursos temporarios. Internet continua necessaria.

Ao compilar localmente, o EXE fica em `dist/BriefingMeteorologico.exe`.

No EXE, logs persistem em `%LOCALAPPDATA%\BriefingMeteorologico\logs\app.log`,
sem exigir escrita ao lado do executável. Os relatórios são salvos no local escolhido.
O pacote não se destina a Windows de 32 bits, macOS ou Linux. Foi verificado neste
Windows local; não foi testado em todas as versões/configurações de Windows.

Para gerar novamente após mudanças no código, usando o ambiente de desenvolvimento:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build_exe.ps1
```

A receita `BriefingMeteorologico.spec` inclui os recursos necessários no pacote,
conforme a [documentação do PyInstaller](https://pyinstaller.org/en/stable/usage.html).
Artefatos temporários de compilação ficam em `build/` e o EXE final em `dist/`.
`scripts/check_exe.ps1` testa uma cópia do EXE em diretório isolado, com Python
removido do PATH, verifica GUI/HTTPS/geometria e salva diagnóstico e briefings em
`manual_results/exe_isolado/`. Essa verificação é manual e usa a internet.

### Executar a partir do código Python

Python 3.11 ou superior, internet para as consultas e ambiente gráfico com Tkinter.
Instale Python por https://www.python.org/downloads/windows/ e selecione a opção
para adicioná-lo ao PATH. O projeto foi validado com Python 3.13; testes unit?rios s?o offline.

Abra um terminal na pasta deste projeto. Crie um ambiente virtual se ainda não existir e instale as dependências:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

No PowerShell, a ativação também pode ser feita com `.venv\Scripts\Activate.ps1`.
Se a política bloquear a ativação, use diretamente o executável, sem mudar a política:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

As dependências são CustomTkinter, requests, pytest, Shapely e pyproj. As duas
últimas são utilizadas para verificar a proximidade entre SIGMETs e a rota em
coordenadas projetadas em metros. O aplicativo roda localmente, sem necessidade de servidor local. Este repositório
publica apenas código, documentação e rotinas de compilação; ambientes virtuais,
logs, relatórios pessoais e binários não fazem parte do histórico do código.

## Como preencher

1. Selecione **HÉLICE** ou **JATO** e **NÃO-FIKI** ou **FIKI / EQUIPADA**.
2. Informe origem e destino com códigos ICAO de quatro letras e os elementos da
   rota entre eles: `SBSP DCT SBGR`, por exemplo.
3. Informe altitude em pés acima do nível médio do mar.
4. Informe saída UTC em `AAAA-MM-DD` e `HH:MM`. Os campos iniciais mostram UTC.
5. Clique **ANALISAR VOO**. O status acompanha a consulta; a interface permanece
   disponível enquanto uma thread separada acessa a rede.
6. Leia o resumo inicial, origem/destino, pontos da rota, SIGMETs, tabela de
   altitudes e limitações. Use **SALVAR RELATÓRIO** para TXT ou Markdown UTF-8.

Também aceita `BGKK DCT NASOP UT592 NONRO DCT XRAY DCT GIRUG GIRU4M BIKF`.
DCT é instrução. UT592 é candidata a aerovia; GIRU4M, a procedimento. O parser
classifica por formato e preserva a ordem, sem validar a navegação. Pontos que
não forem encontrados são informados e a análise continua entre os pontos
resolvidos. Aerovias e SID/STAR não são expandidas. A rota resultante pode ser
parcial e não representa necessariamente a trajetória do plano no simulador.

## Como interpretar

- **VERDE — BAIXO**: os indicadores disponíveis não sugerem risco significativo;
  não é garantia de ausência de perigo.
- **AMARELO — ATENÇÃO**: há indícios de risco ou informação incompleta.
- **VERMELHO — ALTO**: combinação desfavorável de indicadores ou alerta relevante.

A classificação aparece também por escrito, sem depender da cor. A confiança
ALTA/MÉDIA/BAIXA descreve a evidência disponível, não uma probabilidade calibrada.
Dados incompletos não geram automaticamente uma avaliação verde.

O risco de gelo considera temperatura **na altitude**, cobertura de nuvens,
umidade, freezing level, precipitação e alertas. O programa fala em condições
favoráveis à formação de gelo, sem afirmar que a aeronave encontrará gelo.
FZRA/FZDZ oficiais e chuva/garoa congelante modeladas recebem atenção especial
com risco alto; o relatório distingue precipitação de superfície e cruzeiro.
A avaliação é conservadora para NÃO-FIKI. FIKI não significa proteção universal.

Convecção é avaliada separadamente. TS/CB oficiais ou trovoada modelada geram
alerta para desvio lateral; mudar altitude não é estratégia principal para
atravessar células. CAPE isolado não é classificado como tempestade. Não há
inferência de MOD/SEV TURB apenas pelo vento: sem fonte específica ou SIGMET
relevante, aparece **Turbulência: dado específico não disponível**.

A tabela compara as altitudes genéricas configuradas e inclui a altitude
informada. Reaproveita os mesmos perfis verticais. Destaca condições relativamente
mais favoráveis apenas quando a geometria, os alertas e os dados necessários
permitem comparação; não indica uma altitude para voar. Os valores na tabela
resumem máximos/faixas ao longo da rota, não representam um único ponto.

## Fontes e metodologia

- [AWC Data API](https://aviationweather.gov/data/api/) e sua
  [OpenAPI](https://aviationweather.gov/data/schema/openapi.yaml): produtos
  `metar`, `taf`, `sigmet`, `airport`, `fix` e `navaid`. Usa JSON estruturado,
  GeoJSON para SIGMET e preserva as mensagens brutas quando fornecidas.
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs): endpoint
  `https://api.open-meteo.com/v1/forecast`, modelo `best_match`, variáveis horárias
  de freezing level, temperatura, umidade, nuvens, vento e altura geopotencial
  em níveis de pressão; precipitação, código de tempo, CAPE e dados de superfície.

A documentação foi consultada antes de implementar as chamadas. A especificação
AWC consultada está em `awc_openapi_reference.yaml`. O User-Agent identifica
esta aplicação. Cache em memória tem TTL de 300 segundos, inclusive para
respostas válidas sem dados. As consultas são espaçadas; HTTP 429 ativa espera
antes de novas consultas ao serviço. Não há tentativas repetidas ilimitadas.

As coordenadas vêm do AWC. Fixes ambíguos são comparados com um corredor de
contexto entre origem/destino e a posição anterior; candidatos sem distinção
suficiente são rejeitados. A cobertura mundial de navegação do AWC não garante
que todo fix de um plano esteja disponível.

As amostras usam grande círculo, com espaçamento máximo aproximado de 50 NM,
mais os pontos resolvidos. A ETA usa distância/velocidade constante (160 KTAS
hélice, 430 KTAS jato), sem vento, subida, descida ou procedimentos. Esses valores
e os limites genéricos podem ser alterados em `config.py`/`models/aircraft.py`.

Para cada amostra, usa-se a hora de modelo mais próxima da ETA, limitada a 30
minutos de diferença. Os dados verticais são interpolados **pelas alturas
geopotenciais reais**, sem assumir altitude fixa por pressão, extrapolar ou
substituir temperatura por temperatura da superfície. Vento é interpolado por
componentes vetoriais, evitando erro entre direções 350° e 10°. Níveis abaixo do
terreno/pressão de superfície são excluídos quando essa informação existe.

Percentuais de nuvens nos níveis de pressão são dados modelados, baseados na
umidade do modelo; não equivalem a FEW/SCT/BKN/OVC nem comprovam água líquida
super-resfriada. São apresentados como pouca cobertura, parcial, significativa
ou extensa. Bases METAR/TAF estão em pés **acima do aeroporto**; altitudes de
cruzeiro e freezing level são acima do nível do mar. Não há topo ou base de
nuvens modelados inventados: aparecem como indisponíveis.

O TAF é selecionado aproximadamente no horário de saída/chegada. Se o TAF mais
recente não cobrir o horário, consulta-se o parâmetro documentado de validade.
FM substitui a condição predominante; BECMG inclui transição; TEMPO/PROB30/PROB40
são possibilidades adicionais com condições não alteradas herdadas. A comparação
com METAR aponta possível piora de visibilidade, teto, rajadas ou fenômenos.
Se a validade ou o grupo não puder ser determinado, isso aparece no briefing.

SIGMETs são verificados por validade e geometria em um corredor configurável
de 25 NM, acrescido de suporte de meia amostra para evitar lacunas entre pontos.
Essa verificação é conservadora e indica **proximidade**, não interseção exata.
Base/topo limitam a avaliação em altitude quando disponíveis. Alertas de convecção
não são considerados contornados apenas por uma altitude diferente.

## Estrutura

```text
main.py, config.py, requirements.txt, pytest.ini
models/       aeronave, plano, perfil atmosférico e resultados
services/     HTTP/cache, AWC, navegação, Open-Meteo e orquestrador
analysis/     gelo, convecção, turbulência, nuvens, vento, SIGMET e altitudes
reports/      briefing em linguagem simples e exportação
utils/        unidades, tempo, geometria e logging
gui/          formulário, worker, progresso e exibição
scripts/      verificações manuais das APIs e da GUI
tests/        testes offline com respostas mockadas
logs/         app.log com rotação
manual_results/ relatórios dos testes reais em TXT/Markdown
```

## Testes

Com o ambiente ativado:

```powershell
pytest
```

Ou `.\.venv\Scripts\python.exe -m pytest`. Os testes unitários não acessam a
internet. Cobrem parser, unidades, geometria, ETA, normalização METAR/TAF,
HTTP/timeout/cache, interpolação, SIGMET, riscos, altitudes e relatórios parciais.

Verificações manuais opcionais, que acessam a rede e não rodam no pytest:

```powershell
.\.venv\Scripts\python.exe scripts/test_live_apis.py
.\.venv\Scripts\python.exe scripts/check_gui.py
```

A primeira consulta SBSP, KJFK, BIKF e BGKK, analisa duas rotas e salva relatórios.
A segunda abre `main.py`, acompanha a responsividade durante consultas reais e
verifica exportações feitas pelo botão da GUI. A janela fecha após a verificação.

## Limitações

- Não substitui navegação oficial, despacho ou briefing oficial. Não consulta
  terreno certificado, MEA/MORA, espaço aéreo, performance ou combustível.
- Perfil genérico de hélice tem limite de 17.000 ft e de jato, 41.000 ft;
  não representa as limitações de uma aeronave específica. `AircraftProfile`
  permite acrescentar modelos específicos futuramente.
- API/modelo pode ter lacunas, divergências, resolução insuficiente ou limite
  de horizonte. Datas sem previsão não são substituídas pelo tempo atual.
- SIGMETs são os disponíveis na consulta, com cobertura limitada pelo AWC;
  não garantem os alertas que existirão no horário futuro do voo. Voos distantes
  do horário atual permanecem com cobertura de alertas não determinada.
- METAR é observação, não previsão. TAF pode não existir ou não cobrir a ETA.
- Sem PIREP/AIREP ou produto específico de turbulência integrado nesta versão.
- Não estima severidade física de gelo, água líquida, duração certificada de
  exposição, radar, localização exata de células ou todos os riscos aeronáuticos.
- Sem integração direta com MSFS; meteorologia real pode divergir do simulador.
- Consultas falhas geram mensagens e logs, sem valores meteorológicos fictícios.

**Ferramenta educacional para simulação. Não utilizar como única fonte para operações aéreas reais.**

## Publicacao e releases

O repositorio deve ser publico para distribuicao. A compilacao automatizada em
GitHub Actions roda os testes offline e gera o EXE em Windows de 64 bits. Tags
no formato `v1.0.0` publicam uma release com o ZIP, documentacao e avisos das
bibliotecas. A execucao manual do workflow gera apenas um artefato para download.
Os workflows ainda precisam ser executados no GitHub para validar o ambiente hospedado.

O uso da API gratuita Open-Meteo deve respeitar os termos do provedor, incluindo
as condicoes de uso nao comercial da camada gratuita. Veja
https://open-meteo.com/en/terms e https://open-meteo.com/en/licence.
A licenca do codigo da aplicacao nao altera os termos das fontes meteorologicas.

A licenca do projeto sera definida antes da publicacao. As dependencias mantem
suas proprias licencas, preservadas no pacote de distribuicao.
