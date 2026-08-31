param(
    [string]$SourcePath = 'tools/wdcmonv2/wdcmonv2str8n-archive-2000.asm',
    [string]$S19Path = 'BUILD/v1.29/s19/str8n-v1.29-wdcmonv2-archive-2000.s19',
    [string]$MapPath = 'BUILD/v1.29/map/str8n-v1.29-wdcmonv2-archive-2000.map',
    [string]$ExtractorPath = 'tools/wdcmonv2/extract_wdcmonv2_archive.ps1'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-Fnv1a32 {
    param([byte[]]$Bytes)
    [uint32]$hash = 2166136261
    foreach ($b in $Bytes) {
        [uint64]$product = [uint64]([uint32]($hash -bxor $b)) * [uint64]16777619
        $hash = [uint32]($product -band [uint64]4294967295)
    }
    return ('{0:X8}' -f $hash)
}

function New-S1 {
    param([int]$Address, [byte[]]$Data)
    $count = $Data.Length + 3
    $sum = $count + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    $body = [System.Text.StringBuilder]::new()
    foreach ($b in $Data) { $sum += $b; [void]$body.AppendFormat('{0:X2}', $b) }
    return ('S1{0:X2}{1:X4}{2}{3:X2}' -f $count, $Address, $body, ((-bnot $sum) -band 0xFF))
}

function New-S9 {
    param([int]$Address)
    $sum = 3 + (($Address -shr 8) -band 0xFF) + ($Address -band 0xFF)
    return ('S903{0:X4}{1:X2}' -f $Address, ((-bnot $sum) -band 0xFF))
}

foreach ($path in @($SourcePath, $S19Path, $MapPath, $ExtractorPath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing archive component: $path" }
}

[byte[]]$hello = [System.Text.Encoding]::ASCII.GetBytes('hello')
if ((Get-Fnv1a32 -Bytes $hello) -ne '4F9F2CAB') {
    throw 'Host FNV-1a implementation failed the published hello test vector'
}

$source = Get-Content -Raw -LiteralPath $SourcePath
foreach ($required in @(
    'READ ONLY; NO FLASH WRITE CODE', 'W2R-BEGIN B=', 'W2R-END B=',
    'FNV1A=', 'W2R_SELECT_BANK_A', 'W2R_EMIT_S1_32', 'W2R_EMIT_S9_RESET'
)) {
    if (-not $source.Contains($required)) { throw "Archive source lacks required contract text: $required" }
}
if ($source -match '(?i)\$D555|\$AAAA') {
    throw 'Read-only archive source contains an SST39 unlock address'
}
if ($source -match '(?im)^\s*(STA|STZ|TRB|TSB|INC|DEC)\s+\$[89A-F][0-9A-F]{3}\b') {
    throw "Read-only archive source contains an absolute write in CPU flash space: $($Matches[0])"
}

$map = Get-Content -Raw -LiteralPath $MapPath
if ($map -notmatch '(?im)^\s*00002000\s+START\s*$') { throw 'START is not linked at $2000' }

$minAddress = 0x10000
$maxAddress = -1
$entry = -1
$dataBytes = 0
foreach ($raw in Get-Content -LiteralPath $S19Path) {
    $line = $raw.Trim()
    if ($line -match '^S1([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]+)$') {
        $count = [Convert]::ToInt32($Matches[1], 16)
        $address = [Convert]::ToInt32($Matches[2], 16)
        $payloadBytes = $count - 3
        $minAddress = [Math]::Min($minAddress, $address)
        $maxAddress = [Math]::Max($maxAddress, $address + $payloadBytes - 1)
        $dataBytes += $payloadBytes
    } elseif ($line -match '^S903([0-9A-Fa-f]{4})[0-9A-Fa-f]{2}$') {
        $entry = [Convert]::ToInt32($Matches[1], 16)
    }
}
if ($minAddress -ne 0x2000 -or $maxAddress -gt 0x7AFF -or $entry -ne 0x2000) {
    throw ('RAM image contract failed: range=${0:X4}-${1:X4}, S9=${2:X4}' -f $minAddress, $maxAddress, $entry)
}

$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ('str8n-w2r-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
    $image = New-Object byte[] 0x8000
    for ($i = 0; $i -lt $image.Length; $i++) { $image[$i] = [byte](($i * 17 + 3) -band 0xFF) }
    $image[0x7FFC] = 0x00
    $image[0x7FFD] = 0xC0
    $fnv = Get-Fnv1a32 -Bytes $image
    $records = [System.Collections.Generic.List[string]]::new()
    $records.Add("W2R-BEGIN B=0 BYTES=8000 FNV1A=$fnv RESET=C000")
    for ($offset = 0; $offset -lt $image.Length; $offset += 32) {
        $chunk = New-Object byte[] 32
        [Array]::Copy($image, $offset, $chunk, 0, 32)
        $records.Add((New-S1 -Address (0x8000 + $offset) -Data $chunk))
    }
    $records.Add((New-S9 -Address 0xC000))
    $records.Add("W2R-END B=0 BYTES=8000 FNV1A=$fnv")

    $image3 = New-Object byte[] 0x8000
    [Array]::Copy($image, $image3, $image.Length)
    $image3[0] = $image3[0] -bxor 0xFF
    $image3[0x7FFC] = 0x23
    $image3[0x7FFD] = 0xC1
    $fnv3 = Get-Fnv1a32 -Bytes $image3
    $records.Add("W2R-BEGIN B=3 BYTES=8000 FNV1A=$fnv3 RESET=C123")
    for ($offset = 0; $offset -lt $image3.Length; $offset += 32) {
        $chunk = New-Object byte[] 32
        [Array]::Copy($image3, $offset, $chunk, 0, 32)
        $records.Add((New-S1 -Address (0x8000 + $offset) -Data $chunk))
    }
    $records.Add((New-S9 -Address 0xC123))
    $records.Add("W2R-END B=3 BYTES=8000 FNV1A=$fnv3")
    $transcript = Join-Path $scratch 'fixture.log'
    [System.IO.File]::WriteAllLines($transcript, [string[]]$records, [System.Text.Encoding]::ASCII)
    $outDir = Join-Path $scratch 'out'
    & $ExtractorPath -TranscriptPath $transcript -OutputDirectory $outDir -BaseName fixture -Bank 0 | Out-Null
    [byte[]]$roundTrip = [System.IO.File]::ReadAllBytes((Join-Path $outDir 'fixture.bin'))
    if ($roundTrip.Length -ne $image.Length) { throw 'Extractor fixture BIN length mismatch' }
    for ($i = 0; $i -lt $image.Length; $i++) {
        if ($roundTrip[$i] -ne $image[$i]) { throw "Extractor fixture mismatch at offset $i" }
    }
    $receiptText = Get-Content -Raw -LiteralPath (Join-Path $outDir 'fixture.receipt.txt')
    if (-not $receiptText.Contains(
            'REDISTRIBUTION=OWNER-LOCAL; DO NOT PUBLISH WITHOUT EXPRESS PERMISSION')) {
        throw 'Extractor receipt lacks the owner-local redistribution warning'
    }

    $bad = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $records) { $bad.Add($line) }
    $bad[1] = $bad[1].Substring(0, 10) + '00' + $bad[1].Substring(12)
    $badTranscript = Join-Path $scratch 'bad.log'
    [System.IO.File]::WriteAllLines($badTranscript, [string[]]$bad, [System.Text.Encoding]::ASCII)
    $rejected = $false
    try {
        & $ExtractorPath -TranscriptPath $badTranscript -OutputDirectory (Join-Path $scratch 'bad-out') -Bank 0 | Out-Null
    } catch {
        $rejected = $true
    }
    if (-not $rejected) { throw 'Extractor accepted a corrupt S1 record' }
} finally {
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
}

Write-Host ('WDCMONV2 ARCHIVE S19 = PASS; bytes={0}; range=${1:X4}-${2:X4}; S9=$2000' -f $dataBytes, $minAddress, $maxAddress)
Write-Host 'ARCHIVE EXTRACTOR TEST = PASS; bank selection + dense 32K + checksum rejection + FNV + RESET'
