param(
    [string]$PayloadS19Path = "../R-YORS/SRC/BUILD/s19/ryors-v1.2-asm-himon-bank3-8-e.s19",
    [string]$TopBinPath = "BUILD/v1.2/bin/str8n-v1.2-bank3-f000-ffff.bin",
    [string]$S19Path = "BUILD/v1.2/s19/ryors-v1.2-asm-himon-str8n-bank0-2-8-f.s19",
    [ValidateRange(1, 64)][int]$BytesPerRecord = 32
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-S1Record {
    param([int]$Address, [byte[]]$Data)
    $count = $Data.Length + 3
    $sum = $count + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    $hex = New-Object System.Text.StringBuilder
    foreach ($byte in $Data) {
        $sum += $byte
        [void]$hex.AppendFormat('{0:X2}', $byte)
    }
    return ('S1{0:X2}{1:X4}{2}{3:X2}' -f $count, $Address, $hex, ((-bnot $sum) -band 0xFF))
}

function New-S9Record {
    param([int]$Address)
    $sum = 3 + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    return ('S903{0:X4}{1:X2}' -f $Address, ((-bnot $sum) -band 0xFF))
}

if (-not (Test-Path -LiteralPath $PayloadS19Path)) { throw "Missing 28K payload: $PayloadS19Path" }
if (-not (Test-Path -LiteralPath $TopBinPath)) { throw "Missing STR8-N top BIN: $TopBinPath" }

$payload = @{}
$payloadS9 = $null
foreach ($rawLine in Get-Content -LiteralPath $PayloadS19Path) {
    $line = $rawLine.Trim()
    if ($line.Length -eq 0) { continue }
    if ($line -notmatch '^S([19])([0-9A-Fa-f]+)$') { throw "Unsupported record: $line" }
    $kind = $Matches[1]
    $hex = $Matches[2]
    if (($hex.Length % 2) -ne 0) { throw "Odd-length record: $line" }
    [byte[]]$bytes = for ($i = 0; $i -lt $hex.Length; $i += 2) {
        [Convert]::ToByte($hex.Substring($i, 2), 16)
    }
    if ($bytes[0] -ne ($bytes.Length - 1)) { throw "Bad record count: $line" }
    $sum = 0
    foreach ($byte in $bytes) { $sum = ($sum + $byte) -band 0xFF }
    if ($sum -ne 0xFF) { throw "Bad record checksum: $line" }
    $address = ([int]$bytes[1] -shl 8) -bor $bytes[2]
    if ($kind -eq '9') {
        if ($bytes[0] -ne 3 -or $null -ne $payloadS9) { throw "Invalid or duplicate S9: $line" }
        $payloadS9 = $address
        continue
    }
    $length = [int]$bytes[0] - 3
    if ($length -lt 1) { throw "Empty S1: $line" }
    $last = $address + $length - 1
    if ($address -lt 0x8000 -or $last -gt 0xEFFF) {
        throw ('28K payload record ${0:X4}-${1:X4} is outside $8000-$EFFF' -f $address, $last)
    }
    for ($i = 0; $i -lt $length; $i++) {
        $target = $address + $i
        if ($payload.ContainsKey($target)) { throw ('Duplicate payload byte ${0:X4}' -f $target) }
        $payload[$target] = $bytes[3 + $i]
    }
}

if ($payloadS9 -ne 0xC000) { throw ('28K payload S9 is ${0:X4}; expected $C000' -f $payloadS9) }
if ($payload.Count -ne 0x7000) { throw "28K payload contains $($payload.Count) bytes; expected 28672" }
for ($address = 0x8000; $address -le 0xEFFF; $address++) {
    if (-not $payload.ContainsKey($address)) { throw ('Missing payload byte ${0:X4}' -f $address) }
}

[byte[]]$top = [System.IO.File]::ReadAllBytes($TopBinPath)
if ($top.Length -ne 0x1000) { throw "STR8-N top BIN is $($top.Length) bytes; expected 4096" }

[byte[]]$image = New-Object byte[] 0x8000
for ($offset = 0; $offset -lt 0x7000; $offset++) { $image[$offset] = $payload[0x8000 + $offset] }
[Array]::Copy($top, 0, $image, 0x7000, 0x1000)
$reset = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
if ($reset -eq 0xFFFF -or $reset -lt 0x8000) { throw ('Invalid full-bank RESET vector ${0:X4}' -f $reset) }

$lines = New-Object System.Collections.Generic.List[string]
for ($offset = 0; $offset -lt $image.Length; $offset += $BytesPerRecord) {
    $length = [Math]::Min($BytesPerRecord, $image.Length - $offset)
    [byte[]]$recordData = New-Object byte[] $length
    [Array]::Copy($image, $offset, $recordData, 0, $length)
    $lines.Add((New-S1Record -Address (0x8000 + $offset) -Data $recordData))
}
$lines.Add((New-S9Record -Address $reset))

$parent = Split-Path -Parent $S19Path
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($S19Path, $lines, [System.Text.Encoding]::ASCII)

$sha = [System.Security.Cryptography.SHA256]::Create()
$imageHash = [BitConverter]::ToString($sha.ComputeHash($image)).Replace('-', '')
$s19Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash
Write-Host 'R-YORS FULL BANK    = PASS'
Write-Host 'CPU RANGE           = $8000-$FFFF; 32768 bytes'
Write-Host ('S1 RECORDS          = {0}' -f ($lines.Count - 1))
Write-Host ('S9 / RESET          = ${0:X4}' -f $reset)
Write-Host ('IMAGE SHA256        = {0}' -f $imageHash)
Write-Host ('S19 SHA256          = {0}' -f $s19Hash)
Write-Host ('OUTPUT               = {0}' -f $S19Path)
