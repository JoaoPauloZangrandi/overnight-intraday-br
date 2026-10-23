# Roda um comando da operação (ou do executor) e guarda a saída em data\operacao\log.
# Usado pelas tarefas agendadas (ver agendar_windows.ps1). Com -Abrir, mostra a saída no Bloco
# de Notas: é assim que a boleta aparece na sua tela antes de cada leilão.
param(
    [Parameter(Mandatory = $true)][string]$Uv,
    [Parameter(Mandatory = $true)][string]$Nome,
    [Parameter(Mandatory = $true)][string]$Argumentos,
    [ValidateSet("operacao", "executor")][string]$Modulo = "operacao",
    [switch]$Abrir
)
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$Log = Join-Path $Repo "data\operacao\log"
New-Item -ItemType Directory -Force $Log | Out-Null
$Arquivo = Join-Path $Log ("{0:yyyyMMdd_HHmm}_{1}.txt" -f (Get-Date), $Nome)
$env:PYTHONIOENCODING = "utf-8"
& $Uv run --extra mt5 python -m "overnight_br.$Modulo" @($Argumentos.Split(" ")) *> $Arquivo
if ($Abrir) { Start-Process notepad.exe $Arquivo }
