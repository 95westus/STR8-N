param(
    [Parameter(Mandatory = $true)][string]$BinPath,
    [string]$S19Path = "BUILD/v1.22/s19/guest-payload.s19",
    [int]$BaseAddress = 0x8000,
    [int]$EntryAddress = -1,
    [ValidateRange(0, 3)][int]$Bank = 0,
    [ValidateRange(1, 64)][int]$BytesPerRecord = 32
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-S1Record {
    param([int]$Address, [byte[]]$Data)
    $count = $Data.Length + 3
    $sum = $count + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    $dataHex = New-Object System.Text.StringBuilder
    foreach ($b in $Data) { $sum += $b; [void]$dataHex.AppendFormat('{0:X2}', $b) }
    return ('S1{0:X2}{1:X4}{2}{3:X2}' -f $count, $Address, $dataHex, ((-bnot $sum) -band 0xFF))
}

function New-S9Record {
    param([int]$Address)
    $sum = 3 + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    return ('S903{0:X4}{1:X2}' -f $Address, ((-bnot $sum) -band 0xFF))
}

if (-not (Test-Path -LiteralPath $BinPath)) { throw "Missing BIN: $BinPath" }
[byte[]]$image = [System.IO.File]::ReadAllBytes($BinPath)
$endExclusive = $BaseAddress + $image.Length
if ($image.Length -lt 0x1000 -or $image.Length -gt 0x8000 -or
    ($image.Length -band 0x0FFF) -ne 0 -or ($BaseAddress -band 0x0FFF) -ne 0 -or
    $BaseAddress -lt 0x8000 -or $endExclusive -gt 0x10000) {
    throw 'BIN must be a 4K-aligned 4K-32K image mapped wholly inside $8000-$FFFF'
}
if ($Bank -eq 3 -and $endExclusive -gt 0xF000) { throw 'Bank 3 BIN must not include protected sector F' }
if ($EntryAddress -lt -1 -or $EntryAddress -gt 0xFFFF) { throw 'EntryAddress must be -1 or fit in 16 bits' }

$fullBank = $BaseAddress -eq 0x8000 -and $image.Length -eq 0x8000
if ($EntryAddress -lt 0) {
    if ($fullBank -and $Bank -lt 3) {
        $EntryAddress = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
    } else {
        $EntryAddress = 0xFFFF
    }
}
if ($fullBank -and $Bank -lt 3) {
    $reset = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
    if ($EntryAddress -ne $reset -or $reset -eq 0xFFFF) { throw 'Full Bank 0-2 S9 must equal the non-erased RESET vector' }
} elseif ($Bank -eq 3 -and $EntryAddress -ne 0xFFFF -and
    ($EntryAddress -lt $BaseAddress -or $EntryAddress -ge $endExclusive)) {
    throw 'Bank-3 entry must be $FFFF for an existing row or inside the image for a first install'
} elseif ($Bank -lt 3 -and $EntryAddress -ne 0xFFFF -and
    ($EntryAddress -lt $BaseAddress -or $EntryAddress -ge $endExclusive)) {
    throw 'Partial Bank 0-2 entry must be $FFFF or inside the image'
}

$lines = New-Object System.Collections.Generic.List[string]
for ($offset = 0; $offset -lt $image.Length; $offset += $BytesPerRecord) {
    $length = [Math]::Min($BytesPerRecord, $image.Length - $offset)
    [byte[]]$data = New-Object byte[] $length
    [Array]::Copy($image, $offset, $data, 0, $length)
    $lines.Add((New-S1Record -Address ($BaseAddress + $offset) -Data $data))
}
$lines.Add((New-S9Record -Address $EntryAddress))

$parent = Split-Path -Parent $S19Path
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($S19Path, $lines, [System.Text.Encoding]::ASCII)
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BinPath).Hash
Write-Host ('GUEST BIN      = bank {0}, ${1:X4}-${2:X4}; {3} bytes' -f $Bank, $BaseAddress, ($endExclusive - 1), $image.Length)
Write-Host ('S9 ENTRY       = ${0:X4}' -f $EntryAddress)
Write-Host ('BIN SHA-256    = {0}' -f $hash)
Write-Host ('PAYLOAD S19    = {0}; {1} S1 records + one S9' -f $S19Path, ($lines.Count - 1))
