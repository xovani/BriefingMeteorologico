$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$checkDirectory = Join-Path $projectRoot 'manual_results\exe_isolado'
$executable = Join-Path $projectRoot 'dist\BriefingMeteorologico.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Gere o executável primeiro.' }
New-Item -ItemType Directory -Path $checkDirectory -Force | Out-Null
$isolatedExecutable = Join-Path $checkDirectory 'BriefingMeteorologico.exe'
Copy-Item -LiteralPath $executable -Destination $isolatedExecutable -Force
$diagnostic = Join-Path $checkDirectory 'verificacao.json'
# Restrict discovery of external Python packages; only the EXE is copied.
$env:PATH = Join-Path $env:SystemRoot 'System32'
$env:PYTHONPATH = ''
$env:PYTHONHOME = ''
$env:PYTHONNOUSERSITE = '1'
$env:LOCALAPPDATA = Join-Path $checkDirectory 'dados_usuario'
$testProcess = Start-Process -FilePath $isolatedExecutable -WorkingDirectory $checkDirectory -WindowStyle Hidden -PassThru -ArgumentList @('--verificar-exe', ('"' + $diagnostic + '"'))
$deadline = (Get-Date).AddSeconds(200)
while (-not $testProcess.WaitForExit(1000)) {
    if ((Get-Date) -gt $deadline) {
        $testProcess.Kill()
        throw 'Tempo limite na verificação do executável.'
    }
}
$testProcess.Refresh()
if ($testProcess.ExitCode -ne 0) { throw "Executável terminou com erro: $($testProcess.ExitCode)" }
$result = Get-Content -LiteralPath $diagnostic -Encoding UTF8 -Raw | ConvertFrom-Json
if (-not $result.ok -or -not $result.frozen) { throw 'Verificação do pacote falhou; consulte verificacao.json.' }
$result | ConvertTo-Json -Depth 6
