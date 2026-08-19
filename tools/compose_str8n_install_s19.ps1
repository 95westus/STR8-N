param(
    [Parameter(Mandatory = $true)][string]$PayloadS19Path,
    [string]$S19Path = "BUILD/v1.22/s19/str8n-install.s19",
    [int]$PayloadStart = 0x8000,
    [int]$PayloadEndExclusive = 0x10000,
    [ValidateRange(0, 3)][int]$Bank = 0,
    [int]$ExistingBank3Entry = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$size = $PayloadEndExclusive - $PayloadStart
if ($PayloadStart -lt 0x8000 -or $PayloadEndExclusive -gt 0x10000 -or
    $size -lt 0x1000 -or ($size -band 0x0FFF) -ne 0 -or
    ($PayloadStart -band 0x0FFF) -ne 0) {
    throw ('Payload ${0:X4}-${1:X4} must be a 4K-aligned 4K-32K range inside $8000-$FFFF' -f $PayloadStart, ($PayloadEndExclusive - 1))
}
if ($Bank -eq 3 -and $PayloadEndExclusive -gt 0xF000) {
    throw 'Bank 3 payload must end at or below $F000; sector F contains STR8-N'
}
if ($ExistingBank3Entry -lt -1 -or $ExistingBank3Entry -gt 0xFFFF) {
    throw 'ExistingBank3Entry must be -1 or fit in 16 bits'
}
if ($ExistingBank3Entry -ge 0 -and
    ($ExistingBank3Entry -lt 0x8000 -or $ExistingBank3Entry -ge 0xF000)) {
    throw 'An existing Bank-3 entry must be in $8000-$EFFF'
}

function Read-S19 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing S19: $Path" }
    $records = New-Object System.Collections.Generic.List[object]
    $lineNumber = 0
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $lineNumber++
        $line = $raw.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line -notmatch '^S([019])([0-9A-Fa-f]+)$') {
            throw "${Path}:$lineNumber only S0, S1, and S9 records are accepted"
        }
        $type = [int]$Matches[1]
        $hex = $Matches[2]
        if (($hex.Length -band 1) -ne 0 -or $hex.Length -lt 8) { throw "${Path}:$lineNumber malformed record" }
        $count = [Convert]::ToInt32($hex.Substring(0, 2), 16)
        if ($line.Length -ne (4 + (2 * $count))) { throw "${Path}:$lineNumber count/length mismatch" }
        $sum = 0
        for ($offset = 0; $offset -lt $hex.Length; $offset += 2) {
            $sum += [Convert]::ToInt32($hex.Substring($offset, 2), 16)
        }
        if (($sum -band 0xFF) -ne 0xFF) { throw "${Path}:$lineNumber checksum failure" }
        $address = [Convert]::ToInt32($hex.Substring(2, 4), 16)
        $dataLength = $count - 3
        if ($type -eq 9 -and $dataLength -ne 0) { throw "${Path}:$lineNumber S9 must contain no data" }
        [byte[]]$data = New-Object byte[] ([Math]::Max(0, $dataLength))
        for ($i = 0; $i -lt $dataLength; $i++) {
            $data[$i] = [Convert]::ToByte($hex.Substring(6 + (2 * $i), 2), 16)
        }
        $records.Add([pscustomobject]@{ Type=$type; Address=$address; Data=$data; Line=$line.ToUpperInvariant() })
    }
    return $records.ToArray()
}

$records = @(Read-S19 $PayloadS19Path)
if ($records.Count -eq 0) { throw 'Payload is empty' }
$index = 0
if ($records[0].Type -eq 0) { $index++ }
$expected = $PayloadStart
$s1Count = 0
[byte[]]$image = New-Object byte[] $size
while ($index -lt $records.Count -and $records[$index].Type -eq 1) {
    $record = $records[$index]
    if ($record.Data.Length -le 0) { throw 'Payload contains an empty S1 record' }
    if ($record.Address -ne $expected) {
        throw ('Payload gap, overlap, or reordering at ${0:X4}; expected ${1:X4}' -f $record.Address, $expected)
    }
    if (($expected + $record.Data.Length) -gt $PayloadEndExclusive) { throw 'Payload exceeds the selected range' }
    [Array]::Copy($record.Data, 0, $image, $expected - $PayloadStart, $record.Data.Length)
    $expected += $record.Data.Length
    $s1Count++
    $index++
}
if ($s1Count -eq 0 -or $expected -ne $PayloadEndExclusive) {
    throw ('Payload ends at ${0:X4}; expected ${1:X4}' -f $expected, $PayloadEndExclusive)
}
if ($index -ne ($records.Count - 1) -or $records[$index].Type -ne 9) {
    throw 'Exactly one final S9 must follow the dense S1 records'
}
$entry = $records[$index].Address

if ($Bank -lt 3 -and $PayloadStart -eq 0x8000 -and $PayloadEndExclusive -eq 0x10000) {
    $reset = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
    if ($entry -ne $reset -or $entry -eq 0xFFFF) {
        throw ('Full-bank S9 ${0:X4} must equal the non-erased RESET vector ${1:X4}' -f $entry, $reset)
    }
} elseif ($Bank -eq 3 -and $ExistingBank3Entry -ge 0) {
    if ($entry -ne 0xFFFF -and $entry -ne $ExistingBank3Entry) {
        throw ('Existing Bank-3 S9 ${0:X4} must be $FFFF or ${1:X4}' -f $entry, $ExistingBank3Entry)
    }
} elseif ($Bank -eq 3) {
    if ($entry -lt $PayloadStart -or $entry -ge $PayloadEndExclusive) {
        throw 'A first Bank-3 install requires an S9 entry inside the selected range'
    }
} elseif ($entry -ne 0xFFFF -and ($entry -lt $PayloadStart -or $entry -ge $PayloadEndExclusive)) {
    throw 'A partial Bank 0-2 payload requires S9=$FFFF or an entry inside the selected range'
}

$sectorCrcs = New-Object System.Collections.Generic.List[string]
for ($sectorOffset = 0; $sectorOffset -lt $image.Length; $sectorOffset += 0x1000) {
    $crc = 0xFFFF
    for ($i = 0; $i -lt 0x1000; $i++) {
        $crc = $crc -bxor ([int]$image[$sectorOffset + $i] -shl 8)
        for ($bit = 0; $bit -lt 8; $bit++) {
            if (($crc -band 0x8000) -ne 0) { $crc = (($crc -shl 1) -bxor 0x1021) -band 0xFFFF }
            else { $crc = ($crc -shl 1) -band 0xFFFF }
        }
    }
    $sectorCrcs.Add(('${0:X4}:{1:X4}' -f ($PayloadStart + $sectorOffset), $crc))
}

$parent = Split-Path -Parent $S19Path
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($S19Path, @($records | ForEach-Object { $_.Line }), [System.Text.Encoding]::ASCII)
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash
Write-Host ('PAYLOAD              = bank {0}, ${1:X4}-${2:X4}; {3} bytes' -f $Bank, $PayloadStart, ($PayloadEndExclusive - 1), $size)
Write-Host ('S1/S9                = {0} records / ${1:X4}' -f $s1Count, $entry)
Write-Host ('SECTOR CRC-16        = {0}' -f ($sectorCrcs -join '; '))
Write-Host ('S19 SHA-256          = {0}' -f $hash)
Write-Host ('PAYLOAD-ONLY STREAM  = {0}' -f $S19Path)
