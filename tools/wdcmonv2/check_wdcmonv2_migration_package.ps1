param(
    [string]$KitDirectory = 'BUILD/v1.23/wdcmonv2-ryors-migration-kit',
    [string]$ZipPath = 'BUILD/v1.23/str8n-v1.23-wdcmonv2-ryors-migration-kit.zip',
    [string]$ArchiveS19Path = 'BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-archive-2000.s19',
    [string]$InstallS19Path = 'BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-install-2000.s19',
    [string]$CandidateBinPath = 'BUILD/v1.23/bin/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin',
    [string]$RyorsS19Path = '../R-YORS/SRC/BUILD/s19/ryors-v1.2-himon-asm-bank3-8-e.s19'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

$expected = @(
    'ARTIFACTS/ryors-v1.2-himon-asm-bank3-8-e.s19',
    'ARTIFACTS/str8n-v1.23-wdcmonv2-archive-2000.s19',
    'ARTIFACTS/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin',
    'ARTIFACTS/str8n-v1.23-wdcmonv2-install-2000.s19',
    'DOC/WDCMONV2_MIGRATION.md',
    'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md',
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md',
    'LICENSE',
    'PACKAGE-MANIFEST.json',
    'PACKAGE-README.txt',
    'SOURCE/str8n-v1.23-wdcmonv2-install-image.inc',
    'SOURCE/wdcmonv2str8n-archive-2000.asm',
    'SOURCE/wdcmonv2str8n-install-2000.asm',
    'TOOLS/check_wdcmonv2_archive.ps1',
    'TOOLS/check_wdcmonv2_install.ps1',
    'TOOLS/extract_wdcmonv2_archive.ps1',
    'TOOLS/start_wdcmonv2_ram.ps1',
    'VERIFY-PACKAGE.ps1'
) | Sort-Object

if (-not (Test-Path -LiteralPath $KitDirectory -PathType Container)) { throw "Kit directory missing: $KitDirectory" }
if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) { throw "Kit ZIP missing: $ZipPath" }
$kitFull = (Resolve-Path -LiteralPath $KitDirectory).Path.TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$actual = @(Get-ChildItem -LiteralPath $kitFull -Recurse -File | ForEach-Object {
    $_.FullName.Substring($kitFull.Length + 1).Replace([System.IO.Path]::DirectorySeparatorChar, '/')
} | Sort-Object)
if (($actual -join "`n") -ne ($expected -join "`n")) {
    throw "Migration package allowlist mismatch.`nEXPECTED:`n$($expected -join "`n")`nACTUAL:`n$($actual -join "`n")"
}

$manifestPath = Join-Path $kitFull 'PACKAGE-MANIFEST.json'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.schema -ne 1) { throw 'Migration package manifest schema is not 1' }
if ($manifest.stockWdcmonv2FirmwareIncluded -ne $false) { throw 'Manifest must state that stock WDCMONv2 firmware is absent' }
if ($manifest.localBankArchivesIncluded -ne $false) { throw 'Manifest must state that local bank archives are absent' }
if ($manifest.hardwareStatus -notmatch 'stock-board transcript pending') { throw 'Manifest must retain the pending hardware status' }

$manifestRows = @($manifest.files)
if ($manifestRows.Count -ne ($expected.Count - 1)) { throw 'Manifest payload count does not match package allowlist' }
foreach ($row in $manifestRows) {
    if ($row.file -eq 'PACKAGE-MANIFEST.json') { throw 'Manifest must not attempt to hash itself' }
    $path = Join-Path $kitFull ($row.file.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Manifest names a missing file: $($row.file)" }
    $item = Get-Item -LiteralPath $path
    if ([int64]$row.bytes -ne $item.Length) { throw "Manifest length mismatch: $($row.file)" }
    if ($row.sha256 -ne (Get-Sha256 -Path $path)) { throw "Manifest SHA-256 mismatch: $($row.file)" }
}

$identity = [ordered]@{
    'ARTIFACTS/str8n-v1.23-wdcmonv2-archive-2000.s19' = $ArchiveS19Path
    'ARTIFACTS/str8n-v1.23-wdcmonv2-install-2000.s19' = $InstallS19Path
    'ARTIFACTS/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin' = $CandidateBinPath
    'ARTIFACTS/ryors-v1.2-himon-asm-bank3-8-e.s19' = $RyorsS19Path
}
foreach ($item in $identity.GetEnumerator()) {
    if (-not (Test-Path -LiteralPath $item.Value -PathType Leaf)) { throw "Expected source artifact missing: $($item.Value)" }
    $packaged = Join-Path $kitFull ($item.Key.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    if ((Get-Sha256 -Path $packaged) -ne (Get-Sha256 -Path $item.Value)) {
        throw "Packaged artifact differs from verified build input: $($item.Key)"
    }
}
if ((Get-Item -LiteralPath (Join-Path $kitFull 'ARTIFACTS/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin')).Length -ne 4096) {
    throw 'The only packaged BIN must be the exact 4K STR8-N migration candidate'
}

foreach ($name in $actual) {
    if ($name -eq 'ARTIFACTS/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin') { continue }
    if ($name -match '(?i)(capture|receipt|stock[-_]?b[0-3]|wdcmonv2-bank[0-3])' -or $name -match '(?i)\.bin$') {
        throw "Package contains a forbidden owner/archive-looking file: $name"
    }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ZipPath).Path)
try {
    $zipNames = @($zip.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object)
    if (($zipNames -join "`n") -ne ($expected -join "`n")) { throw 'ZIP entry allowlist differs from staged package' }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        foreach ($entry in $zip.Entries) {
            if (-not $entry.Name) { continue }
            $input = $entry.Open()
            try { $zipHash = ([BitConverter]::ToString($sha.ComputeHash($input))).Replace('-', '') } finally { $input.Dispose() }
            $diskPath = Join-Path $kitFull ($entry.FullName.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
            if ($zipHash -ne (Get-Sha256 -Path $diskPath)) { throw "ZIP payload mismatch: $($entry.FullName)" }
        }
    } finally {
        $sha.Dispose()
    }
} finally {
    $zip.Dispose()
}

Write-Host ('MIGRATION PACKAGE   = PASS; {0} allowlisted files' -f $expected.Count)
Write-Host ('PACKAGE ZIP SHA256  = {0}' -f (Get-Sha256 -Path $ZipPath))
Write-Host 'WDC FIRMWARE/ARCHIVE = ABSENT BY ALLOWLIST'
