param([string]$Root = $PSScriptRoot)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$rootFull = [IO.Path]::GetFullPath($Root)
$sumsPath = Join-Path $rootFull 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) { throw 'SHA256SUMS.txt is missing' }

$required = @(
    'ARTIFACTS/str8n-v1.29-bank3-f000-ffff.bin',
    'ARTIFACTS/str8n-v1.29-f000.s19',
    'ARTIFACTS/str8n-v1.29-bank-maint-2000.s19',
    'ARTIFACTS/str8n-v1.29-bank-maint-menu-2000.s19',
    'ARTIFACTS/str8n-v1.29-top-update-2000.s19',
    'ARTIFACTS/str8n-v1.29-directory-refresh-2000.s19',
    'ARCHIVE/TESTS/str8n-v1.29-console-abi-test-2000.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19',
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19',
    'OPTIONAL/HIMON-ASM/INSTALL.md',
    'MANIFEST/str8n-manifest.json',
    'PACKAGES/str8n-v1.29-wdcmonv2-str8n-migration-kit.zip',
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

if ((Get-Item -LiteralPath (Join-Path $rootFull 'ARTIFACTS/str8n-v1.29-bank3-f000-ffff.bin')).Length -ne 4096) {
    throw 'Canonical top BIN is not exactly 4096 bytes'
}
$packageReadme = Get-Content -Raw -LiteralPath (Join-Path $rootFull 'PACKAGE-README.txt')
foreach ($text in @('follow the screen', 'CTRL+U and CTRL+D send different',
        'press each once and only when requested', 'After J0, physical',
        'RESET is the designed return')) {
    if (-not $packageReadme.Contains($text)) { throw "Package README lacks operator guidance: $text" }
}
$forbidden = Get-ChildItem -LiteralPath $rootFull -Recurse -File |
    Where-Object { $_.FullName -match '(?i)[\\/](LOCAL|R-YORS|HIMON|ASM-F2)[\\/]' -or $_.Name -match '(?i)bank[0-2].*\.(bin|s19)$' }
if ($forbidden) { throw "Forbidden payload or local evidence found: $($forbidden.FullName -join ', ')" }

Write-Host 'STR8-N v1.29 release package verification PASS'
