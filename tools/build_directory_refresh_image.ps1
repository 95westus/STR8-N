param(
    [Parameter(Mandatory = $true)]
    [string]$ReadbackPath,

    [Parameter(Mandatory = $true)]
    [string]$ConfirmReadbackPath,

    [string]$TopBinPath = "BUILD/v1.21/bin/str8n-v1.21-bank3-f000-ffff.bin",

    [Parameter(Mandatory = $true)]
    [string]$OutPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DeviceSize = 0x20000
$TopStart = 0x1F000
$TopSize = 0x1000
$DirectoryOffset = 0x0FB0
$ConfigEndOffset = 0x0FF9

$readbackFullPath = [System.IO.Path]::GetFullPath($ReadbackPath)
$confirmReadbackFullPath = [System.IO.Path]::GetFullPath($ConfirmReadbackPath)
$topFullPath = [System.IO.Path]::GetFullPath($TopBinPath)
$outFullPath = [System.IO.Path]::GetFullPath($OutPath)

if ($readbackFullPath -eq $confirmReadbackFullPath) {
    throw 'The two independently saved readbacks must have distinct paths'
}
if ($outFullPath -eq $readbackFullPath -or
    $outFullPath -eq $confirmReadbackFullPath -or
    $outFullPath -eq $topFullPath) {
    throw 'Output path must not overwrite either input archive'
}

foreach ($path in @($readbackFullPath, $confirmReadbackFullPath, $topFullPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required input not found: $path"
    }
}

[byte[]]$readback = [System.IO.File]::ReadAllBytes($readbackFullPath)
[byte[]]$confirmReadback = [System.IO.File]::ReadAllBytes($confirmReadbackFullPath)
[byte[]]$top = [System.IO.File]::ReadAllBytes($topFullPath)

if ($readback.Length -ne $DeviceSize) {
    throw ('Readback is {0} bytes; SST39SF010A must be exactly {1} bytes' -f $readback.Length, $DeviceSize)
}
if ($confirmReadback.Length -ne $DeviceSize) {
    throw ('Confirming readback is {0} bytes; SST39SF010A must be exactly {1} bytes' -f $confirmReadback.Length, $DeviceSize)
}
if ($top.Length -ne $TopSize) {
    throw ('Top BIN is {0} bytes; expected exactly {1}' -f $top.Length, $TopSize)
}

$readbackHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $readbackFullPath).Hash
$confirmReadbackHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $confirmReadbackFullPath).Hash
if ($readbackHash -ne $confirmReadbackHash) {
    throw ('Independent readback SHA-256 mismatch: {0} != {1}' -f $readbackHash, $confirmReadbackHash)
}
if ($top[0x0000] -ne 0x4C) {
    throw 'Top BIN does not begin with the STR8-N JMP reset entry'
}
if ($top[0x000C] -ne 0x53 -or $top[0x000D] -ne 0x52 -or $top[0x000E] -ne 0x02 -or $top[0x000F] -ne 0x03) {
    throw 'Top BIN does not contain the expected SR/02/03 resident signature'
}
if ($top[0x0FFC] -ne 0x00 -or $top[0x0FFD] -ne 0xF0) {
    throw ('Top BIN RESET vector is ${0:X2}{1:X2}; expected $F000' -f $top[0x0FFD], $top[0x0FFC])
}

for ($offset = $DirectoryOffset; $offset -le $ConfigEndOffset; $offset++) {
    if ($top[$offset] -ne 0xFF) {
        throw ('Top BIN directory/config byte ${0:X3} is ${1:X2}; expected erased $FF' -f $offset, $top[$offset])
    }
}

[byte[]]$merged = New-Object byte[] $DeviceSize
[Array]::Copy($readback, 0, $merged, 0, $DeviceSize)
[Array]::Copy($top, 0, $merged, $TopStart, $TopSize)

for ($offset = 0; $offset -lt $TopStart; $offset++) {
    if ($merged[$offset] -ne $readback[$offset]) {
        throw ('Merge changed protected readback byte ${0:X5} outside the target sector' -f $offset)
    }
}

$parent = Split-Path -Parent $outFullPath
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
[System.IO.File]::WriteAllBytes($outFullPath, $merged)

$topHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $topFullPath).Hash
$outHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outFullPath).Hash

Write-Host ('READBACK 1           = {0}; {1} bytes' -f $readbackFullPath, $readback.Length)
Write-Host ('READBACK 2           = {0}; {1} bytes' -f $confirmReadbackFullPath, $confirmReadback.Length)
Write-Host ('MATCHED SHA-256      = {0}' -f $readbackHash)
Write-Host ('TOP BIN              = {0}; {1} bytes' -f $topFullPath, $top.Length)
Write-Host ('TOP BIN SHA-256      = {0}' -f $topHash)
Write-Host ('CHANGED PHYSICAL     = $1F000-$1FFFF only')
Write-Host ('ERASED DIRECTORY     = $1FFB0-$1FFEF')
Write-Host ('ERASED CONFIG        = $1FFF0-$1FFF9')
Write-Host ('RESET VECTOR         = $F000')
Write-Host ('PROGRAMMER IMAGE     = {0}; {1} bytes' -f $outFullPath, $merged.Length)
Write-Host ('PROGRAMMER SHA-256   = {0}' -f $outHash)
Write-Host 'DIRECTORY REFRESH IMAGE = PASS'
