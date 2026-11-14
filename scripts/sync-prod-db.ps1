<#
.SYNOPSIS
    Copy the production database into the local PostgreSQL database.

.DESCRIPTION
    1. Dumps production (read-only) to a temporary file.
    2. Drops and recreates the LOCAL database, then restores the dump into it.
    3. Runs this branch's migrations against the copy (skip with -SkipMigrate).

    The target must be on this machine (localhost, 127.0.0.1 or ::1); the script
    refuses anything else, so it can never overwrite a Railway database.

    Settings come from parameters, else environment variables, else sampledb/.env:
      PROD_DATABASE_URL   production connection URL (required)
      LOCAL_PGPASSWORD    local postgres password; if missing, taken from the
                          local DATABASE_URL line in sampledb/.env, else prompted for

    The dump holds real user data. It is written to %TEMP% and always deleted.

.EXAMPLE
    .\scripts\sync-prod-db.ps1
.EXAMPLE
    .\scripts\sync-prod-db.ps1 -Force -SkipMigrate
#>
[CmdletBinding()]
param(
    [string]$ProdUrl,
    [string]$LocalHost = 'localhost',
    [int]$LocalPort = 5432,
    [string]$LocalUser = 'postgres',
    [string]$LocalDb = 'sampledb',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\18\bin',
    [switch]$SkipMigrate,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DjangoDir = Join-Path $RepoRoot 'sampledb'
$EnvFile = Join-Path $DjangoDir '.env'
$Python = Join-Path $RepoRoot 'venv\Scripts\python.exe'

function Get-Setting([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ($value) { return $value }
    if (Test-Path $EnvFile) {
        foreach ($line in Get-Content $EnvFile) {
            if ($line -match "^\s*$Name\s*=\s*(.*)$") {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    return $null
}

function Invoke-Native([string]$Exe, [string[]]$Arguments, [string]$What) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

# --- Settings and safety checks -------------------------------------------

if (-not $ProdUrl) { $ProdUrl = Get-Setting 'PROD_DATABASE_URL' }
if (-not $ProdUrl) {
    throw "No production URL. Pass -ProdUrl or set PROD_DATABASE_URL (environment or sampledb/.env)."
}
if ($ProdUrl -match '<[^>]*>') {
    throw "PROD_DATABASE_URL still contains a placeholder like '<prod password>'. Put the real password in its place."
}
try { $prodHost = ([uri]$ProdUrl).Host } catch { throw "PROD_DATABASE_URL is not a valid URL." }

$localHosts = @('localhost', '127.0.0.1', '::1')
if ($localHosts -notcontains $LocalHost) {
    throw "Refusing to restore into '$LocalHost': the target must be a local database."
}
if ($localHosts -contains $prodHost) {
    throw "PROD_DATABASE_URL points to this machine ($prodHost). Source and target look swapped."
}

foreach ($tool in 'pg_dump', 'psql', 'dropdb', 'createdb') {
    if (-not (Test-Path (Join-Path $PgBin "$tool.exe"))) {
        throw "$tool.exe not found in '$PgBin'. Pass -PgBin with your PostgreSQL bin folder."
    }
}

$localPassword = Get-Setting 'LOCAL_PGPASSWORD'
if (-not $localPassword -and (Test-Path $EnvFile)) {
    # Fall back to the password in sampledb/.env's DATABASE_URL when it points at the local server.
    # Read from the file on purpose: the OS DATABASE_URL may belong to another project.
    $line = (Select-String -Path $EnvFile -Pattern '^\s*DATABASE_URL\s*=' | Select-Object -First 1).Line
    if ($line -and (($line -split '=', 2)[1].Trim().Trim('"').Trim("'") -match '^\w+://([^:/@]+):(.*)@([^@/:]+)(:\d+)?/[^@]*$')) {
        if ($Matches[1] -eq $LocalUser -and $localHosts -contains $Matches[3]) {
            $localPassword = [uri]::UnescapeDataString($Matches[2])
        }
    }
}
if (-not $localPassword) {
    $secure = Read-Host "Password for local postgres user '$LocalUser'" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $localPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

Write-Host ""
Write-Host "Source (read only): $prodHost"
Write-Host "Target (replaced):  $LocalUser@${LocalHost}:$LocalPort/$LocalDb"
if (-not $Force) {
    $answer = Read-Host "This deletes everything in the local database '$LocalDb'. Type 'yes' to continue"
    if ($answer -ne 'yes') { Write-Host "Cancelled."; exit 1 }
}

# --- Dump, recreate, restore, migrate ---------------------------------------

$dumpFile = Join-Path $env:TEMP ("samplepedia-prod-{0}.sql" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$savedEnv = @{}
# No Discord blanking needed: migrations use historical models, which fire no signals
# (and on Windows an empty variable is deleted, so '' could not override .env anyway)
$envOverrides = @{
    PGPASSWORD = $localPassword
    DEBUG      = 'True'
}
$encodedPassword = [uri]::EscapeDataString($localPassword)
$envOverrides['DATABASE_URL'] = "postgresql://${LocalUser}:$encodedPassword@${LocalHost}:$LocalPort/$LocalDb"

try {
    # Environment changes in a script stick to the caller's session; restore them in finally
    foreach ($name in $envOverrides.Keys) {
        $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }

    Write-Host "`n[1/4] Dumping production..."
    # pg_dump gets its password from the URL; keep PGPASSWORD unset for it
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $null, 'Process')
    Invoke-Native (Join-Path $PgBin 'pg_dump.exe') @(
        '--no-owner', '--no-acl', '--file', $dumpFile, $ProdUrl
    ) 'pg_dump'
    Write-Host ("      {0:N1} MB" -f ((Get-Item $dumpFile).Length / 1MB))

    foreach ($name in $envOverrides.Keys) {
        [Environment]::SetEnvironmentVariable($name, $envOverrides[$name], 'Process')
    }
    $conn = @('--host', $LocalHost, '--port', "$LocalPort", '--username', $LocalUser)

    Write-Host "[2/4] Recreating local database '$LocalDb'..."
    Invoke-Native (Join-Path $PgBin 'dropdb.exe') ($conn + @('--if-exists', '--force', $LocalDb)) 'dropdb'
    Invoke-Native (Join-Path $PgBin 'createdb.exe') ($conn + @($LocalDb)) 'createdb'

    Write-Host "[3/4] Restoring..."
    Invoke-Native (Join-Path $PgBin 'psql.exe') ($conn + @(
        '--dbname', $LocalDb, '--quiet', '--set', 'ON_ERROR_STOP=1', '--file', $dumpFile
    )) 'psql restore'

    if ($SkipMigrate) {
        Write-Host "[4/4] Skipped migrations (-SkipMigrate)."
    } else {
        Write-Host "[4/4] Applying this branch's migrations..."
        Push-Location $DjangoDir
        try { Invoke-Native $Python @('manage.py', 'migrate', '--no-input') 'migrate' }
        finally { Pop-Location }
    }
}
finally {
    if (Test-Path $dumpFile) { Remove-Item $dumpFile -Force }
    foreach ($name in $savedEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnv[$name], 'Process')
    }
}

Write-Host "`nDone. To run the server on the copy, from sampledb/:"
Write-Host '  $env:DATABASE_URL = "postgresql://' -NoNewline
Write-Host "${LocalUser}:<url-encoded password>@${LocalHost}:$LocalPort/$LocalDb`""
Write-Host '  $env:DEBUG = "True"; ..\venv\Scripts\python.exe manage.py runserver'
