param(
    [Parameter(Mandatory = $true)][string]$BinPath,
    [string]$S19Path = "BUILD/s19/guest-8000-ffff.s19",
    [ValidateRange(1, 64)][int]$BytesPerRecord = 32
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-S1Record {
    param([int]$Address, [byte[]]$Data)
    $count = $Data.Length + 3
    $sum = $count + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    $dataHex = New-Object System.Text.StringBuilder
    foreach ($b in $Data) {
        $sum += $b
        [void]$dataHex.AppendFormat('{0:X2}', $b)
    }
    $checksum = (-bnot $sum) -band 0xFF
    return ('S1{0:X2}{1:X4}{2}{3:X2}' -f $count, $Address, $dataHex, $checksum)
}

function New-S9Record {
    param([int]$Address)
    $sum = 3 + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    return ('S903{0:X4}{1:X2}' -f $Address, ((-bnot $sum) -band 0xFF))
}

if (-not (Test-Path -LiteralPath $BinPath)) { throw "Missing BIN: $BinPath" }
[byte[]]$image = [System.IO.File]::ReadAllBytes($BinPath)
if ($image.Length -ne 0x8000) {
    throw "Guest BIN is $($image.Length) bytes; expected exactly 32768 for `$8000-`$FFFF"
}

$nmi = [int]$image[0x7FFA] -bor ([int]$image[0x7FFB] -shl 8)
$reset = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
$irq = [int]$image[0x7FFE] -bor ([int]$image[0x7FFF] -shl 8)
if ($reset -lt 0x8000 -or $reset -gt 0xFFFE) {
    throw ('RESET vector is ${0:X4}; STR8 Jn requires $8000-$FFFE' -f $reset)
}

$lines = New-Object System.Collections.Generic.List[string]
for ($offset = 0; $offset -lt $image.Length; $offset += $BytesPerRecord) {
    $length = [Math]::Min($BytesPerRecord, $image.Length - $offset)
    [byte[]]$data = New-Object byte[] $length
    [Array]::Copy($image, $offset, $data, 0, $length)
    $lines.Add((New-S1Record -Address (0x8000 + $offset) -Data $data))
}
$lines.Add((New-S9Record -Address $reset))

$parent = Split-Path -Parent $S19Path
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($S19Path, $lines, [System.Text.Encoding]::ASCII)
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BinPath).Hash
Write-Host ('GUEST BIN       = {0}; 32768 bytes' -f $BinPath)
Write-Host ('NMI/RESET/IRQ   = ${0:X4}/${1:X4}/${2:X4}' -f $nmi, $reset, $irq)
Write-Host ('BIN SHA-256     = {0}' -f $hash)
Write-Host ('PAYLOAD S19     = {0}; {1} S1 records + one S9' -f `
    $S19Path, ($lines.Count - 1))
