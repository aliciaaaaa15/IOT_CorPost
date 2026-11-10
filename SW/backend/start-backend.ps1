<#
.SYNOPSIS
    Starts the CorPost backend: Docker + TimescaleDB + migrations + FastAPI.

.DESCRIPTION
    It can be run from any folder: the script changes into SW/backend by itself.

    Normal mode (default):
        TimescaleDB and the API run in containers. The Alembic migrations
        are applied automatically when the backend container starts.

    -Dev mode:
        Only the database runs in Docker. FastAPI runs on the local machine with
        automatic reload when files are saved (for development). It stays in the
        foreground; Ctrl+C stops it.

    -Stop mode:
        Stops the containers (the data is kept in the volume).

.EXAMPLE
    .\start-backend.ps1               # everything in Docker
    .\start-backend.ps1 -Dev          # DB in Docker + local API with --reload
    .\start-backend.ps1 -Stop         # stop everything
    .\start-backend.ps1 -NoBrowser    # do not open http://localhost:8000/docs

.NOTES
    If Windows blocks the script (execution policy), run it like this:
    powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
#>
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

# 1) Change into the backend folder (the script's own folder), wherever it is launched from
Set-Location -Path $PSScriptRoot

$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$BaseUrl = "http://localhost:$ApiPort"

function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# Run an external program and fail if it returns an error
function Run([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Failed: $exe $($arguments -join ' ')" }
}

function Test-Docker {
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    docker info *> $null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    return $ok
}

function Wait-Until([scriptblock]$check, [int]$timeoutSec, [string]$what) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try { if (& $check) { return $true } } catch { }
        Start-Sleep -Seconds 2
    }
    Warn "Timed out waiting for: $what"
    return $false
}

# ---------------------------------------------------------------- Stop
if ($Stop) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -or -not (Test-Docker)) {
        Warn 'Docker is not running: there are no containers to stop.'
        return
    }
    Step 'Stopping containers (docker compose down)'
    Run docker @('compose', 'down')
    Ok 'Stopped. The data is kept. To delete it as well: docker compose down -v'
    return
}

# ---------------------------------------------------------------- Docker
Step 'Checking Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'The "docker" command was not found. Install Docker Desktop.'
}
if (-not (Test-Docker)) {
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $desktop) {
        Warn 'Docker is not running: starting Docker Desktop (it may take a minute)...'
        Start-Process $desktop
        if (-not (Wait-Until { Test-Docker } 180 'Docker to be ready')) {
            throw 'Docker did not start. Open Docker Desktop manually and run the script again.'
        }
    } else {
        throw 'Docker is not running. Open Docker Desktop and run the script again.'
    }
}
Ok 'Docker ready'

# ---------------------------------------------------------------- .env
if (-not (Test-Path '.env')) {
    if (Test-Path '.env.example') {
        Copy-Item '.env.example' '.env'
        Warn '.env did not exist: created from .env.example'
    } else {
        throw 'The .env file is missing (and there is no .env.example).'
    }
}

if ($Dev) {
    # ------------------------------------------------------------ Development mode
    Step 'Database in Docker (without the backend container)'
    Run docker @('compose', 'stop', 'backend')   # frees port $ApiPort for the local uvicorn
    Run docker @('compose', 'up', '-d', 'db')
    $dbId = (docker compose ps -q db)
    if (-not (Wait-Until { (docker inspect --format '{{.State.Health.Status}}' $dbId) -eq 'healthy' } 90 'the database')) {
        throw 'The database did not become ready.'
    }
    Ok 'Database ready (localhost:5432)'

    Step 'Virtual environment and dependencies'
    if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
        Run python @('-m', 'venv', '.venv')
        Ok 'Virtual environment created'
    }
    $py = '.\.venv\Scripts\python.exe'
    Run $py @('-m', 'pip', 'install', '-q', '-r', 'requirements.txt')
    Ok 'Dependencies up to date'

    Step 'Migrations (alembic upgrade head)'
    Run $py @('-m', 'alembic', 'upgrade', 'head')

    Step "FastAPI locally with automatic reload: $BaseUrl/docs   (Ctrl+C to stop)"
    if (-not $NoBrowser) { Start-Process "$BaseUrl/docs" }
    & $py -m uvicorn app.main:app --reload --port $ApiPort
    return
}

# ---------------------------------------------------------------- Normal mode (everything in Docker)
Step 'Building and starting database + backend (docker compose up -d --build)'
Run docker @('compose', 'up', '-d', '--build')

Step 'Waiting for the API to respond (includes migrations)'
$ready = Wait-Until {
    (Invoke-WebRequest -UseBasicParsing "$BaseUrl/health/db" -TimeoutSec 3).StatusCode -eq 200
} 90 'the API'
if (-not $ready) {
    Warn 'The API is not responding. Last lines of the backend log:'
    docker compose logs --tail 25 backend
    throw 'The backend did not start.'
}

Step 'Backend running'
docker compose ps
Ok "API:   $BaseUrl/health"
Ok "Docs:  $BaseUrl/docs"
Write-Host ''
Write-Host '    View logs:  docker compose logs -f backend'
Write-Host '    Stop:       .\start-backend.ps1 -Stop'
if (-not $NoBrowser) { Start-Process "$BaseUrl/docs" }
