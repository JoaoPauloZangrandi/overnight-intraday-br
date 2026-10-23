# Agenda a rotina diária no Agendador de Tarefas do Windows (segunda a sexta).
#
# Sempre:
#   08h00  atualiza os dados (arquivo diário do COTAHIST do pregão anterior)
#   08h10  escolha do mês (no último pregão do mês vale como decisão oficial)
#   08h15  atualiza o teste em papel
#
# Com -Executor (o executor manda as ordens sozinho; configuração em data\operacao\config.toml):
#   09h46        abertura   vende a noite e vende a descoberto o dia, no leilão de abertura
#   10h20        conferir   vende no contínuo o que sobrou da noite e cancela o dia não executado
#   16h30/17h30  cobrir     recompra o vendido do dia antes da zeragem da corretora
#   16h56/17h56  call       compra a noite no call de fechamento
#   17h15/18h15  fim        confere e manda o resumo para o celular
# As etapas da tarde são agendadas nos dois horários: o executor sabe se a B3 está no horário de
# verão americano e ignora a que estiver fora da janela.
#
# Sem -Executor (você manda as ordens): a boleta de cada leilão abre no Bloco de Notas às 09h30
# e às 16h40.
#
# Uso (PowerShell, na pasta do repositório):
#   powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 100000 -Executor
#   powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 100000
# Para remover tudo:
#   Get-ScheduledTask 'OvernightBR*' | Unregister-ScheduledTask -Confirm:$false
param(
    [Parameter(Mandatory = $true)][double]$Capital,
    [ValidateSet("so_noite", "noite_e_dia")][string]$Versao = "so_noite",
    [string]$InicioPapel = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$Executor
)
$Repo = Split-Path -Parent $PSScriptRoot
$Rodar = Join-Path $PSScriptRoot "rodar.ps1"
$Uv = (Get-Command uv -ErrorAction Stop).Source
$Dias = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
$Cap = $Capital.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$Tarefas = @(
    @{ Nome = "1-dados"; Hora = "08:00"; Args = "atualizar" },
    @{ Nome = "2-escolha"; Hora = "08:10"; Args = "escolha" },
    @{ Nome = "3-papel"; Hora = "08:15"; Args = "papel --inicio $InicioPapel" }
)
if ($Executor) {
    $Tarefas += @(
        @{ Nome = "4-abertura"; Hora = "09:46"; Args = "abertura"; Modulo = "executor" },
        @{ Nome = "5-conferir"; Hora = "10:20"; Args = "conferir"; Modulo = "executor" },
        @{ Nome = "6-cobrir-verao"; Hora = "16:30"; Args = "cobrir"; Modulo = "executor" },
        @{ Nome = "6-cobrir-inverno"; Hora = "17:30"; Args = "cobrir"; Modulo = "executor" },
        @{ Nome = "7-call-verao"; Hora = "16:56"; Args = "call"; Modulo = "executor" },
        @{ Nome = "7-call-inverno"; Hora = "17:56"; Args = "call"; Modulo = "executor" },
        @{ Nome = "8-fim-verao"; Hora = "17:15"; Args = "fim"; Modulo = "executor" },
        @{ Nome = "8-fim-inverno"; Hora = "18:15"; Args = "fim"; Modulo = "executor" }
    )
} else {
    $Tarefas += @(
        @{ Nome = "4-boleta-abertura"; Hora = "09:30"; Abrir = $true
           Args = "boleta --leilao abertura --capital $Cap --versao $Versao" },
        @{ Nome = "5-boleta-fechamento"; Hora = "16:40"; Abrir = $true
           Args = "boleta --leilao fechamento --capital $Cap --versao $Versao" }
    )
}
foreach ($t in $Tarefas) {
    $modulo = if ($t.Modulo) { $t.Modulo } else { "operacao" }
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$Rodar`" -Uv `"$Uv`" -Nome $($t.Nome) " +
           "-Modulo $modulo -Argumentos `"$($t.Args)`""
    if ($t.Abrir) { $arg += " -Abrir" }
    $acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg -WorkingDirectory $Repo
    $gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dias -At $t.Hora
    # sem bateria nem rede, o Windows não pode adiar a tarefa: ela roda ou avisa no registro
    $opcoes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable:$false -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
    Register-ScheduledTask -TaskName "OvernightBR $($t.Nome)" -Action $acao -Trigger $gatilho `
        -Settings $opcoes -Force | Out-Null
    Write-Host "agendada: OvernightBR $($t.Nome) às $($t.Hora)"
}
