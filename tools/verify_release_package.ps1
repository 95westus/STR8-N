param([string]$Root = $PSScriptRoot)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$rootFull = [IO.Path]::GetFullPath($Root)
$sumsPath = Join-Path $rootFull 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) { throw 'SHA256SUMS.txt is missing' }

$required = @(
    'ARTIFACTS/str8n-v1.33-bank3-f000-ffff.bin',
    'ARTIFACTS/str8n-v1.33-f000.s19',
    'ARTIFACTS/str8n-v1.33-bank-maint-2000.s19',
    'ARTIFACTS/str8n-v1.33-bank-maint-menu-2000.s19',
    'ARTIFACTS/str8n-v1.33-top-update-2000.s19',
    'ARTIFACTS/str8n-v1.33-directory-refresh-2000.s19',
    'ARCHIVE/TESTS/str8n-v1.33-console-abi-test-2000.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19',
    'OPTIONAL/HIMON-ASM/INSTALL.md',
    'SOFTWARE/README.md',
    'SOFTWARE/GAMES/life-2000.s19',
    'SOFTWARE/DEMOS/pia-led-show-2000.s19',
    'SOFTWARE/UTILITIES/bank-audit-2000.s19',
    'SOFTWARE/UTILITIES/bank-dump-2000.s19',
    'SOFTWARE/ASM-SOURCES/asm-session-report-ap-2000.a',
    'SOFTWARE/ASM-SOURCES/bank-audit-2000.a',
    'SOFTWARE/ASM-SOURCES/bank-crc-all-3000.a',
    'SOFTWARE/ASM-SOURCES/bank-dump-2000.a',
    'SOFTWARE/ASM-SOURCES/flash-bank-dump-ap-2000.a',
    'SOFTWARE/ASM-SOURCES/flash-bank-read-ap-2000.a',
    'SOFTWARE/ASM-SOURCES/pia-led-show-2000.a',
    'SOFTWARE/ASM-SOURCES/terminal-answerback-vt100-3000.a',
    'SOFTWARE/ASM-SOURCES/vt102-exerciser-7000.a',
    'SOFTWARE/ASM-SOURCES/vt525-exerciser-7000.a',
    'SOFTWARE/ADVANCED/APMAN/apman-7000.s19',
    'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.s19',
    'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.bin',
    'SOFTWARE/ADVANCED/APMAN/apman-v1.ap',
    'SOFTWARE/ADVANCED/APMAN/APMAN_V1_BOARD_TEST.md',
    'SOFTWARE/ADVANCED/AP-STORE/ap-store-v1-chain-install-tool-package-4000.s19',
    'SOFTWARE/ADVANCED/AP-STORE/ap-store-v1-slice6-catalog-tool-package-4000.s19',
    'SOFTWARE/UTILITIES/BANK_AUDIT_AP_CARD.md',
    'SOFTWARE/UTILITIES/BANK_DUMP_AP_CARD.md',
    'MANIFEST/str8n-manifest.json',
    'DOC/STR8N_V1_30_RECLAIM.md',
    'DOC/STR8N_CONSERVATIVE_RESIDENT_PASS.md',
    'DOC/STR8N_CONSERVATIVE_BOARD_TRANSCRIPT.txt',
    'DOC/STR8N_V1_30_BOARD_TRANSCRIPT.txt',
    'DOC/LED_STATUS_PROPOSAL.md',
    'DOC/LED_STATUS_BOARD_TEST_2026-09-06.md',
    'DOC/LED_STATUS_BOARD_TRANSCRIPT_2026-09-06.txt',
    'DOC/LED_HOST_PRESENCE_BOARD_TEST_2026-09-06.md',
    'DOC/LED_HOST_PRESENCE_BOARD_TRANSCRIPT_2026-09-06.txt',
    'DOC/LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md',
    'DOC/LED_IO_ACTIVITY_BOARD_TRANSCRIPT_2026-09-06.txt',
    'DOC/STR8N_V1_31_VERSION_BOARD_TEST_2026-09-06.md',
    'DOC/STR8N_V1_31_VERSION_BOARD_TRANSCRIPT_2026-09-06.txt',
    'DOC/STR8N_V1_32_RESET_SOURCE_BOARD_TEST_2026-09-07.md',
    'DOC/STR8N_V1_32_RESET_SOURCE_BOARD_TRANSCRIPT_2026-09-07.txt',
    'DOC/STR8N_V1_33_TOP_UPDATE_BOARD_TEST_2026-09-10.md',
    'DOC/STR8N_V1_33_TOP_UPDATE_BOARD_TRANSCRIPT_2026-09-10.txt',
    'DOC/RESET_SOURCE_CONTRACT.md',
    'PACKAGES/str8n-v1.33-wdcmonv2-str8n-migration-kit.zip',
    'PACKAGE-README.txt', 'SHA256SUMS.txt'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $rootFull $relative) -PathType Leaf)) {
        throw "Required release file is missing: $relative"
    }
}

foreach ($line in Get-Content -LiteralPath $sumsPath) {
    if ($line -notmatch '^([0-9A-F]{64})  (.+)$') { throw "Invalid checksum row: $line" }
    $path = Join-Path $rootFull $Matches[2]
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Checksummed file is missing: $($Matches[2])" }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne $Matches[1]) {
        throw "Checksum mismatch: $($Matches[2])"
    }
}

function Assert-S19Contract {
    param(
        [string]$RelativePath,
        [int]$ExpectedStart,
        [int]$ExpectedEnd,
        [int]$ExpectedEntry
    )
    $first = 0x10000
    $last = -1
    $entry = -1
    $dataBytes = 0
    foreach ($line in Get-Content -LiteralPath (Join-Path $rootFull $RelativePath)) {
        if ($line.StartsWith('S1')) {
            $count = [Convert]::ToInt32($line.Substring(2, 2), 16)
            $address = [Convert]::ToInt32($line.Substring(4, 4), 16)
            $length = $count - 3
            $first = [Math]::Min($first, $address)
            $last = [Math]::Max($last, $address + $length - 1)
            $dataBytes += $length
        } elseif ($line.StartsWith('S9')) {
            if ($entry -ge 0) { throw "Duplicate S9 record: $RelativePath" }
            $entry = [Convert]::ToInt32($line.Substring(4, 4), 16)
        }
    }
    $expectedBytes = $ExpectedEnd - $ExpectedStart + 1
    if ($first -ne $ExpectedStart -or $last -ne $ExpectedEnd -or
            $dataBytes -ne $expectedBytes -or $entry -ne $ExpectedEntry) {
        throw ('Optional S19 contract failed for {0}: range=${1:X4}-${2:X4}, bytes={3}, S9=${4:X4}' -f
            $RelativePath, $first, $last, $dataBytes, $entry)
    }
}

Assert-S19Contract 'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19' 0xC000 0xEFFF 0xC000
Assert-S19Contract 'OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19' 0x8000 0xBFFF 0x8000
Assert-S19Contract 'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19' 0x8000 0xEFFF 0xC000
Assert-S19Contract 'SOFTWARE/GAMES/life-2000.s19' 0x2000 0x2D7A 0x2000
Assert-S19Contract 'SOFTWARE/DEMOS/pia-led-show-2000.s19' 0x2000 0x2083 0x2000
Assert-S19Contract 'SOFTWARE/UTILITIES/bank-audit-2000.s19' 0x2000 0x2201 0x2000
Assert-S19Contract 'SOFTWARE/UTILITIES/bank-dump-2000.s19' 0x2000 0x292B 0x2000
Assert-S19Contract 'SOFTWARE/ADVANCED/APMAN/apman-7000.s19' 0x7000 0x7B11 0x7000
Assert-S19Contract 'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.s19' 0x8000 0x8FFF 0x8000

$asmSourceDir = Join-Path $rootFull 'SOFTWARE/ASM-SOURCES'
$asmSources = @(Get-ChildItem -LiteralPath $asmSourceDir -File -Filter '*.a')
if ($asmSources.Count -ne 10) {
    throw "SOFTWARE/ASM-SOURCES must contain exactly 10 maintained .a files; found $($asmSources.Count)"
}
foreach ($source in $asmSources) {
    foreach ($line in Get-Content -LiteralPath $source.FullName) {
        $code = ($line -split ';', 2)[0]
        if ($code.Length -gt 63) {
            throw "ASM-F2 code line exceeds 63 characters in $($source.Name): $code"
        }
    }
}
$vt100 = Get-Content -Raw -LiteralPath (Join-Path $asmSourceDir 'terminal-answerback-vt100-3000.a')
if ($vt100 -match 'STR8-N 1\.22' -or $vt100 -notmatch 'STR8-N 1\.29') {
    throw 'VT100 answerback source must retain its STR8-N 1.29 compatible-console provenance'
}

if ((Get-Item -LiteralPath (Join-Path $rootFull 'ARTIFACTS/str8n-v1.33-bank3-f000-ffff.bin')).Length -ne 4096) {
    throw 'Canonical top BIN is not exactly 4096 bytes'
}
$packageReadme = Get-Content -Raw -LiteralPath (Join-Path $rootFull 'PACKAGE-README.txt')
foreach ($text in @('follow the screen', 'CTRL+U and CTRL+D send different',
        'press each once and only when requested', 'After J0, physical',
        'RESET is the designed return')) {
    if (-not $packageReadme.Contains($text)) { throw "Package README lacks operator guidance: $text" }
}
$allowedBankImages = @(
    [IO.Path]::GetFullPath((Join-Path $rootFull 'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.s19')),
    [IO.Path]::GetFullPath((Join-Path $rootFull 'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.bin'))
)
$forbidden = Get-ChildItem -LiteralPath $rootFull -Recurse -File |
    Where-Object {
        $_.FullName -match '(?i)[\\/](LOCAL|R-YORS|HIMON|ASM-F2)[\\/]' -or
        ($_.Name -match '(?i)bank[0-2].*\.(bin|s19)$' -and $_.FullName -notin $allowedBankImages)
    }
if ($forbidden) { throw "Forbidden payload or local evidence found: $($forbidden.FullName -join ', ')" }

Write-Host 'STR8-N v1.33 release package verification PASS'
