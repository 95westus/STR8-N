param(
    [Parameter(Mandatory = $true)][string]$TranscriptPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$BaseName = '',
    [ValidateRange(0, 3)][int]$Bank = -1,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Convert-SRecordBytes {
    param([Parameter(Mandatory = $true)][string]$Line)
    if ($Line.Length -lt 4 -or (($Line.Length - 2) -band 1) -ne 0) {
        throw "Malformed S-record length: $Line"
    }
    $bytes = New-Object byte[] (($Line.Length - 2) / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($Line.Substring(2 + (2 * $i), 2), 16)
    }
    if ($bytes[0] -ne ($bytes.Length - 1)) {
        throw "S-record count mismatch: $Line"
    }
    $sum = 0
    foreach ($b in $bytes) { $sum = ($sum + $b) -band 0xFF }
    if ($sum -ne 0xFF) { throw "S-record checksum mismatch: $Line" }
    return ,$bytes
}

function Get-Fnv1a32 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    [uint32]$hash = 2166136261
    foreach ($b in $Bytes) {
        [uint64]$product = [uint64]([uint32]($hash -bxor $b)) * [uint64]16777619
        $hash = [uint32]($product -band [uint64]4294967295)
    }
    return ('{0:X8}' -f $hash)
}

if (-not (Test-Path -LiteralPath $TranscriptPath)) {
    throw "Transcript not found: $TranscriptPath"
}

$beginPattern = '^W2R-BEGIN B=([0-3]) BYTES=8000 FNV1A=([0-9A-Fa-f]{8}) RESET=([0-9A-Fa-f]{4})$'
$endPattern = '^W2R-END B=([0-3]) BYTES=8000 FNV1A=([0-9A-Fa-f]{8})$'
$active = $null
$complete = $null

foreach ($raw in Get-Content -LiteralPath $TranscriptPath) {
    $line = $raw.Trim()
    $begin = [regex]::Match($line, $beginPattern)
    if ($begin.Success) {
        $active = [ordered]@{
            Bank = [int]$begin.Groups[1].Value
            Fnv = $begin.Groups[2].Value.ToUpperInvariant()
            Reset = $begin.Groups[3].Value.ToUpperInvariant()
            Records = [System.Collections.Generic.List[string]]::new()
        }
        continue
    }
    if ($null -eq $active) { continue }
    if ($line -match '^S[0-9]') {
        $active.Records.Add($line.ToUpperInvariant())
        continue
    }
    $end = [regex]::Match($line, $endPattern)
    if ($end.Success) {
        if ([int]$end.Groups[1].Value -ne $active.Bank) {
            throw 'W2R-END bank does not match W2R-BEGIN'
        }
        if ($end.Groups[2].Value.ToUpperInvariant() -ne $active.Fnv) {
            throw 'W2R-END FNV1A does not match W2R-BEGIN'
        }
        if ($Bank -lt 0 -or $active.Bank -eq $Bank) {
            $complete = $active
        }
        $active = $null
    }
}

if ($null -eq $complete) {
    if ($Bank -ge 0) {
        throw "No complete W2R-BEGIN/W2R-END transaction found for Bank $Bank"
    }
    throw 'No complete W2R-BEGIN/W2R-END archive transaction found'
}
if ($complete.Records.Count -ne 1025) {
    throw "Archive must contain 1024 S1 records and one S9; found $($complete.Records.Count) records"
}

$image = New-Object byte[] 0x8000
$expectedAddress = 0x8000
for ($recordIndex = 0; $recordIndex -lt 1024; $recordIndex++) {
    $line = $complete.Records[$recordIndex]
    if (-not $line.StartsWith('S1')) { throw "Record $recordIndex is not S1" }
    [byte[]]$bytes = Convert-SRecordBytes -Line $line
    $address = ([int]$bytes[1] -shl 8) -bor [int]$bytes[2]
    $dataLength = [int]$bytes[0] - 3
    if ($address -ne $expectedAddress -or $dataLength -ne 32) {
        throw ('Non-dense S1 at record {0}: address=${1:X4}, bytes={2}' -f $recordIndex, $address, $dataLength)
    }
    [Array]::Copy($bytes, 3, $image, $address - 0x8000, $dataLength)
    $expectedAddress += $dataLength
}
if ($expectedAddress -ne 0x10000) { throw 'Archive does not end exactly at $FFFF' }

$s9Line = $complete.Records[1024]
if (-not $s9Line.StartsWith('S9')) { throw 'Final record is not S9' }
[byte[]]$s9 = Convert-SRecordBytes -Line $s9Line
if ($s9[0] -ne 3) { throw 'S9 count must be 3' }
$s9Entry = ([int]$s9[1] -shl 8) -bor [int]$s9[2]
$declaredReset = [Convert]::ToInt32($complete.Reset, 16)
if ($s9Entry -ne $declaredReset) {
    throw ('S9 entry ${0:X4} does not match receipt RESET=${1}' -f $s9Entry, $complete.Reset)
}

$observedReset = [int]$image[0x7FFC] -bor ([int]$image[0x7FFD] -shl 8)
if ($observedReset -ne $declaredReset) {
    throw ('Image RESET vector ${0:X4} does not match receipt RESET=${1}' -f $observedReset, $complete.Reset)
}

$actualFnv = Get-Fnv1a32 -Bytes $image
if ($actualFnv -ne $complete.Fnv) {
    throw "Archive FNV1A mismatch: receipt=$($complete.Fnv), emitted=$actualFnv"
}

if ([string]::IsNullOrWhiteSpace($BaseName)) { $BaseName = "wdcmonv2-bank$($complete.Bank)" }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$binPath = Join-Path $OutputDirectory ($BaseName + '.bin')
$s19Path = Join-Path $OutputDirectory ($BaseName + '.s19')
$receiptPath = Join-Path $OutputDirectory ($BaseName + '.receipt.txt')
foreach ($path in @($binPath, $s19Path, $receiptPath)) {
    if ((Test-Path -LiteralPath $path) -and -not $Force) {
        throw "Output exists (use -Force to replace): $path"
    }
}

[System.IO.File]::WriteAllBytes($binPath, $image)
[System.IO.File]::WriteAllLines($s19Path, [string[]]$complete.Records, [System.Text.Encoding]::ASCII)
$sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $binPath).Hash
$receipt = @(
    'WDCMONV2 -> STR8-N LOCAL BANK ARCHIVE'
    "BANK=$($complete.Bank)"
    'BYTES=32768'
    "CPU_RANGE=8000-FFFF"
    "FNV1A=$actualFnv"
    ('RESET={0:X4}' -f $observedReset)
    "SHA256=$sha256"
    "SOURCE_TRANSCRIPT=$([System.IO.Path]::GetFullPath($TranscriptPath))"
    'STATUS=VERIFIED'
    'REDISTRIBUTION=OWNER-LOCAL; DO NOT PUBLISH WITHOUT EXPRESS PERMISSION'
)
[System.IO.File]::WriteAllLines($receiptPath, $receipt, [System.Text.Encoding]::ASCII)

Write-Host 'WDCMONV2 ARCHIVE = VERIFIED'
Write-Host ("BANK             = {0}" -f $complete.Bank)
Write-Host ("FNV1A            = {0}" -f $actualFnv)
Write-Host ("RESET            = {0:X4}" -f $observedReset)
Write-Host ("SHA256           = {0}" -f $sha256)
Write-Host ("BIN              = {0}" -f $binPath)
Write-Host ("S19              = {0}" -f $s19Path)
Write-Host ("RECEIPT          = {0}" -f $receiptPath)
Write-Warning 'OWNER-LOCAL ARCHIVE: do not publish or redistribute without express permission.'
