param(
    [string]$KitDirectory = 'BUILD/v1.32/wdcmonv2-str8n-migration-kit',
    [string]$ZipPath = 'BUILD/v1.32/str8n-v1.32-wdcmonv2-str8n-migration-kit.zip',
    [string]$ArchiveS19Path = 'BUILD/v1.32/s19/str8n-v1.32-wdcmonv2-archive-2000.s19',
    [string]$InstallS19Path = 'BUILD/v1.32/s19/str8n-v1.32-wdcmonv2-install-2000.s19',
    [string]$TopBinPath = 'BUILD/v1.32/bin/str8n-v1.32-bank3-f000-ffff.bin',
    [string]$CandidateBinPath = 'BUILD/v1.32/bin/str8n-v1.32-bank3-f000-ffff.bin',
    [string]$CanonicalS19Path = 'BUILD/v1.32/s19/str8n-v1.32-f000.s19',
    [string]$BankMaintS19Path = 'BUILD/v1.32/s19/str8n-v1.32-str8-in65-bank-maint-2000.s19',
    [string]$HostBridgePath = 'tools/wdcmonv2/start_wdcmonv2_ram.ps1',
    [string]$BoardTestPath = 'docs/WDCMONV2_MIGRATION_BOARD_TEST.md',
    [string]$ArchiveRootName = 'STR8-N-v1.32-Migration-Kit'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Assert-DocumentedHash {
    param(
        [Parameter(Mandatory = $true)][string]$Document,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Documented artifact missing: $Path" }
    $pattern = '(?m)^' + [regex]::Escape($Label) + '\r?\nSHA-256 ([0-9A-F]{64})$'
    $match = [regex]::Match($Document, $pattern)
    if (-not $match.Success) { throw "Board card lacks an exact SHA-256 row for: $Label" }
    $actualHash = Get-Sha256 -Path $Path
    if ($match.Groups[1].Value -ne $actualHash) {
        throw "Board card SHA-256 is stale for ${Label}: documented=$($match.Groups[1].Value), actual=$actualHash"
    }
}

if (-not (Test-Path -LiteralPath $BoardTestPath -PathType Leaf)) { throw "Board test missing: $BoardTestPath" }

$expected = @(
    'STR8-iN65-LOADER.ps1',
    'STR8-iN65-LOADER.py',
    'QUICKSTART.txt',
    'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19',
    'ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19',
    'ARTIFACTS/STR8-iN65-LOADER-2000.s19',
    'ARTIFACTS/STR8-N-v1-30.bin',
    'ARTIFACTS/STR8-N-v1-30.s19',
    'DOC/HIMON_ASMF2_AFTER_STR8N.md',
    'DOC/STR8_IN65_BANK_MAINTENANCE.md',
    'DOC/WDCMONV2_MIGRATION.md',
    'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md',
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md',
    'LICENSE',
    'PACKAGE-MANIFEST.json',
    'PACKAGE-README.txt',
    'SOURCE/str8n-v1.32-wdcmonv2-install-image.inc',
    'SOURCE/wdcmonv2str8n-archive-2000.asm',
    'SOURCE/wdcmonv2str8n-install-2000.asm',
    'TOOLS/check_wdcmonv2_archive.ps1',
    'TOOLS/check_wdcmonv2_install.ps1',
    'TOOLS/extract_wdcmonv2_archive.ps1',
    'TOOLS/start_wdcmonv2_ram.ps1',
    'TOOLS/start_wdcmonv2_ram.py',
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
if ($manifest.ryorsPayloadIncluded -ne $false) { throw 'Manifest must state that no R-YORS payload is included' }
if ($manifest.windowsHostStatus -notmatch 'board-proven') { throw 'Manifest must retain Windows host proof status' }
if ($manifest.ubuntuPythonHostStatus -notmatch 'no board proof') { throw 'Manifest must mark Ubuntu Python as lacking board proof' }
if ($manifest.archiveRoot -ne $ArchiveRootName) { throw 'Manifest archive root does not match the required surrounding folder' }
if ($manifest.hardwareStatus -ne 'v1.32 factory migration board-accepted on SXB2 HW 3.00 WDCMON 2.00 BF/B5 flash, COM4, 2026-09-08; operator-confirmed F0') {
    throw 'Manifest must publish the accepted v1.32 factory-migration board proof'
}
if ($manifest.firstProcedure -notmatch 'STR8-iN65-LOADER') { throw 'Manifest must publish the one-command factory path first' }

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
    'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19' = $ArchiveS19Path
    'ARTIFACTS/STR8-iN65-LOADER-2000.s19' = $InstallS19Path
    'ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19' = $BankMaintS19Path
    'ARTIFACTS/STR8-N-v1-30.bin' = $CandidateBinPath
    'ARTIFACTS/STR8-N-v1-30.s19' = $CanonicalS19Path
}
foreach ($item in $identity.GetEnumerator()) {
    if (-not (Test-Path -LiteralPath $item.Value -PathType Leaf)) { throw "Expected source artifact missing: $($item.Value)" }
    $packaged = Join-Path $kitFull ($item.Key.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    if ((Get-Sha256 -Path $packaged) -ne (Get-Sha256 -Path $item.Value)) {
        throw "Packaged artifact differs from verified build input: $($item.Key)"
    }
}
if ((Get-Item -LiteralPath (Join-Path $kitFull 'ARTIFACTS/STR8-N-v1-30.bin')).Length -ne 4096) {
    throw 'The only packaged BIN must be the exact canonical 4K STR8-N image'
}

foreach ($name in $actual) {
    if ($name -eq 'ARTIFACTS/STR8-N-v1-30.bin') { continue }
    if ($name -match '(?i)(capture|receipt|stock[-_]?b[0-3]|wdcmonv2-bank[0-3])' -or $name -match '(?i)\.bin$') {
        throw "Package contains a forbidden owner/archive-looking file: $name"
    }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ZipPath).Path)
try {
    $zipNames = @($zip.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object)
    $expectedZipNames = @($expected | ForEach-Object { $ArchiveRootName + '/' + $_ } | Sort-Object)
    if (($zipNames -join "`n") -ne ($expectedZipNames -join "`n")) { throw 'ZIP entry allowlist or surrounding folder differs from staged package' }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        foreach ($entry in $zip.Entries) {
            if (-not $entry.Name) { continue }
            $input = $entry.Open()
            try { $zipHash = ([BitConverter]::ToString($sha.ComputeHash($input))).Replace('-', '') } finally { $input.Dispose() }
            $prefix = $ArchiveRootName + '/'
            if (-not $entry.FullName.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
                throw "ZIP entry escaped required archive root: $($entry.FullName)"
            }
            $relative = $entry.FullName.Substring($prefix.Length)
            $diskPath = Join-Path $kitFull ($relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
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
Write-Host 'V1.32 FACTORY MIGRATION BOARD PROOF = ACCEPTED; COM4; 2026-09-08; LED F0 CONFIRMED'
