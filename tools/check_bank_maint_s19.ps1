param(
    [string]$S19Path = "BUILD/v1.21/s19/str8n-v1.21-bank-maint-2000.s19",
    [string]$SourcePath = "tools/bank-maint/str8n-v1.21-bank-maint-2000.asm"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$expectedEntry = 0x2000
$lowestAllowed = 0x2000
$highestAllowed = 0x7AFF
$data = @{}
$dataRecords = 0
$startRecords = 0

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Missing Bank Maintenance source: $SourcePath"
}
$sourceLines = [System.IO.File]::ReadAllLines((Resolve-Path $SourcePath))
$codeText = ($sourceLines | ForEach-Object { ($_ -split ';', 2)[0] }) -join "`n"
$reclaimStart = $codeText.IndexOf('BM_RECLAIM LDA')
$reclaimEnd = $codeText.IndexOf('BM_ERASE LDA')
if ($reclaimStart -lt 0 -or $reclaimEnd -le $reclaimStart) {
    throw 'Bank Maintenance reclaim routine is missing or out of order'
}
$reclaimCode = $codeText.Substring($reclaimStart, $reclaimEnd - $reclaimStart)
foreach ($requiredCode in @('JSR BM_COPY_DIR_EMPTY', 'JSR BM_BUFFER_ERASED',
        'LDA #$03', 'LDA #$F0', 'STA $7C02', 'STA $7C03',
        'STA $7C04', 'JSR BM_STAGE', 'JSR BM_FILL', 'BM_RECLAIM_J3',
        'STA $19EC', 'STA $19ED', 'STA $19EE', 'STA $19EF')) {
    if (-not $reclaimCode.Contains($requiredCode)) {
        throw "Bank Maintenance reclaim is missing '$requiredCode'"
    }
}
$j3Match = [regex]::Match($reclaimCode, '(?m)^BM_RECLAIM_J3\s*$')
$j3EndMatch = [regex]::Match($reclaimCode, '(?m)^BM_MRBANK\s+DB')
$j3Start = $j3Match.Index
$j3End = $j3EndMatch.Index
if (-not $j3Match.Success -or -not $j3EndMatch.Success -or $j3End -le $j3Start) {
    throw 'Bank Maintenance D3 journal compaction routine is missing or out of order'
}
$staleReclaimCode = $reclaimCode.Substring(0, $j3Start)
$j3ReclaimCode = $reclaimCode.Substring($j3Start, $j3End - $j3Start)
foreach ($branch in @(
        @{ Name = 'D0-D2 reclaim'; Code = $staleReclaimCode },
        @{ Name = 'D3 compaction'; Code = $j3ReclaimCode })) {
    $programCalls = ([regex]::Matches($branch.Code, 'JSR\s+BM_PROGRAM')).Count
    if ($programCalls -ne 3) {
        throw "Bank Maintenance $($branch.Name) has $programCalls program calls; expected backup, B3F rewrite, and backup erase"
    }
}
foreach ($requiredCode in @('LDY #$0C', 'CPY #$10', 'LDA #$FC',
        'STZ $7C08', 'LDA #$80', 'CMP #$03')) {
    if (-not $j3ReclaimCode.Contains($requiredCode)) {
        throw "Bank Maintenance D3 compaction is missing '$requiredCode'"
    }
}
$journalStoreTargets = @([regex]::Matches($j3ReclaimCode, 'STA\s+\$(19E[0-9A-F])') |
    ForEach-Object { $_.Groups[1].Value })
if (($journalStoreTargets -join ',') -ne '19EC,19ED,19EE,19EF') {
    throw "Bank Maintenance D3 compaction writes unexpected D3 bytes: $($journalStoreTargets -join ',')"
}

foreach ($rawLine in Get-Content -LiteralPath $S19Path) {
    $line = $rawLine.Trim()
    if ($line.Length -eq 0) { continue }
    if ($line -notmatch '^S([19])([0-9A-Fa-f]+)$') {
        throw "Unsupported or malformed S-record: $line"
    }

    $kind = $Matches[1]
    $hex = $Matches[2]
    if (($hex.Length % 2) -ne 0) { throw "Odd-length S-record: $line" }
    $bytes = for ($i = 0; $i -lt $hex.Length; $i += 2) {
        [Convert]::ToInt32($hex.Substring($i, 2), 16)
    }
    if ($bytes.Count -lt 4) { throw "Short S-record: $line" }
    if ($bytes[0] -ne ($bytes.Count - 1)) { throw "Bad count: $line" }
    $sum = 0
    foreach ($byte in $bytes) { $sum = ($sum + $byte) -band 0xFF }
    if ($sum -ne 0xFF) { throw "Bad checksum: $line" }

    $address = ($bytes[1] -shl 8) -bor $bytes[2]
    if ($kind -eq '1') {
        $length = $bytes[0] - 3
        if ($length -lt 1) { throw "Empty S1 record: $line" }
        $last = $address + $length - 1
        if (($address -lt $lowestAllowed) -or ($last -gt $highestAllowed)) {
            throw ('S1 range ${0:X4}-${1:X4} is outside STR8-N L RAM' -f $address, $last)
        }
        for ($i = 0; $i -lt $length; $i++) {
            $target = $address + $i
            if ($data.ContainsKey($target)) { throw ('Duplicate S1 byte at ${0:X4}' -f $target) }
            $data[$target] = $bytes[3 + $i]
        }
        $dataRecords++
    }
    else {
        if ($bytes[0] -ne 3) { throw "S9 must not contain data: $line" }
        if ($address -ne $expectedEntry) {
            throw ('S9 entry ${0:X4}; expected ${1:X4}' -f $address, $expectedEntry)
        }
        $startRecords++
    }
}

if ($dataRecords -eq 0) { throw 'No S1 data records found' }
if ($startRecords -ne 1) { throw "Expected one S9 record; found $startRecords" }
foreach ($required in @(0x2000, 0x3400, 0x362A)) {
    if (-not $data.ContainsKey($required)) {
        throw ('Required program/worker byte ${0:X4} is absent' -f $required)
    }
}

$orderedAddresses = @($data.Keys | Sort-Object)
[byte[]]$programBytes = $orderedAddresses | ForEach-Object { $data[$_] }
$banner = [System.Text.Encoding]::ASCII.GetBytes('STR8-N 1.21 BANK MAINT')
$bannerFound = $false
for ($offset = 0; $offset -le $programBytes.Length - $banner.Length; $offset++) {
    $match = $true
    for ($index = 0; $index -lt $banner.Length; $index++) {
        if ($programBytes[$offset + $index] -ne $banner[$index]) {
            $match = $false
            break
        }
    }
    if ($match) {
        $bannerFound = $true
        break
    }
}
if (-not $bannerFound) { throw 'Bank Maintenance does not publish its v1.21 banner' }

foreach ($requiredText in @('D=ADOPT', 'ENTRY 8000-FFFE>', 'TYPE ADOPT B',
        'R=RECLAIM DIR', 'RECLAIM DIR 0-3>', 'B3F REWRITE',
        'TYPE CLEAR D', 'BACKUP VERIFIED', 'BANK NOT ERASED', 'DIR EMPTY',
        'SCRATCH B', 'TYPE RESET J3>', 'J3 NOT FULL',
        'NO ERASED SCRATCH')) {
    $needle = [System.Text.Encoding]::ASCII.GetBytes($requiredText)
    $found = $false
    for ($offset = 0; $offset -le $programBytes.Length - $needle.Length; $offset++) {
        $match = $true
        for ($index = 0; $index -lt $needle.Length; $index++) {
            if ($programBytes[$offset + $index] -ne $needle[$index]) {
                $match = $false
                break
            }
        }
        if ($match) { $found = $true; break }
    }
    if (-not $found) { throw "Bank Maintenance is missing directory-adoption text '$requiredText'" }
}

$expectedWorkerHash = 'FFCDB4201C913FC9B3E3F3D438A98940F76967C5E62F843A2DC32CFF1D1AD1B2'
[byte[]]$workerBytes = 0x3400..0x362A | ForEach-Object { $data[$_] }
$workerSha = [System.Security.Cryptography.SHA256]::Create()
$workerHash = [BitConverter]::ToString($workerSha.ComputeHash($workerBytes)).Replace('-', '')
if ($workerHash -ne $expectedWorkerHash) {
    throw "Private mutation worker hash $workerHash; expected $expectedWorkerHash"
}

$addresses = $orderedAddresses
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash
Write-Host 'BANK MAINT S19      = PASS'
Write-Host ('S1 RECORDS          = {0}' -f $dataRecords)
Write-Host ('DATA BYTES          = {0}' -f $data.Count)
Write-Host ('ADDRESS SPAN        = ${0:X4}-${1:X4}' -f $addresses[0], $addresses[-1])
Write-Host ('S9 EXECUTION        = ${0:X4}' -f $expectedEntry)
Write-Host ('PRIVATE WORKER      = {0}' -f $workerHash)
Write-Host ('SHA256              = {0}' -f $hash)
