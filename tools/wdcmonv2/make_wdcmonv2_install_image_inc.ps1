param(
    [string]$TopBinPath = 'BUILD/v1.33/bin/str8n-v1.33-bank3-f000-ffff.bin',
    [string]$OutPath = 'BUILD/v1.33/generated/str8n-v1.33-wdcmonv2-install-image.inc',
    [string]$CandidateBinPath = 'BUILD/v1.33/bin/str8n-v1.33-wdcmonv2-bank3-f000-ffff.bin'
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

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($OutPath, $lines, [System.Text.Encoding]::ASCII)
$binParent = Split-Path -Parent $CandidateBinPath
if ($binParent) { New-Item -ItemType Directory -Force -Path $binParent | Out-Null }
[System.IO.File]::WriteAllBytes($CandidateBinPath, $bytes)
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $candidateHash = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '') } finally { $sha.Dispose() }
Write-Host ('WDCMONV2 EXTERNAL TOP = {0}; exact canonical 4096-byte BIN; FNV1A={1:X8}; SHA256={2}' -f $CandidateBinPath, $fnv, $candidateHash)
