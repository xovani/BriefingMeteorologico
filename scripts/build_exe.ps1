$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm 'BriefingMeteorologico.spec'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o executável.' }
    Write-Host 'Executável gerado em dist\BriefingMeteorologico.exe'
} finally {
    Pop-Location
}
