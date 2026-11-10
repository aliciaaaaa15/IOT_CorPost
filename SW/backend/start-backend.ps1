<#
.SYNOPSIS
    Arranca el backend de CorPost: Docker + TimescaleDB + migraciones + FastAPI.

.DESCRIPTION
    Se puede ejecutar desde cualquier carpeta: el script entra solo en SW/backend.

    Modo normal (por defecto):
        TimescaleDB y la API corren en contenedores. Las migraciones de Alembic
        se aplican solas al arrancar el contenedor del backend.

    Modo -Dev:
        Solo la base de datos corre en Docker. FastAPI corre en tu PC con
        recarga automatica al guardar cambios (para programar). Se queda en
        primer plano; con Ctrl+C se para.

    Modo -Stop:
        Para los contenedores (los datos se conservan en el volumen).

.EXAMPLE
    .\SW\start-backend.ps1               # todo en Docker
    .\SW\start-backend.ps1 -Dev          # BD en Docker + API local con --reload
    .\SW\start-backend.ps1 -Stop         # parar todo
    .\SW\start-backend.ps1 -NoBrowser    # no abrir http://localhost:8000/docs

.NOTES
    Si Windows bloquea el script (politica de ejecucion), lanzalo asi:
    powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
#>
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

# 1) Entrar en la carpeta del backend (la del propio script), sea cual sea desde donde se lance
Set-Location -Path $PSScriptRoot

$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$BaseUrl = "http://localhost:$ApiPort"

function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# Ejecuta un programa externo y falla si devuelve error
function Run([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Ha fallado: $exe $($arguments -join ' ')" }
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
    Warn "Tiempo agotado esperando: $what"
    return $false
}

# ---------------------------------------------------------------- Parar
if ($Stop) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -or -not (Test-Docker)) {
        Warn 'Docker no esta en marcha: no hay contenedores que parar.'
        return
    }
    Step 'Parando contenedores (docker compose down)'
    Run docker @('compose', 'down')
    Ok 'Parado. Los datos se conservan. Para borrarlos tambien: docker compose down -v'
    return
}

# ---------------------------------------------------------------- Docker
Step 'Comprobando Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'No encuentro el comando "docker". Instala Docker Desktop.'
}
if (-not (Test-Docker)) {
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $desktop) {
        Warn 'Docker no esta en marcha: arrancando Docker Desktop (puede tardar un minuto)...'
        Start-Process $desktop
        if (-not (Wait-Until { Test-Docker } 180 'que Docker este listo')) {
            throw 'Docker no ha arrancado. Abre Docker Desktop a mano y vuelve a lanzar el script.'
        }
    } else {
        throw 'Docker no esta en marcha. Abre Docker Desktop y vuelve a lanzar el script.'
    }
}
Ok 'Docker listo'

# ---------------------------------------------------------------- .env
if (-not (Test-Path '.env')) {
    if (Test-Path '.env.example') {
        Copy-Item '.env.example' '.env'
        Warn 'No existia .env: creado a partir de .env.example'
    } else {
        throw 'Falta el archivo .env (y no hay .env.example).'
    }
}

if ($Dev) {
    # ------------------------------------------------------------ Modo desarrollo
    Step 'Base de datos en Docker (sin el contenedor del backend)'
    Run docker @('compose', 'stop', 'backend')   # libera el puerto $ApiPort para uvicorn local
    Run docker @('compose', 'up', '-d', 'db')
    $dbId = (docker compose ps -q db)
    if (-not (Wait-Until { (docker inspect --format '{{.State.Health.Status}}' $dbId) -eq 'healthy' } 90 'la base de datos')) {
        throw 'La base de datos no ha llegado a estar lista.'
    }
    Ok 'Base de datos lista (localhost:5432)'

    Step 'Entorno virtual y dependencias'
    if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
        Run python @('-m', 'venv', '.venv')
        Ok 'Entorno virtual creado'
    }
    $py = '.\.venv\Scripts\python.exe'
    Run $py @('-m', 'pip', 'install', '-q', '-r', 'requirements.txt')
    Ok 'Dependencias al dia'

    Step 'Migraciones (alembic upgrade head)'
    Run $py @('-m', 'alembic', 'upgrade', 'head')

    Step "FastAPI en local con recarga automatica: $BaseUrl/docs   (Ctrl+C para parar)"
    if (-not $NoBrowser) { Start-Process "$BaseUrl/docs" }
    & $py -m uvicorn app.main:app --reload --port $ApiPort
    return
}

# ---------------------------------------------------------------- Modo normal (todo en Docker)
Step 'Construyendo y levantando base de datos + backend (docker compose up -d --build)'
Run docker @('compose', 'up', '-d', '--build')

Step 'Esperando a que la API responda (incluye migraciones)'
$ready = Wait-Until {
    (Invoke-WebRequest -UseBasicParsing "$BaseUrl/health/db" -TimeoutSec 3).StatusCode -eq 200
} 90 'la API'
if (-not $ready) {
    Warn 'La API no responde. Ultimas lineas del log del backend:'
    docker compose logs --tail 25 backend
    throw 'El backend no ha arrancado.'
}

Step 'Backend en marcha'
docker compose ps
Ok "API:   $BaseUrl/health"
Ok "Docs:  $BaseUrl/docs"
Write-Host ''
Write-Host '    Ver logs:  docker compose logs -f backend'
Write-Host '    Parar:     .\start-backend.ps1 -Stop'
if (-not $NoBrowser) { Start-Process "$BaseUrl/docs" }
