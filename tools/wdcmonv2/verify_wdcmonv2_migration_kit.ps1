param(
    [string]$KitDirectory = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

if (-not (Test-Path -LiteralPath $KitDirectory -PathType Container)) { throw "Migration kit directory missing: $KitDirectory" }
$root = (Resolve-Path -LiteralPath $KitDirectory).Path.TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$actual = @(Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {
    $_.FullName.Substring($root.Length + 1).Replace([System.IO.Path]::DirectorySeparatorChar, '/')
} | Sort-Object)
if (($actual -join "`n") -ne ($expected -join "`n")) { throw 'Migration kit file allowlist mismatch' }

$manifest = Get-Content -Raw -LiteralPath (Join-Path $root 'PACKAGE-MANIFEST.json') | ConvertFrom-Json
if ($manifest.schema -ne 1 -or
    $manifest.stockWdcmonv2FirmwareIncluded -ne $false -or
    $manifest.localBankArchivesIncluded -ne $false) {
    throw 'Migration kit provenance flags are invalid'
}
$rows = @($manifest.files)
if ($rows.Count -ne ($expected.Count - 1)) { throw 'Migration kit manifest payload count mismatch' }
foreach ($row in $rows) {
    $path = Join-Path $root ($row.file.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Manifest file missing: $($row.file)" }
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne [int64]$row.bytes) { throw "Manifest length mismatch: $($row.file)" }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($hash -ne $row.sha256) { throw "Manifest SHA-256 mismatch: $($row.file)" }
}

$loader = Join-Path $root 'TOOLS/start_wdcmonv2_ram.ps1'
& $loader -SelfTest
& $loader -ImagePath (Join-Path $root 'ARTIFACTS/str8n-v1.23-wdcmonv2-archive-2000.s19') -ValidateOnly
& $loader -ImagePath (Join-Path $root 'ARTIFACTS/str8n-v1.23-wdcmonv2-install-2000.s19') -ValidateOnly

Write-Host ('MIGRATION KIT       = VERIFIED; {0} allowlisted files' -f $expected.Count)
Write-Host 'WDCMONV2 FIRMWARE    = NOT INCLUDED'
Write-Host 'LOCAL BANK ARCHIVES  = NOT INCLUDED'
Write-Host 'HARDWARE STATUS      = STOCK-BOARD TRANSCRIPT PENDING'
