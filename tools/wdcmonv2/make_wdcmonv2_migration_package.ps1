param(
    [string]$ArchiveS19Path = 'BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-archive-2000.s19',
    [string]$InstallS19Path = 'BUILD/v1.23/s19/str8n-v1.23-wdcmonv2-install-2000.s19',
    [string]$CandidateBinPath = 'BUILD/v1.23/bin/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin',
    [string]$InstallIncludePath = 'BUILD/v1.23/generated/str8n-v1.23-wdcmonv2-install-image.inc',
    [string]$RyorsS19Path = '../R-YORS/SRC/BUILD/s19/ryors-v1.2-himon-asm-bank3-8-e.s19',
    [string]$KitDirectory = 'BUILD/v1.23/wdcmonv2-ryors-migration-kit',
    [string]$ZipPath = 'BUILD/v1.23/str8n-v1.23-wdcmonv2-ryors-migration-kit.zip'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

$inputs = [ordered]@{
    'ARTIFACTS/str8n-v1.23-wdcmonv2-archive-2000.s19' = $ArchiveS19Path
    'ARTIFACTS/str8n-v1.23-wdcmonv2-install-2000.s19' = $InstallS19Path
    'ARTIFACTS/str8n-v1.23-wdcmonv2-bank3-f000-ffff.bin' = $CandidateBinPath
    'ARTIFACTS/ryors-v1.2-himon-asm-bank3-8-e.s19' = $RyorsS19Path
    'SOURCE/wdcmonv2str8n-archive-2000.asm' = 'tools/wdcmonv2/wdcmonv2str8n-archive-2000.asm'
    'SOURCE/wdcmonv2str8n-install-2000.asm' = 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm'
    'SOURCE/str8n-v1.23-wdcmonv2-install-image.inc' = $InstallIncludePath
    'TOOLS/extract_wdcmonv2_archive.ps1' = 'tools/wdcmonv2/extract_wdcmonv2_archive.ps1'
    'TOOLS/check_wdcmonv2_archive.ps1' = 'tools/wdcmonv2/check_wdcmonv2_archive.ps1'
    'TOOLS/check_wdcmonv2_install.ps1' = 'tools/wdcmonv2/check_wdcmonv2_install.ps1'
    'TOOLS/start_wdcmonv2_ram.ps1' = 'tools/wdcmonv2/start_wdcmonv2_ram.ps1'
    'VERIFY-PACKAGE.ps1' = 'tools/wdcmonv2/verify_wdcmonv2_migration_kit.ps1'
    'DOC/WDCMONV2_MIGRATION.md' = 'docs/WDCMONV2_MIGRATION.md'
    'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md' = 'docs/WDCMONV2_MIGRATION_BOARD_TEST.md'
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md' = 'docs/WDCMONV2_MIGRATION_PROVENANCE.md'
    'LICENSE' = 'LICENSE'
}

foreach ($source in $inputs.Values) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Migration package input is missing: $source"
    }
}

$buildRoot = Get-FullPath -Path 'BUILD'
$kitFull = Get-FullPath -Path $KitDirectory
$zipFull = Get-FullPath -Path $ZipPath
$buildPrefix = $buildRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $kitFull.StartsWith($buildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Kit directory must remain below BUILD: $kitFull"
}
if (-not $zipFull.StartsWith($buildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "ZIP path must remain below BUILD: $zipFull"
}

if (Test-Path -LiteralPath $kitFull) {
    Remove-Item -LiteralPath $kitFull -Recurse -Force
}
New-Item -ItemType Directory -Path $kitFull | Out-Null

foreach ($item in $inputs.GetEnumerator()) {
    $destination = Join-Path $kitFull ($item.Key.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $item.Value -Destination $destination
}

$readmePath = Join-Path $kitFull 'PACKAGE-README.txt'
$readme = @(
    'WDC W65C02SXB (+ OPTIONAL W65C02EDU) -> STR8-N/R-YORS MIGRATION KIT',
    '',
    'STATUS: HOST-QUALIFIED; STOCK-BOARD TRANSCRIPT PENDING',
    '',
    'Start with DOC/WDCMONV2_MIGRATION_BOARD_TEST.md Phase A.',
    'Archive both Bank 0 and Bank 3 before running the write-capable installer.',
    '',
    'This package contains no WDCMONv2 firmware and no locally extracted bank image.',
    'The operator supplies a stock board and retains its owner archive locally.',
    'Do not redistribute owner archive BIN/S19/receipt files with this kit.',
    'See DOC/WDCMONV2_MIGRATION_PROVENANCE.md for the source and release boundary.',
    '',
    'After extracting the ZIP, run:',
    '  powershell -NoProfile -ExecutionPolicy Bypass -File .\VERIFY-PACKAGE.ps1',
    '',
    'The documented stock-board entry command uses TOOLS/start_wdcmonv2_ram.ps1.',
    'It speaks binary WDCMONv2, verifies RAM byte-for-byte, executes, and stays',
    'on the same open COM handle as the ASCII terminal/capture front end.',
    'Each -TranscriptPath also creates a separate .events.txt host-action log; keep both.'
)
[System.IO.File]::WriteAllLines($readmePath, $readme, [System.Text.Encoding]::ASCII)

$payloadFiles = Get-ChildItem -LiteralPath $kitFull -Recurse -File | Sort-Object FullName
$fileRows = foreach ($file in $payloadFiles) {
    $relative = $file.FullName.Substring($kitFull.Length + 1).Replace([System.IO.Path]::DirectorySeparatorChar, '/')
    [ordered]@{
        file = $relative
        bytes = $file.Length
        sha256 = Get-Sha256 -Path $file.FullName
    }
}
$manifest = [ordered]@{
    schema = 1
    package = 'str8n-v1.23-wdcmonv2-ryors-migration-kit'
    hardwareStatus = 'host-qualified; stock-board transcript pending'
    stockWdcmonv2FirmwareIncluded = $false
    localBankArchivesIncluded = $false
    firstProcedure = 'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md Phase A'
    files = @($fileRows)
}
$manifestPath = Join-Path $kitFull 'PACKAGE-MANIFEST.json'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5) + [Environment]::NewLine, $utf8NoBom)

$zipParent = Split-Path -Parent $zipFull
New-Item -ItemType Directory -Force -Path $zipParent | Out-Null
if (Test-Path -LiteralPath $zipFull) { Remove-Item -LiteralPath $zipFull -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stream = [System.IO.File]::Open($zipFull, [System.IO.FileMode]::CreateNew)
try {
    $zip = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($file in (Get-ChildItem -LiteralPath $kitFull -Recurse -File | Sort-Object FullName)) {
            $relative = $file.FullName.Substring($kitFull.Length + 1).Replace([System.IO.Path]::DirectorySeparatorChar, '/')
            $entry = $zip.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = [System.DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [System.TimeSpan]::Zero)
            $input = [System.IO.File]::OpenRead($file.FullName)
            $output = $entry.Open()
            try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
        }
    } finally {
        $zip.Dispose()
    }
} finally {
    $stream.Dispose()
}

Write-Host ('MIGRATION KIT DIR   = {0}' -f $kitFull)
Write-Host ('MIGRATION KIT ZIP   = {0}' -f $zipFull)
Write-Host ('MIGRATION ZIP SHA256= {0}' -f (Get-Sha256 -Path $zipFull))
Write-Host 'WDC FIRMWARE         = NOT INCLUDED'
Write-Host 'LOCAL BANK ARCHIVES  = NOT INCLUDED'
