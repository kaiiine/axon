#Requires -Version 5.1
<#
.SYNOPSIS
    Axon — installation sous Windows, l'équivalent de setup.sh.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1 -ConfigSeulement
#>
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingWriteHost', '',
    Justification = 'Installateur interactif : sortie colorée destinée à la console.')]
param(
    # Reconfigurer les intégrations sans rien réinstaller.
    [switch]$ConfigSeulement
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'

function Ok([string]$Texte)     { Write-Host '  ✓  ' -ForegroundColor Green -NoNewline; Write-Host $Texte }
function Info([string]$Texte)   { Write-Host '  →  ' -ForegroundColor Yellow -NoNewline; Write-Host $Texte }
function Alerte([string]$Texte) { Write-Host '  ⚠  ' -ForegroundColor DarkYellow -NoNewline; Write-Host $Texte }
function Etape([string]$Titre)  { Write-Host ''; Write-Host '━━  ' -ForegroundColor Yellow -NoNewline; Write-Host $Titre -ForegroundColor White }
function Echec([string]$Texte)  { Write-Host '  ✗  ' -ForegroundColor Red -NoNewline; Write-Host $Texte; exit 1 }
function Detail([string]$Texte) { Write-Host "  $Texte" -ForegroundColor DarkGray }

function Oui([string]$Question) {
    (Read-Host "  ? $Question [o/N]") -match '^[oOyY]'
}

function Existe([string]$Commande) {
    [bool](Get-Command $Commande -ErrorAction SilentlyContinue)
}

# Le venv du dépôt : `.venv`, ou un `venv` historique réutilisé tel quel.
function Get-DossierVenv {
    if (Test-Path '.venv') { return '.venv' }
    if (Test-Path 'venv') { return 'venv' }
    '.venv'
}

function Get-PythonVenv { Join-Path (Get-DossierVenv) 'Scripts\python.exe' }

# Le Python du système, 3.11 ou plus : le lanceur `py` d'abord, puis `python`.
function Get-PythonSysteme {
    foreach ($candidat in @(@('py', '-3'), @('python'))) {
        if (-not (Existe $candidat[0])) { continue }
        $arguments = @($candidat | Select-Object -Skip 1) + @('-c', 'import sys; print(sys.version_info >= (3, 11))')
        $recent = & $candidat[0] @arguments 2>$null
        if ($LASTEXITCODE -eq 0 -and $recent -eq 'True') { return , $candidat }
    }
    $null
}

function Invoke-PythonSysteme([string[]]$Arguments) {
    if (-not $script:PythonSysteme) { $script:PythonSysteme = Get-PythonSysteme }
    if (-not $script:PythonSysteme) {
        Echec 'Python 3.11+ introuvable : winget install --id Python.Python.3.12 -e   (puis relance)'
    }
    $tout = @($script:PythonSysteme | Select-Object -Skip 1) + $Arguments
    & $script:PythonSysteme[0] @tout
}

# Le menu des intégrations est commun avec setup.sh : src/installation.
function Invoke-Configuration([string]$Action) {
    $python = Get-PythonVenv
    if (Test-Path $python) { & $python -m src.installation.configuration $Action }
    else { Invoke-PythonSysteme @('-m', 'src.installation.configuration', $Action) }
}

function Show-Banniere {
    Write-Host ''
    @(
        '  ██████╗ ██╗  ██╗ ██████╗ ███╗  ██╗'
        ' ██╔══██╗╚██╗██╔╝██╔═══██╗████╗ ██║'
        ' ███████║ ╚███╔╝ ██║   ██║██╔██╗██║'
        ' ██╔══██║ ██╔██╗ ██║   ██║██║╚████║'
        ' ██║  ██║██╔╝ ██╗╚██████╔╝██║ ╚███║'
        ' ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚══╝'
    ) | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
    Write-Host ''
}

function Install-Systeme {
    Etape 'Prérequis système'

    Ok (Invoke-PythonSysteme @('--version'))

    if (Existe 'ollama') {
        Ok "Ollama $(ollama --version 2>$null | Select-Object -First 1)"
    } elseif ((Existe 'winget') -and (Oui 'Ollama absent — l''installer avec winget ?')) {
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) { Ok 'Ollama installé — ouvre un nouveau terminal pour l''utiliser' }
        else { Alerte 'Installation d''Ollama échouée : https://ollama.com/download' }
    } else {
        Alerte 'Ollama absent : https://ollama.com/download'
    }

    if ((Existe 'soffice') -or (Test-Path "$env:ProgramFiles\LibreOffice\program\soffice.exe")) {
        Ok 'LibreOffice (export PDF)'
    } else {
        Alerte 'LibreOffice absent — export PDF des lettres indisponible'
        Detail 'winget install --id TheDocumentFoundation.LibreOffice -e'
    }
}

function Install-Environnement {
    Etape 'Environnement virtuel Python'
    $venv = Get-DossierVenv
    if (Test-Path $venv) {
        Ok "$venv déjà présent → $(Resolve-Path $venv)"
    } else {
        Info 'Création du venv...'
        Invoke-PythonSysteme @('-m', 'venv', $venv)
        if ($LASTEXITCODE -ne 0) { Echec 'Création du venv impossible' }
        Ok "$venv créé → $(Resolve-Path $venv)"
    }
    $python = Get-PythonVenv

    Etape 'Dépendances Python'
    & $python -m pip install --upgrade pip --quiet
    & $python -m pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -ne 0) { Echec 'Installation de requirements.txt échouée — relance avec la sortie complète : pip install -r requirements.txt' }
    Ok 'requirements.txt installé'

    Write-Host ''
    & $python -m playwright install chromium
    if ($LASTEXITCODE -eq 0) { Ok 'Playwright — Chromium prêt' }
    else { Alerte 'Installation de Playwright échouée — l''agent browser sera indisponible' }

    Info 'rtk (compression des sorties shell) n''existe que sous Linux et macOS : ignoré'
}

function Install-Configuration {
    Etape 'Fichier de configuration'
    if (Test-Path '.env') {
        Ok ".env déjà présent → $(Resolve-Path '.env')"
    } else {
        Copy-Item '.env.sample' '.env'
        Ok ".env créé → $(Resolve-Path '.env')"
    }
    Invoke-Configuration 'identite'
}

function Install-ModelesOllama {
    Etape 'Modèles Ollama'
    if (-not (Existe 'ollama')) {
        Alerte 'Ollama absent — modèles ignorés. Relance le setup une fois Ollama installé.'
        return
    }
    $modeles = ollama list 2>$null | Out-String
    if ($modeles -match 'nomic-embed-text') {
        Ok 'nomic-embed-text (embedding) déjà présent'
    } else {
        Info 'Téléchargement de nomic-embed-text (~274 MB, requis)...'
        ollama pull nomic-embed-text
        if ($LASTEXITCODE -eq 0) { Ok 'nomic-embed-text prêt' } else { Alerte 'Téléchargement échoué : ollama pull nomic-embed-text' }
    }
    Write-Host ''
    if ($modeles -match 'qwen2\.5:7b') {
        Ok 'qwen2.5:7b déjà présent'
    } else {
        Detail 'Backend local optionnel — utile si tu n''as pas accès au cloud'
        if (Oui 'Télécharger qwen2.5:7b pour le backend local (~4.4 GB) ?') {
            ollama pull qwen2.5:7b
            if ($LASTEXITCODE -eq 0) { Ok 'qwen2.5:7b prêt' }
        }
    }
}

function Install-DemonRappel {
    Etape 'Démon des rappels'
    & (Join-Path $PSScriptRoot 'ops\windows\installer-rappels.ps1')
}

# L'île est un plugin (axon-overlay), installé par la marketplace depuis ce
# dépôt : sous Windows, l'app Tauri (zone de notification, Ctrl+Maj+Espace).
function Install-Ile {
    Etape 'Île (plugin axon-overlay)'
    Detail 'Demandes, rappels d''études et réponses en direct dans la barre du système.'
    if (-not (Oui 'Installer l''île (construction de plusieurs minutes) ?')) {
        Info 'Plus tard, dans Axon : /plugin'
        return
    }
    $manquants = @(@('npm', 'cargo') | Where-Object { -not (Existe $_) })
    if ($manquants) {
        Alerte "Pour la construire, il manque : $($manquants -join ', ')"
        Detail 'winget install --id OpenJS.NodeJS.LTS -e ; winget install --id Rustlang.Rustup -e'
        Detail 'Visual Studio Build Tools (C++) : winget install --id Microsoft.VisualStudio.2022.BuildTools -e'
        return
    }
    & (Get-PythonVenv) -m src.plugins install .\axon-overlay
    if ($LASTEXITCODE -ne 0) { Alerte 'Installation de l''île échouée — dans Axon : /plugin install .\axon-overlay' }
}

Show-Banniere
if ($ConfigSeulement) {
    if (-not (Test-Path '.env')) { Copy-Item '.env.sample' '.env'; Ok '.env créé depuis .env.sample' }
    Invoke-Configuration 'identite'
    Invoke-Configuration 'menu'
} else {
    Install-Systeme
    Install-Environnement
    Install-Configuration
    Install-ModelesOllama
    Install-DemonRappel
    Install-Ile
    Invoke-Configuration 'menu'
}

Write-Host ''
Invoke-Configuration 'statut'
Write-Host '  ─────────────────────────────────────' -ForegroundColor Yellow
Write-Host '  Prêt.' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Lancer Axon :' -ForegroundColor White
Write-Host "    $(Get-DossierVenv)\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host '    python -m src.ui.main' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Reconfigurer les intégrations :  ' -ForegroundColor DarkGray -NoNewline
Write-Host 'powershell -ExecutionPolicy Bypass -File setup.ps1 -ConfigSeulement' -ForegroundColor Yellow
Write-Host ''
