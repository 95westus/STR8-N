param(
    [Parameter(Mandatory = $true)][string]$BaseImagePath,
    [Parameter(Mandatory = $true)][string]$TopBinPath,
    [Parameter(Mandatory = $true)][string]$OutPath,
    [string]$ReceiptPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DeviceSize = 128KB
$TopSize = 4KB
$TopOffset = 0x1F000

foreach ($path in @($BaseImagePath, $TopBinPath)) {
    if ([string]::IsNullOrWhiteSpace($path) -or
        -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required input not found: $path"
    }
}

[byte[]]$base = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $BaseImagePath).Path)
[byte[]]$top = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $TopBinPath).Path)
if ($base.Length -ne $DeviceSize) {
    throw "Base image is $($base.Length) bytes; expected $DeviceSize"
}
if ($top.Length -ne $TopSize) {
    throw "STR8-iN/65 top is $($top.Length) bytes; expected $TopSize"
}
if ($top[0] -ne 0x4C) { throw 'STR8-iN/65 top does not begin with JMP' }
if ($top[0x0FFC] -eq 0xFF -and $top[0x0FFD] -eq 0xFF) {
    throw 'STR8-iN/65 top has an erased RESET vector'
}

[byte[]]$image = New-Object byte[] $DeviceSize
[Array]::Copy($base, $image, $DeviceSize)
[Array]::Copy($top, 0, $image, $TopOffset, $TopSize)

for ($offset = 0; $offset -lt $TopOffset; $offset++) {
    if ($image[$offset] -ne $base[$offset]) {
        throw ('Composition changed base byte outside B3:F at file offset ${0:X5}' -f $offset)
    }
}
for ($offset = 0; $offset -lt $TopSize; $offset++) {
    if ($image[$TopOffset + $offset] -ne $top[$offset]) {
        throw ('Composition mismatch in B3:F at sector offset ${0:X3}' -f $offset)
    }
}

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllBytes($OutPath, $image)

$baseHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BaseImagePath).Hash
$topHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TopBinPath).Hash
$outHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutPath).Hash
$changed = 0
for ($offset = 0; $offset -lt $TopSize; $offset++) {
    if ($base[$TopOffset + $offset] -ne $top[$offset]) { $changed++ }
}
$reset = [int]$top[0x0FFC] -bor ([int]$top[0x0FFD] -shl 8)

$receipt = @(
    'STR8-iN/65 local programmer image'
    'OWNER-LOCAL: contains bytes from the supplied base image; do not publish.'
    "BASE=$BaseImagePath"
    "BASE_SHA256=$baseHash"
    "TOP=$TopBinPath"
    "TOP_SHA256=$topHash"
    ('REPLACED_RANGE=file $1F000-$1FFFF / Bank 3 CPU $F000-$FFFF')
    "CHANGED_BYTES_IN_RANGE=$changed"
    ('RESET=${0:X4}' -f $reset)
    "OUTPUT=$OutPath"
    "OUTPUT_SHA256=$outHash"
)
if ([string]::IsNullOrWhiteSpace($ReceiptPath)) { $ReceiptPath = "$OutPath.receipt.txt" }
$receiptParent = Split-Path -Parent $ReceiptPath
if ($receiptParent) { New-Item -ItemType Directory -Force -Path $receiptParent | Out-Null }
[System.IO.File]::WriteAllLines($ReceiptPath, $receipt, [System.Text.Encoding]::ASCII)

$receipt | ForEach-Object { Write-Host $_ }
