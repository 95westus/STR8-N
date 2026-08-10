param(
    [string]$MutationWorkerS19Path = "BUILD/s19/str8n-mutation-worker-0200.s19",
    [Parameter(Mandatory = $true)][string]$PayloadS19Path,
    [string]$WorkerEqPath = "src/str8-worker-eq.inc",
    [string]$S19Path = "BUILD/s19/str8n-install.s19",
    [int]$PayloadStart = 0x8000,
    [int]$PayloadEndExclusive = 0x10000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($PayloadStart -lt 0x8000 -or $PayloadEndExclusive -gt 0x10000 -or
    $PayloadStart -ge $PayloadEndExclusive -or
    ($PayloadStart -band 0x0FFF) -ne 0 -or
    ($PayloadEndExclusive -band 0x0FFF) -ne 0) {
    throw ('Payload extent ${0:X4}-${1:X4} must be a non-empty 4K-aligned range inside $8000-$FFFF' -f `
        $PayloadStart, ($PayloadEndExclusive - 1))
}

function Get-EquValue {
    param([string]$Path, [string]$Name)

    $pattern = '^\s*' + [Regex]::Escape($Name) + '\s+EQU\s+(.+?)\s*$'
    $match = Select-String -LiteralPath $Path -Pattern $pattern | Select-Object -First 1
    if (-not $match) { throw "Missing literal constant $Name in $Path" }
    $value = $match.Matches[0].Groups[1].Value.Trim()
    if ($value -match '^\$([0-9A-Fa-f]+)$') { return [Convert]::ToInt32($Matches[1], 16) }
    if ($value -match "^'(.)'$" ) { return [int][char]$Matches[1] }
    throw "Unsupported literal constant $Name`: $value"
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
            throw "${Path}:$lineNumber unsupported or malformed record: $line"
        }
        $type = [int]$Matches[1]
        $hex = $Matches[2]
        if (($hex.Length -band 1) -ne 0 -or $hex.Length -lt 8) {
            throw "${Path}:$lineNumber malformed record length"
        }
        $count = [Convert]::ToInt32($hex.Substring(0, 2), 16)
        if ($line.Length -ne (4 + (2 * $count))) {
            throw "${Path}:$lineNumber count/length mismatch"
        }
        $sum = 0
        for ($offset = 0; $offset -lt $hex.Length; $offset += 2) {
            $sum += [Convert]::ToInt32($hex.Substring($offset, 2), 16)
        }
        if (($sum -band 0xFF) -ne 0xFF) {
            throw "${Path}:$lineNumber checksum failure"
        }
        $address = [Convert]::ToInt32($hex.Substring(2, 4), 16)
        $dataLength = $count - 3
        [byte[]]$data = New-Object byte[] ([Math]::Max(0, $dataLength))
        for ($i = 0; $i -lt $dataLength; $i++) {
            $data[$i] = [Convert]::ToByte($hex.Substring(6 + (2 * $i), 2), 16)
        }
        $records.Add([pscustomobject]@{
            Type = $type
            Address = $address
            Data = $data
            Line = $line.ToUpperInvariant()
        })
    }
    return $records.ToArray()
}

function Assert-DenseRecords {
    param(
        [object[]]$Records,
        [int]$Start,
        [int]$EndExclusive,
        [string]$Name
    )

    $expected = $Start
    foreach ($record in $Records) {
        if ($record.Type -ne 1) { continue }
        if ($record.Data.Length -le 0) { throw "$Name contains a zero-length S1 record" }
        if ($record.Address -ne $expected) {
            throw ('{0} gap/overlap at ${1:X4}; expected ${2:X4}' -f $Name, $record.Address, $expected)
        }
        $expected += $record.Data.Length
        if ($expected -gt $EndExclusive) {
            throw ('{0} crosses ${1:X4}' -f $Name, $EndExclusive)
        }
    }
    if ($expected -ne $EndExclusive) {
        throw ('{0} ends at ${1:X4}; expected ${2:X4}' -f $Name, $expected, $EndExclusive)
    }
}

$workerStart = Get-EquValue $WorkerEqPath 'STR8_JUMP_WORKER_START'
$mutationEnd = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_END'
$mutationSig = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_SIG'
$mutationSig0 = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_SIG0'
$mutationSig1 = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_SIG1'
$mutationSig2 = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_SIG2'
$mutationSig3 = Get-EquValue $WorkerEqPath 'STR8_MUTATION_WORKER_SIG3'

$workerRecords = Read-S19 $MutationWorkerS19Path
$payloadRecords = Read-S19 $PayloadS19Path

$workerS0 = @($workerRecords | Where-Object Type -eq 0)
$workerS9Records = @($workerRecords | Where-Object Type -eq 9)
if ($workerS0.Count -ne 0 -or $workerS9Records.Count -ne 1) {
    throw "Mutation worker must contain S1 data followed by exactly one S9 and no S0"
}
$workerS9 = $workerS9Records[0]
if ($workerS9.Address -ne $workerStart) {
    throw ('Mutation-worker S9 is ${0:X4}; expected ${1:X4}' -f $workerS9.Address, $workerStart)
}
Assert-DenseRecords $workerRecords $workerStart $mutationEnd 'Mutation worker'

$payloadS0 = @($payloadRecords | Where-Object Type -eq 0)
$payloadS1 = @($payloadRecords | Where-Object Type -eq 1)
$payloadS9 = @($payloadRecords | Where-Object Type -eq 9)
if ($payloadS0.Count -gt 1 -or $payloadS9.Count -ne 1) {
    throw "Payload must contain at most one S0 and exactly one S9"
}
Assert-DenseRecords $payloadRecords $PayloadStart $PayloadEndExclusive 'Payload'

[byte[]]$workerImage = New-Object byte[] ($mutationEnd - $workerStart)
$workerS1 = @($workerRecords | Where-Object Type -eq 1)
foreach ($record in $workerS1) {
    [Array]::Copy($record.Data, 0, $workerImage, $record.Address - $workerStart, $record.Data.Length)
}
[byte[]]$expectedSignature = $mutationSig0, $mutationSig1, $mutationSig2, $mutationSig3
for ($i = 0; $i -lt $expectedSignature.Length; $i++) {
    if ($workerImage[($mutationSig - $workerStart) + $i] -ne $expectedSignature[$i]) {
        throw ('Mutation-worker identity mismatch at ${0:X4}' -f ($mutationSig + $i))
    }
}

[byte[]]$payloadImage = New-Object byte[] ($PayloadEndExclusive - $PayloadStart)
foreach ($record in $payloadS1) {
    [Array]::Copy($record.Data, 0, $payloadImage, $record.Address - $PayloadStart, $record.Data.Length)
}

if ($PayloadStart -eq 0x8000 -and $PayloadEndExclusive -eq 0x10000) {
    $vectorOffset = 0xFFFC - $PayloadStart
    $resetVector = [int]$payloadImage[$vectorOffset] -bor ([int]$payloadImage[$vectorOffset + 1] -shl 8)
    if ($payloadS9[0].Address -ne $resetVector) {
        throw ('Payload S9 is ${0:X4}; reset vector is ${1:X4}' -f $payloadS9[0].Address, $resetVector)
    }
} else {
    if ($payloadS9[0].Address -ne 0xFFFF -and
        ($payloadS9[0].Address -lt $PayloadStart -or $payloadS9[0].Address -ge $PayloadEndExclusive)) {
        throw ('Range payload S9 ${0:X4} is outside ${1:X4}-${2:X4}' -f `
            $payloadS9[0].Address, $PayloadStart, ($PayloadEndExclusive - 1))
    }
}

$sectorCrcs = New-Object System.Collections.Generic.List[string]
for ($sectorOffset = 0; $sectorOffset -lt $payloadImage.Length; $sectorOffset += 0x1000) {
    $crc = 0xFFFF
    for ($i = 0; $i -lt 0x1000; $i++) {
        $crc = $crc -bxor ([int]$payloadImage[$sectorOffset + $i] -shl 8)
        for ($bit = 0; $bit -lt 8; $bit++) {
            if (($crc -band 0x8000) -ne 0) {
                $crc = (($crc -shl 1) -bxor 0x1021) -band 0xFFFF
            } else {
                $crc = ($crc -shl 1) -band 0xFFFF
            }
        }
    }
    $sectorHigh = ($PayloadStart + $sectorOffset) -shr 8
    $sectorCrcs.Add(('{0:X1}:${1:X2} {2:X2}' -f ($sectorHigh -shr 4), `
        ($crc -band 0xFF), ($crc -shr 8)))
}

$lines = New-Object System.Collections.Generic.List[string]
foreach ($record in $payloadS0) { $lines.Add($record.Line) }
foreach ($record in $workerS1) { $lines.Add($record.Line) }
foreach ($record in $payloadS1) { $lines.Add($record.Line) }
$lines.Add($payloadS9[0].Line)

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $S19Path) | Out-Null
[System.IO.File]::WriteAllLines($S19Path, $lines, [System.Text.Encoding]::ASCII)
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash

Write-Host ('MUTATION WORKER        = ${0:X4}-${1:X4}; {2} S1 records' -f $workerStart, ($mutationEnd - 1), $workerS1.Count)
Write-Host ('PAYLOAD                = ${0:X4}-${1:X4}; {2} S1 records' -f $PayloadStart, ($PayloadEndExclusive - 1), $payloadS1.Count)
Write-Host ('S9 ENTRY               = ${0:X4}' -f $payloadS9[0].Address)
Write-Host ('SECTOR CRC LO HI        = {0}' -f ($sectorCrcs -join '; '))
Write-Host ('COMBINED RECORDS        = {0}; one file/send operation' -f $lines.Count)
Write-Host ('SHA-256                 = {0}' -f $hash)
Write-Host ('STR8-N I TRANSPORT     = {0}' -f $S19Path)
