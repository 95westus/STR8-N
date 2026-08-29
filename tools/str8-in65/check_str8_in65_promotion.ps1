param(
    [string]$CanonicalTopPath = 'BUILD/v1.28/bin/str8n-v1.28-bank3-f000-ffff.bin',
    [string]$AcceptedTopPath = 'BUILD/v1.28/bin/str8n-v1.28-str8-in65-bank3-f000-ffff.bin',
    [string]$MigrationTopPath = 'BUILD/v1.28/bin/str8n-v1.28-str8-in65-wdcmonv2-bank3-f000-ffff.bin'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($path in @($CanonicalTopPath, $AcceptedTopPath, $MigrationTopPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Promotion input missing: $path"
    }
}

[byte[]]$canonical = [System.IO.File]::ReadAllBytes($CanonicalTopPath)
[byte[]]$accepted = [System.IO.File]::ReadAllBytes($AcceptedTopPath)
[byte[]]$migration = [System.IO.File]::ReadAllBytes($MigrationTopPath)
foreach ($item in @(
        @{ Name = 'canonical'; Bytes = $canonical },
        @{ Name = 'accepted'; Bytes = $accepted },
        @{ Name = 'migration'; Bytes = $migration })) {
    if ($item.Bytes.Length -ne 0x1000) {
        throw "$($item.Name) top is $($item.Bytes.Length) bytes; expected 4096"
    }
}

for ($offset = 0; $offset -lt 0x1000; $offset++) {
    if ($canonical[$offset] -ne $accepted[$offset]) {
        throw ('Canonical top differs from the accepted resident/configuration at ${0:X3}' -f $offset)
    }
}

$migrationDifferences = @()
for ($offset = 0; $offset -lt 0x1000; $offset++) {
    if ($canonical[$offset] -ne $migration[$offset]) { $migrationDifferences += $offset }
}
$allowedMigrationOffsets = @(0x0FB0..0x0FBF) + @(0x0FF0, 0x0FF1)
foreach ($offset in $migrationDifferences) {
    if ($offset -notin $allowedMigrationOffsets) {
        throw ('Migration top differs at unexpected offset ${0:X3}' -f $offset)
    }
}
if ($canonical[0x0FF0] -ne 0x1E -or $canonical[0x0FF1] -ne 0x1F) {
    throw 'Canonical v1.28 must publish WORK=B1:E and top backup=B1:F'
}
if ($migration[0x0FF0] -ne 0xFF -or $migration[0x0FF1] -ne 0xFF) {
    throw 'WDC migration candidate must leave WORK and top-backup roles unassigned'
}
[byte[]]$wdcDirectory0 = @(
    0xFF, 0xFF, 0xFF, 0xFF,
    [byte][char]'W', [byte][char]'D', [byte][char]'C', [byte][char]'M', [byte][char]'2',
    0xFE, 0xFF, 0xFF, 0xFC, 0xFF, 0xFF, 0xFF
)
for ($i = 0; $i -lt $wdcDirectory0.Length; $i++) {
    if ($migration[0x0FB0 + $i] -ne $wdcDirectory0[$i]) {
        throw ('WDC migration candidate D0 mismatch at ${0:X3}' -f (0x0FB0 + $i))
    }
}

Write-Host 'STR8-iN/65 PROMOTION = PASS'
Write-Host ('CANONICAL SHA256      = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $CanonicalTopPath).Hash)
Write-Host ('ACCEPTED SHA256       = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $AcceptedTopPath).Hash)
Write-Host ('MIGRATION SHA256      = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $MigrationTopPath).Hash)
Write-Host 'POLICY DIFFERENCE      = D0 WDCM2 COMPLETE + roles $FFF0/$FFF1 unassigned'
