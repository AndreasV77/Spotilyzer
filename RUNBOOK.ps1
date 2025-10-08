<# ===========================
 RUNBOOK.ps1  —  Helpers & 1-Liner
 Projekt: Music Analysis Spotify
 Nutzung:  . .\RUNBOOK.ps1   (Punkt-Sourcing!)
 Beispiel: venv312; pull -Name "Rock This" -Out .\output\rock_this.csv
=========================== #>

# --- Root & Paths ---
$script:MAS_ROOT = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$script:VENV = Join-Path $MAS_ROOT ".venv312"
$script:PY    = Join-Path $VENV "Scripts\python.exe"

function _ensure-root {
  param([switch]$Quiet)
  if (-not (Test-Path $MAS_ROOT)) { throw "MAS_ROOT not found: $MAS_ROOT" }
  if (-not (Test-Path (Join-Path $MAS_ROOT ".env"))) {
    if (-not $Quiet) { Write-Warning "Keine .env im Projekt-Root gefunden: $MAS_ROOT\.env" }
  }
}

function _ensure-venv {
  if (-not (Test-Path $PY)) {
    throw "Python in venv nicht gefunden: $PY  (venv neu anlegen: python312 -m venv .\.venv312)"
  }
}

# --- Quality-of-life ---
function venv312 {
  Set-Location $MAS_ROOT
  if (-not (Test-Path (Join-Path $VENV "Scripts\Activate.ps1"))) {
    throw "Keine venv gefunden unter $VENV  → C:\Users\tatsu\scoop\apps\python312\current\python.exe -m venv .\.venv312"
  }
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force | Out-Null
  & (Join-Path $VENV "Scripts\Activate.ps1")
  $env:PYTHONNOUSERSITE = "1"
  Write-Host "venv312 aktiv: $VENV" -ForegroundColor Green
}

function use314 {
  # Starte bewusst globales Scoop-Python 3.14 ohne venv
  $py314 = "C:\Users\tatsu\scoop\apps\python\current\python.exe"
  if (-not (Test-Path $py314)) { throw "Globales Python 3.14 nicht gefunden unter $py314" }
  & $py314 @Args
}

# --- Session-Hygiene ---
function fix-proxy {
  Get-ChildItem Env: | ? { $_.Name -match 'proxy|REQUESTS|CURL|SSL' } | % { "Unset $($_.Name)" }
  Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue
  $env:NO_PROXY = "127.0.0.1,localhost,.spotify.com"
  Write-Host "Proxy-Variablen bereinigt (NO_PROXY=$($env:NO_PROXY))" -ForegroundColor Yellow
}

# --- Token & Netzwerk-Checks ---
function tokentest {
  _ensure-root; _ensure-venv
  & $PY -c 'from dotenv import load_dotenv; load_dotenv(r".\.env"); import spotipy; from spotipy.oauth2 import SpotifyClientCredentials as CC; sp=spotipy.Spotify(auth_manager=CC()); print((sp.auth_manager.get_access_token(as_dict=False) or "")[:40]+"...")'
}

function curltest {
  _ensure-root
  $cid = (Select-String -Path (Join-Path $MAS_ROOT ".env") -Pattern '^SPOTIPY_CLIENT_ID=(.*)$').Matches[0].Groups[1].Value
  $sec = (Select-String -Path (Join-Path $MAS_ROOT ".env") -Pattern '^SPOTIPY_CLIENT_SECRET=(.*)$').Matches[0].Groups[1].Value
  if (-not $cid -or -not $sec) { throw "Client ID/Secret nicht in .env gefunden." }
  $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$cid`:$sec"))
  $tok = curl.exe -s -X POST "https://accounts.spotify.com/api/token" `
          -H "Authorization: Basic $b64" -H "Content-Type: application/x-www-form-urlencoded" `
          --data "grant_type=client_credentials" | ConvertFrom-Json
  if (-not $tok.access_token) { throw "Token konnte nicht geholt werden." }
  $testId = "11dFghVXANMlKmJXsNCbNl"
  $resp = curl.exe -s "https://api.spotify.com/v1/audio-features?ids=$testId" `
          -H "Authorization: Bearer $($tok.access_token)" | ConvertFrom-Json
  $resp
}

# --- Hauptläufe: Pull / Local / Refs / Score ---
function pull {
  <#
    .SYNOPSIS  Playlist → CSV (Client Credentials)
    .PARAMETER Name     Playlist-Name (Owner=Spotify bevorzugt)
    .PARAMETER Id       Alternativ: Playlist-ID/URL/URI
    .PARAMETER Market   DE/US/GB (wirkt auf playlist_items, nicht auf audio-features)
    .PARAMETER Out      Ziel-CSV (Default: .\output\playlist_features.csv)
  #>
  param(
    [string]$Name,
    [string]$Id,
    [ValidateSet('DE','US','GB')] [string]$Market,
    [string]$Out = ".\output\playlist_features.csv"
  )
  _ensure-root; _ensure-venv
  $args = @()
  if ($Id)   { $args += @("--playlist-id", $Id) }
  if ($Name) { $args += @("--playlist-name", $Name) }
  if ($Market) { $args += @("--market", $Market) }
  $args += @("--out", $Out)
  if (-not (Test-Path (Split-Path $Out))) { New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null }
  & $PY ".\example_playlist_pull.py" @args
}

function pullU {
  param(
    [string]$Name,
    [string]$Id,
    [ValidateSet('DE','US','GB')] [string]$Market,
    [string]$Out = ".\output\playlist_features_user.csv"
  )
  _ensure-root; _ensure-venv
  $args = @()
  if ($Id)   { $args += @("--playlist-id", $Id) }
  if ($Name) { $args += @("--playlist-name", $Name) }
  if ($Market) { $args += @("--market", $Market) }
  $args += @("-U", "--out", $Out)
  if (-not (Test-Path (Split-Path $Out))) { New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null }
  & $PY ".\example_playlist_pull.py" @args
}

function localfeat {
  <#
    .SYNOPSIS  Lokale MIR-Features (librosa/pyloudnorm)
    .PARAMETER InDir     Ordner mit Audiodateien
    .PARAMETER Out       Ziel-CSV (Default: .\output\local_features.csv)
  #>
  param(
    [string]$InDir = ".\local_audio",
    [string]$Out = ".\output\local_features.csv"
  )
  _ensure-root; _ensure-venv
  if (-not (Test-Path (Split-Path $Out))) { New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null }
  & $PY ".\local_audio_features.py" --in $InDir --out $Out
}

function refs {
  <#
    .SYNOPSIS  Genre-Referenzen via Recommendations API (Client Credentials)
    .PARAMETER Markets   Liste z. B. DE,US,GB
    .PARAMETER Genres    Liste z. B. pop,rock,metal,techno,house
    .PARAMETER OutDir    Zielordner (Default: .\output\refdata)
  #>
  param(
    [string[]]$Markets = @('DE','US','GB'),
    [string[]]$Genres  = @('pop','rock','metal','techno','house'),
    [string]$OutDir = ".\output\refdata"
  )
  _ensure-root; _ensure-venv
  if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force $OutDir | Out-Null }
  & $PY ".\build_genre_ref_stats.py" --markets @($Markets) --genres @($Genres) --outdir $OutDir
}

function score {
  <#
    .SYNOPSIS  Scoring / Ranking gegen Referenz-Stats
    .PARAMETER LocalCsv   lokale Features (Default: .\output\local_features.csv)
    .PARAMETER StatsCsv   Referenz-Stats (z. B. .\output\refdata\genre_DE_stats.csv)
    .PARAMETER Out        Ziel-CSV (Default: .\output\ranking.csv)
  #>
  param(
    [string]$LocalCsv = ".\output\local_features.csv",
    [Parameter(Mandatory=$true)][string]$StatsCsv,
    [string]$Out = ".\output\ranking.csv"
  )
  _ensure-root; _ensure-venv
  if (-not (Test-Path (Split-Path $Out))) { New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null }
  & $PY ".\score_rank.py" --local $LocalCsv --stats $StatsCsv --out $Out
}

# --- Convenience: Shortcuts ---
Set-Alias p  pull
Set-Alias pu pullU
Set-Alias lf localfeat
Set-Alias r  refs
Set-Alias s  score

Write-Host "RUNBOOK geladen. Verfügbar: venv312, pull/p, pullU/pu, localfeat/lf, refs/r, score/s, tokentest, curltest, fix-proxy." -ForegroundColor Cyan
Write-Host "Root: $MAS_ROOT" -ForegroundColor DarkGray