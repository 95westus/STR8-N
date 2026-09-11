param(
    [string]$CanonicalTopPath = 'BUILD/v1.33/bin/str8n-v1.33-bank3-f000-ffff.bin',
    [string]$AcceptedTopPath = 'BUILD/v1.33/bin/str8n-v1.33-str8-in65-bank3-f000-ffff.bin',
    [string]$MigrationTopPath = 'BUILD/v1.33/bin/str8n-v1.33-str8-in65-wdcmonv2-bank3-f000-ffff.bin'
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

for ($offset = 0; $offset -lt 0x1000; $offset++) {
    if ($canonical[$offset] -ne $migration[$offset]) {
        throw ('External migration BIN differs from canonical top at ${0:X3}' -f $offset)
    }
}
if ($canonical[0x0FF0] -ne 0x1E -or $canonical[0x0FF1] -ne 0x1F) {
    throw 'Canonical v1.33 must publish WORK=B1:E and top backup=B1:F'
}
for ($offset = 0x0FB0; $offset -le 0x0FEF; $offset++) {
    if ($migration[$offset] -ne 0xFF) {
        throw ('Canonical v1.33 directory must be empty at ${0:X3}' -f $offset)
    }
}

Write-Host 'STR8-iN/65 PROMOTION = PASS'
Write-Host ('CANONICAL SHA256      = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $CanonicalTopPath).Hash)
Write-Host ('ACCEPTED SHA256       = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $AcceptedTopPath).Hash)
Write-Host ('MIGRATION SHA256      = {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $MigrationTopPath).Hash)
Write-Host 'EXTERNAL BIN CONTRACT  = byte-identical canonical top; D0 adoption follows boot'
