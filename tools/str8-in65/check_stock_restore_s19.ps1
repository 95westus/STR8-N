param(
    [string]$SourcePath = 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm',
    [string]$S19Path = 'BUILD/v1.29/s19/str8n-v1.29-str8-in65-factory-restore-2000.s19',
    [string]$MapPath = 'BUILD/v1.29/s19/str8n-v1.29-str8-in65-factory-restore-2000.map',
    [string]$VersionText = '1.29'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($path in @($SourcePath, $S19Path, $MapPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing stock-restore component: $path"
    }
}

$source = Get-Content -Raw -LiteralPath $SourcePath
foreach ($required in @(
    'W2R_START:',
    'TYPE RESTORE FACTORY BOARD> ',
    'SECTORS 8-E FIRST; RESET SECTOR F LAST',
    'W2R_COPY_LOWER:',
    'CMP             #$F0',
    'W2R_COPY_TOP:',
    'W2R_SECTOR_RETRY:',
    'JSR             W2I_FLASH_TO_STAGE',
    'JSR             W2I_PROGRAM_STAGE',
    'JSR             W2I_HASH_EQUALS_SOURCE',
    'JSR             W2I_COMPARE_B0_B3_EXACT',
    'B0 == B3 WHOLE BANK VERIFIED',
    'W2R_ERASE_B0:',
    'JSR             W2I_FLASH_ERASE_SECTOR',
    'FACTORY BASELINE VERIFIED: B0 ERASED; B3 STOCK'
)) {
    if (-not $source.Contains($required)) {
        throw "Stock-restore source lacks required guard or proof: $required"
    }
}

$lower = $source.IndexOf('W2R_COPY_LOWER:', [System.StringComparison]::Ordinal)
$top = $source.IndexOf('W2R_COPY_TOP:', [System.StringComparison]::Ordinal)
$verify = $source.IndexOf('W2R_FINAL_VERIFY:', [System.StringComparison]::Ordinal)
$erase = $source.IndexOf('W2R_ERASE_B0:', [System.StringComparison]::Ordinal)
if ($lower -lt 0 -or $top -le $lower -or $verify -le $top -or $erase -le $verify) {
    throw 'Stock-restore source does not preserve lower-sectors, top-sector, final-verify, B0-erase order'
}

$map = Get-Content -Raw -LiteralPath $MapPath
if ($map -notmatch '(?im)^\s*00002000\s+START\s*$') {
    throw 'Stock-restore START is not linked at $2000'
}

$minAddress = 0x10000
$maxAddress = -1
$entry = -1
$dataBytes = 0
$payload = [System.Collections.Generic.List[byte]]::new()
foreach ($raw in Get-Content -LiteralPath $S19Path) {
    $line = $raw.Trim()
    if ($line -match '^S1([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]+)$') {
        $count = [Convert]::ToInt32($Matches[1], 16)
        $address = [Convert]::ToInt32($Matches[2], 16)
        $record = $Matches[3]
        $payloadBytes = $count - 3
        $minAddress = [Math]::Min($minAddress, $address)
        $maxAddress = [Math]::Max($maxAddress, $address + $payloadBytes - 1)
        $dataBytes += $payloadBytes
        for ($i = 0; $i -lt $payloadBytes; $i++) {
            $payload.Add([Convert]::ToByte($record.Substring($i * 2, 2), 16))
        }
    } elseif ($line -match '^S903([0-9A-Fa-f]{4})[0-9A-Fa-f]{2}$') {
        $entry = [Convert]::ToInt32($Matches[1], 16)
    }
}

if ($minAddress -ne 0x2000 -or $maxAddress -ge 0x4000 -or $entry -ne 0x2000) {
    throw ('Board-test RAM contract failed: range=${0:X4}-${1:X4}, S9=${2:X4}; carried candidate data is forbidden' -f $minAddress, $maxAddress, $entry)
}

$ascii = [System.Text.Encoding]::ASCII.GetString($payload.ToArray())
foreach ($prompt in @(
    "STR8-N $VersionText STOCK RESTORE",
    'SOURCE B0 FNV1A=',
    'FACTORY BASELINE: B0 -> B3, THEN ERASE B0',
    'DEST B3 WILL BE REPLACED',
    'TYPE RESTORE FACTORY BOARD> ',
    'COPY/VERIFY B0 -> B3 8-E ',
    'B3:F LAST ',
    'B0 == B3 WHOLE BANK VERIFIED',
    'ERASE/VERIFY FACTORY B0 ',
    'FACTORY BASELINE VERIFIED: B0 ERASED; B3 STOCK',
    'BOOT STOCK B3'
)) {
    if (-not $ascii.Contains($prompt)) {
        throw "Stock-restore S19 lacks visible operator prompt: $prompt"
    }
}

Write-Host ('STR8-iN/65 STOCK RESTORE = PASS; bytes={0}; range=${1:X4}-${2:X4}; S9=$2000' -f $dataBytes, $minAddress, $maxAddress)
Write-Host 'RESTORE CONTRACT = B0 source + B3 destination + 8-E first + F last + exact proof + B0 erased/verified + B3 re-hashed'
