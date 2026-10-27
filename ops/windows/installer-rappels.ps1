# Démon des rappels (src/cron_daemon.py) à l'ouverture de la session Windows.
#   powershell -ExecutionPolicy Bypass -File ops\windows\installer-rappels.ps1            installe et démarre
#   powershell -ExecutionPolicy Bypass -File ops\windows\installer-rappels.ps1 -Retirer   arrête et désinstalle
param([switch]$Retirer)
$ErrorActionPreference = 'Stop'
$Nom = 'Axon - rappels'
$Racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Venv = Join-Path $Racine '.venv'
if (-not (Test-Path $Venv)) { $Venv = Join-Path $Racine 'venv' }

if (Get-ScheduledTask -TaskName $Nom -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $Nom -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $Nom -Confirm:$false
}
if ($Retirer) { Write-Output 'Démon des rappels retiré.'; exit 0 }

# pythonw : aucune fenêtre de console ne reste ouverte.
$Action = New-ScheduledTaskAction -Execute (Join-Path $Venv 'Scripts\pythonw.exe') `
    -Argument '-m src.cron_daemon' -WorkingDirectory $Racine
$Declencheur = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Reglages = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $Nom -Action $Action -Trigger $Declencheur -Settings $Reglages `
    -Description 'Rappels d''échéances et récapitulatif d''études Axon' | Out-Null
Start-ScheduledTask -TaskName $Nom
Write-Output "Démon des rappels installé (tâche planifiée « $Nom »)."
