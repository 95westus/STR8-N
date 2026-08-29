param(
    [string]$TopBinPath = 'BUILD/v1.28/bin/str8n-v1.28-bank3-f000-ffff.bin',
    [string]$OutPath = 'BUILD/v1.28/generated/str8n-v1.28-wdcmonv2-install-image.inc',
    [string]$CandidateBinPath = 'BUILD/v1.28/bin/str8n-v1.28-wdcmonv2-bank3-f000-ffff.bin'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $TopBinPath)) { throw "Top BIN not found: $TopBinPath" }
[byte[]]$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $TopBinPath).Path)
if ($bytes.Length -ne 4096) { throw "Top BIN is $($bytes.Length) bytes; expected 4096" }
if ($bytes[0] -ne 0x4C) { throw 'Top BIN does not begin with JMP' }
if ($bytes[0x0FFC] -eq 0xFF -and $bytes[0x0FFD] -eq 0xFF) { throw 'Top BIN RESET vector is erased' }
for ($offset = 0x0FB0; $offset -le 0x0FEF; $offset++) {
    if ($bytes[$offset] -ne 0xFF) { throw ('Canonical top directory is not empty at ${0:X4}' -f (0xF000 + $offset)) }
}

# A stock board's B1/B2 contents are not yet qualified.  Do not carry the
# canonical development-system defaults B1:E WORK and B1:F top backup into the
# seed install.  The migration image begins with both optional roles unassigned.
$bytes[0x0FF0] = 0xFF
$bytes[0x0FF1] = 0xFF

# The factory path always preserves the complete stock Bank 3 in Bank 0.
# Publish that retained monitor as a complete D0 row in the carried Bank-3
# directory so selector 0 and shell J0 work immediately after migration.
[byte[]]$wdcDirectory0 = @(
    0xFF, 0xFF, 0xFF, 0xFF,
    [byte][char]'W', [byte][char]'D', [byte][char]'C', [byte][char]'M', [byte][char]'2',
    0xFE, 0xFF, 0xFF, 0xFC, 0xFF, 0xFF, 0xFF
)
[Array]::Copy($wdcDirectory0, 0, $bytes, 0x0FB0, $wdcDirectory0.Length)

[uint32]$fnv = 2166136261
foreach ($byte in $bytes) {
    [uint64]$product = [uint64]([uint32]($fnv -bxor $byte)) * [uint64]16777619
    $fnv = [uint32]($product -band [uint64]4294967295)
}
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add(('W2I_CANDIDATE_FNV0      EQU             ${0:X2}' -f ($fnv -band 0xFF)))
$lines.Add(('W2I_CANDIDATE_FNV1      EQU             ${0:X2}' -f (($fnv -shr 8) -band 0xFF)))
$lines.Add(('W2I_CANDIDATE_FNV2      EQU             ${0:X2}' -f (($fnv -shr 16) -band 0xFF)))
$lines.Add(('W2I_CANDIDATE_FNV3      EQU             ${0:X2}' -f (($fnv -shr 24) -band 0xFF)))
for ($offset = 0; $offset -lt $bytes.Length; $offset += 16) {
    $tokens = for ($i = 0; $i -lt 16; $i++) { '${0:X2}' -f $bytes[$offset + $i] }
    $lines.Add('                        DB              ' + ($tokens -join ','))
}

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($OutPath, $lines, [System.Text.Encoding]::ASCII)
$binParent = Split-Path -Parent $CandidateBinPath
if ($binParent) { New-Item -ItemType Directory -Force -Path $binParent | Out-Null }
[System.IO.File]::WriteAllBytes($CandidateBinPath, $bytes)
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $candidateHash = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '') } finally { $sha.Dispose() }
Write-Host ('WDCMONV2 INSTALL TOP = {0}; D0=WDCM2 COMPLETE; roles=FF/FF; FNV1A={1:X8}; SHA256={2}' -f $CandidateBinPath, $fnv, $candidateHash)
