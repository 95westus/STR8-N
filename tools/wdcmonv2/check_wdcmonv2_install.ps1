param(
    [string]$SourcePath = 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm',
    [string]$S19Path = 'BUILD/v1.29/s19/str8n-v1.29-wdcmonv2-install-2000.s19',
    [string]$MapPath = 'BUILD/v1.29/s19/str8n-v1.29-wdcmonv2-install-2000.map',
    [string]$TopBinPath = 'BUILD/v1.29/bin/str8n-v1.29-bank3-f000-ffff.bin',
    [string]$CandidateBinPath = 'BUILD/v1.29/bin/str8n-v1.29-bank3-f000-ffff.bin',
    [string]$VersionText = '1.29'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($path in @($SourcePath, $S19Path, $MapPath, $TopBinPath, $CandidateBinPath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing installer component: $path" }
}

$source = Get-Content -Raw -LiteralPath $SourcePath
foreach ($required in @(
    'W2I_FLASH_MAN_EXPECT    EQU             $BF',
    'W2I_FLASH_DEV_EXPECT    EQU             $B5',
    'COPY B3 TO B0', "INSTALL STR8-N $VersionText", 'COPY/VERIFY B3 -> B0',
    'REFUSE: B0 USED AND DIFFERENT', 'W2I_HASH_EQUALS_SOURCE',
    'W2I_COMPARE_B0_B3_EXACT', 'B0/B3 HASH MATCH BUT BYTES DIFFER',
    'W2I_COPY_B3_TO_B0', 'W2I_RECEIVE_CANDIDATE',
    'SEND STR8-N TOP BIN; 4096 BYTES; START $F000',
    'W2I_HASH_CANDIDATE', 'W2I_CANDIDATE_TO_STAGE',
    'W2I_PROGRAM_STAGE', 'W2I_MSG_RECOVERY', 'W2I_MSG_OLD_RESTORED'
)) {
    if (-not $source.Contains($required)) { throw "Installer source lacks required gate: $required" }
}
foreach ($requiredFlash in @('$D555', '$AAAA', '#$90', '#$F0', '#$80', '#$30', '#$A0')) {
    if (-not $source.Contains($requiredFlash)) { throw "Installer source lacks flash sequence token: $requiredFlash" }
}
if ($source -match '(?im)^\s*(JSR|JMP)\s+\$[89A-E][0-9A-F]{3}\b') {
    throw "Installer directly calls banked ROM: $($Matches[0])"
}
if ($source.Contains('W2I_BANK1') -or $source.Contains('W2I_BANK2')) {
    throw 'Seed installer must not consume Bank 1 or Bank 2'
}
$b0PolicyGate = $source.IndexOf('W2I_B0_NOT_EQUAL:')
$copyGate = $source.IndexOf('W2I_COPY_CONFIRMED:')
$b0Gate = $source.IndexOf('W2I_B0_PROVEN:')
$receiveGate = $source.IndexOf('JSR             W2I_RECEIVE_CANDIDATE', $b0Gate)
$installGate = $source.IndexOf('W2I_INSTALL_CONFIRMED:')
if ($b0PolicyGate -lt 0 -or $copyGate -le $b0PolicyGate -or
    $b0Gate -le $copyGate -or
    $receiveGate -le $b0Gate -or $installGate -le $receiveGate) {
    throw 'Installer gate order must be B0 policy -> COPY confirmation -> B0 exact -> receive canonical BIN -> INSTALL confirmation'
}

$map = Get-Content -Raw -LiteralPath $MapPath
if ($map -notmatch '(?im)^\s*00002000\s+START\s*$') { throw 'START is not linked at $2000' }
if ($map -match '(?im)^\s*00004000\s+W2I_CANDIDATE_IMAGE\s*$') {
    throw 'Installer must receive the canonical top BIN; it may not carry a second top image'
}

$memory = New-Object int[] 65536
for ($i = 0; $i -lt $memory.Length; $i++) { $memory[$i] = -1 }
$entry = -1
$minAddress = 0x10000
$maxAddress = -1
foreach ($raw in Get-Content -LiteralPath $S19Path) {
    $line = $raw.Trim()
    if ($line -notmatch '^S([0-9])([0-9A-Fa-f]+)$') { continue }
    $type = $Matches[1]
    $hex = $Matches[2]
    if (($hex.Length -band 1) -ne 0) { throw "Odd S-record hex length: $line" }
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring(2 * $i, 2), 16)
    }
    if ($bytes[0] -ne ($bytes.Length - 1)) { throw "S-record count mismatch: $line" }
    $sum = 0
    foreach ($b in $bytes) { $sum = ($sum + $b) -band 0xFF }
    if ($sum -ne 0xFF) { throw "S-record checksum mismatch: $line" }
    if ($type -eq '1') {
        $address = ([int]$bytes[1] -shl 8) -bor [int]$bytes[2]
        $length = [int]$bytes[0] - 3
        for ($i = 0; $i -lt $length; $i++) {
            $at = $address + $i
            if ($memory[$at] -ge 0 -and $memory[$at] -ne $bytes[3 + $i]) {
                throw ('Conflicting S1 data at ${0:X4}' -f $at)
            }
            $memory[$at] = $bytes[3 + $i]
        }
        $minAddress = [Math]::Min($minAddress, $address)
        $maxAddress = [Math]::Max($maxAddress, $address + $length - 1)
    } elseif ($type -eq '9') {
        if ($bytes[0] -ne 3) { throw 'S9 count must be 3' }
        $entry = ([int]$bytes[1] -shl 8) -bor [int]$bytes[2]
    }
}
if ($minAddress -ne 0x2000 -or $maxAddress -ge 0x4000 -or $entry -ne 0x2000) {
    throw ('Installer RAM contract failed: range=${0:X4}-${1:X4}, S9=${2:X4}' -f $minAddress, $maxAddress, $entry)
}
for ($address = 0x2000; $address -le $maxAddress; $address++) {
    if ($memory[$address] -lt 0) { throw ('Installer S19 is not dense at ${0:X4}' -f $address) }
}

[byte[]]$top = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $TopBinPath).Path)
if ($top.Length -ne 4096) { throw "Top BIN must be 4096 bytes; got $($top.Length)" }
[byte[]]$candidate = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $CandidateBinPath).Path)
if ($candidate.Length -ne 4096) { throw "External candidate BIN must be 4096 bytes; got $($candidate.Length)" }
for ($i = 0; $i -lt $top.Length; $i++) {
    if ($candidate[$i] -ne $top[$i]) {
        throw ('External candidate BIN differs from canonical top at offset ${0:X3}' -f $i)
    }
}
if ($top[0] -ne 0x4C -or ($top[0x0FFC] -eq 0xFF -and $top[0x0FFD] -eq 0xFF)) {
    throw 'External STR8-N top lacks its JMP face or RESET vector'
}
for ($offset = 0x0FB0; $offset -le 0x0FEF; $offset++) {
    if ($candidate[$offset] -ne 0xFF) {
        throw ('Canonical top must leave the Bank-3 directory empty at ${0:X4}' -f (0xF000 + $offset))
    }
}

Write-Host ('WDCMONV2 LOADER S19  = PASS; range=${0:X4}-${1:X4}; S9=$2000; no embedded top' -f $minAddress, $maxAddress)
Write-Host ('EXTERNAL STR8-N BIN  = PASS; exact canonical 4096-byte top; SHA256={0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $CandidateBinPath).Hash)
Write-Host 'GATE ORDER           = B0 POLICY -> COPY -> B0 EXACT -> RECEIVE BIN -> INSTALL; B1/B2 untouched'
