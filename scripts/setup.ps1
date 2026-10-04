$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repo '.env'
if (Test-Path -LiteralPath $envFile) { throw '.env already exists; it was not overwritten.' }
function New-Secret { [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant() }
$appSecret = New-Secret
$rootSecret = New-Secret
@("MARIADB_DATABASE=bmepilots", "MARIADB_USER=bmepilots", "MARIADB_PASSWORD=$appSecret", "MARIADB_ROOT_PASSWORD=$rootSecret", 'DB_PORT=3307') | Set-Content -LiteralPath $envFile -Encoding utf8
Write-Host 'Created local .env with random credentials. No secrets were printed.'
Write-Host 'Start: docker compose -f compose.yml -f compose.dev.yml up -d --wait'
