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
