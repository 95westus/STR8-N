param(
    [string]$BinPath = "BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin",
    [string]$OutPath = "BUILD/v1.30/generated/str8n-v1.30-top-image.inc",
    [string]$Identity = 'STR8-N 1.30'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $BinPath)) { throw "Top-sector BIN not found: $BinPath" }
[byte[]]$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $BinPath).Path)
if ($bytes.Length -ne 4096) { throw "Top-sector BIN is $($bytes.Length) bytes; expected 4096" }

$identityBytes = [System.Text.Encoding]::ASCII.GetBytes($Identity)
$found = $false
for ($offset = 0; $offset -le ($bytes.Length - $identityBytes.Length); $offset++) {
    $same = $true
    for ($i = 0; $i -lt $identityBytes.Length; $i++) {
        if ($bytes[$offset + $i] -ne $identityBytes[$i]) { $same = $false; break }
    }
    if ($same) { $found = $true; break }
}
if (-not $found) { throw "Candidate top BIN does not contain $Identity identity" }
if ($bytes[0] -ne 0x4C) { throw 'Candidate top BIN does not begin with JMP' }
if ($bytes[0x0FFC] -eq 0xFF -and $bytes[0x0FFD] -eq 0xFF) { throw 'Candidate RESET vector is erased' }

$sum = 0
foreach ($byte in $bytes) { $sum = ($sum + $byte) -band 0xFFFF }
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add(('TU_CANDIDATE_SUM        EQU             ${0:X4}' -f $sum))
for ($offset = 0; $offset -lt $bytes.Length; $offset += 16) {
    $tokens = for ($i = 0; $i -lt 16; $i++) { '${0:X2}' -f $bytes[$offset + $i] }
    $lines.Add('                        DB              ' + ($tokens -join ','))
}

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($OutPath, $lines, [System.Text.Encoding]::ASCII)
Write-Host ('TOP UPDATE IMAGE    = {0}; sum=${1:X4}; SHA256={2}' -f $OutPath, $sum, (Get-FileHash -Algorithm SHA256 -LiteralPath $BinPath).Hash)
