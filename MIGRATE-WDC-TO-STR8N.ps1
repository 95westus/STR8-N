param([string]$Port, [switch]$ValidateOnly, [switch]$BackupOnly)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'beta4_migration.py'
if (-not (Test-Path -LiteralPath $launcher)) { $launcher = Join-Path $PSScriptRoot 'tools/beta4_migration.py' }
$arguments = @($launcher, '--kind', 'wdc')
if ($Port) { $arguments += @('--port', $Port) }
if ($ValidateOnly) { $arguments += '--validate-only' }
if ($BackupOnly) { $arguments += '--backup-only' }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Beta4 migrator failed. Retain the backup and inspect the log.' }
