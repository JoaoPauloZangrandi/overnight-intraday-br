# Agenda a rotina diária no Agendador de Tarefas do Windows (segunda a sexta).
#
#   08h00  atualiza os dados (arquivo diário do COTAHIST do pregão anterior)
#   08h10  escolha do mês (no último pregão do mês vale como decisão oficial)
#   08h15  atualiza o teste em papel
#   09h30  boleta do leilão de abertura (abre no Bloco de Notas)
#   16h40  boleta do leilão de fechamento (abre no Bloco de Notas)
#
# Em feriado as tarefas rodam, mas a boleta responde "não tem pregão". Fora do horário de
# verão americano, o leilão de fechamento passa para 17h55–18h; a boleta das 16h40 continua
# valendo e mostra o horário certo do leilão.
#
# Uso (PowerShell, na pasta do repositório):
#   powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 100000
#   powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 100000 -Versao noite_e_dia
# Para remover tudo:
#   Get-ScheduledTask 'OvernightBR*' | Unregister-ScheduledTask -Confirm:$false
param(
    [Parameter(Mandatory = $true)][double]$Capital,
    [ValidateSet("so_noite", "noite_e_dia")][string]$Versao = "so_noite",
    [string]$InicioPapel = (Get-Date -Format "yyyy-MM-dd")
)
$Repo = Split-Path -Parent $PSScriptRoot
$Rodar = Join-Path $PSScriptRoot "rodar.ps1"
$Uv = (Get-Command uv -ErrorAction Stop).Source
$Dias = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
$Cap = $Capital.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$Tarefas = @(
    @{ Nome = "1-dados"; Hora = "08:00"; Args = "atualizar"; Abrir = $false },
    @{ Nome = "2-escolha"; Hora = "08:10"; Args = "escolha"; Abrir = $false },
    @{ Nome = "3-papel"; Hora = "08:15"; Args = "papel --inicio $InicioPapel"; Abrir = $false },
    @{ Nome = "4-boleta-abertura"; Hora = "09:30"
       Args = "boleta --leilao abertura --capital $Cap --versao $Versao"; Abrir = $true },
    @{ Nome = "5-boleta-fechamento"; Hora = "16:40"
       Args = "boleta --leilao fechamento --capital $Cap --versao $Versao"; Abrir = $true }
)
foreach ($t in $Tarefas) {
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Rodar`" -Uv `"$Uv`" -Nome $($t.Nome) " +
           "-Argumentos `"$($t.Args)`""
    if ($t.Abrir) { $arg += " -Abrir" }
    $acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $Repo
    $gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dias -At $t.Hora
    Register-ScheduledTask -TaskName "OvernightBR $($t.Nome)" -Action $acao -Trigger $gatilho `
        -Force | Out-Null
    Write-Host "agendada: OvernightBR $($t.Nome) às $($t.Hora)"
}
