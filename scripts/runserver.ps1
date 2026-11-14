<#
.SYNOPSIS
    Start the Django dev server against the LOCAL database.

.DESCRIPTION
    Django reads DATABASE_URL from the OS environment only, and this machine has a
    user-level DATABASE_URL that belongs to another project. This script sets it for
    the server process from the DATABASE_URL line in sampledb/.env (the local Postgres
    that scripts/sync-prod-db.ps1 fills), percent-encoding the password.

    Use -Sqlite to run on sampledb/db.sqlite3 instead.
    Extra arguments go to runserver, e.g. a port: .\scripts\runserver.ps1 8001

.EXAMPLE
    .\scripts\runserver.ps1
.EXAMPLE
    .\scripts\runserver.ps1 -Sqlite
#>
param(
    [switch]$Sqlite,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$RunserverArgs
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DjangoDir = Join-Path $RepoRoot 'sampledb'
$EnvFile = Join-Path $DjangoDir '.env'
$Python = Join-Path $RepoRoot 'venv\Scripts\python.exe'

if ($Sqlite) {
    $url = 'sqlite:///' + ((Join-Path $DjangoDir 'db.sqlite3') -replace '\\', '/')
    $label = 'sampledb/db.sqlite3'
} else {
    $line = (Select-String -Path $EnvFile -Pattern '^\s*DATABASE_URL\s*=' | Select-Object -First 1).Line
    if (-not $line) { throw "No DATABASE_URL line in $EnvFile." }
    $raw = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
    # Greedy password match: the password may contain a raw '@'
    if ($raw -notmatch '^(\w+)://([^:/@]+):(.*)@([^@/]+)/([^@/?]+)$') {
        throw "Could not read DATABASE_URL in $EnvFile (expected scheme://user:password@host:port/db)."
    }
    $scheme, $user, $password, $hostPort, $db = $Matches[1..5]
    if ($hostPort -notmatch '^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$') {
        throw "DATABASE_URL in $EnvFile points to '$hostPort', not this machine. Refusing to start."
    }
    $encoded = [uri]::EscapeDataString([uri]::UnescapeDataString($password))
    $url = "${scheme}://${user}:$encoded@$hostPort/$db"
    $label = "local Postgres '$db' on $hostPort"
}

$saved = @{ DATABASE_URL = $env:DATABASE_URL; DEBUG = $env:DEBUG }
try {
    $env:DATABASE_URL = $url
    $env:DEBUG = 'True'
    Write-Host "Database: $label"
    Push-Location $DjangoDir
    try {
        & $Python manage.py runserver @RunserverArgs
    } finally {
        Pop-Location
    }
} finally {
    # Environment changes in a script stick to the caller's session; put them back
    $env:DATABASE_URL = $saved.DATABASE_URL
    $env:DEBUG = $saved.DEBUG
}
