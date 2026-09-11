param(
    [string]$ArchiveS19Path = 'BUILD/v1.33/s19/str8n-v1.33-wdcmonv2-archive-2000.s19',
    [string]$InstallS19Path = 'BUILD/v1.33/s19/str8n-v1.33-wdcmonv2-install-2000.s19',
    [string]$CandidateBinPath = 'BUILD/v1.33/bin/str8n-v1.33-bank3-f000-ffff.bin',
    [string]$CanonicalS19Path = 'BUILD/v1.33/s19/str8n-v1.33-f000.s19',
    [string]$BankMaintS19Path = 'BUILD/v1.33/s19/str8n-v1.33-str8-in65-bank-maint-2000.s19',
    [string]$InstallIncludePath = 'BUILD/v1.33/generated/str8n-v1.33-wdcmonv2-install-image.inc',
    [string]$KitDirectory = 'BUILD/v1.33/wdcmonv2-str8n-migration-kit',
    [string]$ZipPath = 'BUILD/v1.33/str8n-v1.33-wdcmonv2-str8n-migration-kit.zip',
    [string]$ArchiveRootName = 'STR8-N-v1.33-Migration-Kit'
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
    'STR8-iN65-LOADER.ps1' = 'tools/wdcmonv2/MIGRATE-WDC-TO-STR8N.ps1'
    'STR8-iN65-LOADER.py' = 'tools/wdcmonv2/MIGRATE-WDC-TO-STR8N.py'
    'QUICKSTART.txt' = 'docs/STR8_IN65_QUICKSTART.txt'
    'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19' = $ArchiveS19Path
    'ARTIFACTS/STR8-iN65-LOADER-2000.s19' = $InstallS19Path
    'ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19' = $BankMaintS19Path
    'ARTIFACTS/STR8-N-v1-30.bin' = $CandidateBinPath
    'ARTIFACTS/STR8-N-v1-30.s19' = $CanonicalS19Path
    'SOURCE/wdcmonv2str8n-archive-2000.asm' = 'tools/wdcmonv2/wdcmonv2str8n-archive-2000.asm'
    'SOURCE/wdcmonv2str8n-install-2000.asm' = 'tools/wdcmonv2/wdcmonv2str8n-install-2000.asm'
    'SOURCE/str8n-v1.33-wdcmonv2-install-image.inc' = $InstallIncludePath
    'TOOLS/extract_wdcmonv2_archive.ps1' = 'tools/wdcmonv2/extract_wdcmonv2_archive.ps1'
    'TOOLS/check_wdcmonv2_archive.ps1' = 'tools/wdcmonv2/check_wdcmonv2_archive.ps1'
    'TOOLS/check_wdcmonv2_install.ps1' = 'tools/wdcmonv2/check_wdcmonv2_install.ps1'
    'TOOLS/start_wdcmonv2_ram.ps1' = 'tools/wdcmonv2/start_wdcmonv2_ram.ps1'
    'TOOLS/start_wdcmonv2_ram.py' = 'tools/wdcmonv2/start_wdcmonv2_ram.py'
    'VERIFY-PACKAGE.ps1' = 'tools/wdcmonv2/verify_wdcmonv2_migration_kit.ps1'
    'DOC/WDCMONV2_MIGRATION.md' = 'docs/WDCMONV2_MIGRATION.md'
    'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md' = 'docs/WDCMONV2_MIGRATION_BOARD_TEST.md'
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md' = 'docs/WDCMONV2_MIGRATION_PROVENANCE.md'
    'DOC/HIMON_ASMF2_AFTER_STR8N.md' = 'docs/HIMON_ASMF2_AFTER_STR8N.md'
    'DOC/STR8_IN65_BANK_MAINTENANCE.md' = 'docs/STR8_IN65_BANK_MAINTENANCE.md'
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
if ([string]::IsNullOrWhiteSpace($ArchiveRootName) -or
        $ArchiveRootName -in @('.', '..') -or
        $ArchiveRootName.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
        $ArchiveRootName.Contains('/') -or $ArchiveRootName.Contains('\')) {
    throw "Archive root must be one safe folder name: $ArchiveRootName"
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
    'WDC W65C02SXB (+ OPTIONAL W65C02EDU) -> STR8-N MIGRATION KIT',
    '',
    'STATUS: v1.33 ARTIFACT HOST-QUALIFIED; v1.32 FACTORY PATH BOARD-ACCEPTED',
    'HOST STATUS: WINDOWS 11 POWERSHELL BOARD-PROVEN; UBUNTU PYTHON UNTESTED',
    ('ARCHIVE ROOT: {0}' -f $ArchiveRootName),
    '',
    'BEFORE YOU START',
    '  NEEDED: Windows 10/11, Windows PowerShell 5.1 (powershell.exe), the',
    '  board USB COM-port driver, this ZIP extracted to a writable folder, a',
    '  free COM port, stable board power, and access to physical RESET.',
    '  NOT NEEDED: Git, Python, make, WDC tools/WDCDB, internet, a T48, or',
    '  administrator rights after the COM-port driver is installed.',
    '  Ubuntu choices and the experimental included Python loader are described',
    '  in QUICKSTART.txt. Linux host operation is not yet board-tested.',
    '',
    'Optional preflight:',
    '  $PSVersionTable.PSVersion',
    '  [System.IO.Ports.SerialPort]::GetPortNames()',
    '',
    'Factory-board minimal path:',
    '  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\STR8-iN65-LOADER.ps1',
    '  Add -Details for hashes, addresses, bank policy, and evidence paths.',
    '  See QUICKSTART.txt for the short operator card.',
    '  READ THE SCREEN. CTRL+U and CTRL+D send different packaged files;',
    '  press each once and only when its corresponding request appears.',
    '',
    'The RAM installer requires separate COPY and INSTALL confirmations.',
    'It copies/verifies stock B3 into B0, receives the canonical STR8-N 1.33',
    'BIN, and installs it in B3:F.',
    'After verified v1.33 boot, the included Bank Maintenance image prompts for',
    'D0 FF WDCV2 adoption; Bank 0 remains an opaque byte-for-byte factory guest.',
    'After J0, physical RESET is the designed return from that factory guest',
    'to STR8-N. This reset-only return is intentional, not a flaw.',
    'See DOC/STR8_IN65_BANK_MAINTENANCE.md for the exact adoption transaction.',
    'The read-only map/dump/archive procedure remains available in the DOC and TOOLS',
    'directories but is not a gate for the factory-board minimal path.',
    '',
    'This package contains no WDCMONv2 firmware and no locally extracted bank image.',
    'The operator supplies a stock board and retains its owner archive locally.',
    'Do not redistribute owner archive BIN/S19/receipt files with this kit.',
    'See DOC/WDCMONV2_MIGRATION_PROVENANCE.md for the source and release boundary.',
    'Migration ends at the STR8-N prompt. No R-YORS payload is included or installed.',
    'Optional later HIMON/ASM-F2 component loading is documented separately in',
    'DOC/HIMON_ASMF2_AFTER_STR8N.md.',
    '',
    'Optional package verification:',
    '  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\VERIFY-PACKAGE.ps1',
    '',
    'The one-command wrapper uses TOOLS/start_wdcmonv2_ram.ps1.',
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
    package = 'str8n-v1.33-wdcmonv2-str8n-migration-kit'
    hardwareStatus = 'v1.33 artifact host-qualified; v1.32 factory migration board-accepted on SXB2 HW 3.00 WDCMON 2.00 BF/B5 flash, COM4, 2026-09-08'
    windowsHostStatus = 'Windows 11 PowerShell board-proven'
    ubuntuPythonHostStatus = 'experimental; offline-tested only; no board proof'
    archiveRoot = $ArchiveRootName
    stockWdcmonv2FirmwareIncluded = $false
    localBankArchivesIncluded = $false
    ryorsPayloadIncluded = $false
    firstProcedure = 'STR8-iN65-LOADER.ps1'
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
            $entryName = $ArchiveRootName + '/' + $relative
            $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
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
