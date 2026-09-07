param(
    [string]$KitDirectory = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

if (-not (Test-Path -LiteralPath $KitDirectory -PathType Container)) { throw "Migration kit directory missing: $KitDirectory" }
$root = (Resolve-Path -LiteralPath $KitDirectory).Path.TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$actual = @(Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {
    $_.FullName.Substring($root.Length + 1).Replace([System.IO.Path]::DirectorySeparatorChar, '/')
} | Sort-Object)
if (($actual -join "`n") -ne ($expected -join "`n")) { throw 'Migration kit file allowlist mismatch' }

$manifest = Get-Content -Raw -LiteralPath (Join-Path $root 'PACKAGE-MANIFEST.json') | ConvertFrom-Json
if ($manifest.schema -ne 1 -or
    $manifest.stockWdcmonv2FirmwareIncluded -ne $false -or
    $manifest.localBankArchivesIncluded -ne $false -or
    $manifest.ryorsPayloadIncluded -ne $false -or
    $manifest.windowsHostStatus -notmatch 'board-proven' -or
    $manifest.ubuntuPythonHostStatus -notmatch 'no board proof' -or
    $manifest.archiveRoot -ne 'STR8-N-v1.32-Migration-Kit') {
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
$quick = Get-Content -Raw -LiteralPath (Join-Path $root 'STR8-iN65-LOADER.ps1')
foreach ($required in @('STR8-iN/65 LOADER - FAST PATH', 'STR8-N-v1-30.bin',
        'READ THE SCREEN', 'CTRL+U once', 'CTRL+D once', 'J0 is a complete handoff',
        'Physical RESET is the designed return', 'not a flaw', 'ADOPT B0', 'J0', '[switch]$Details')) {
    if (-not $quick.Contains($required)) { throw "One-command wrapper lacks required handoff text: $required" }
}
$pythonQuick = Get-Content -Raw -LiteralPath (Join-Path $root 'STR8-iN65-LOADER.py')
foreach ($required in @('UNTESTED ON LINUX HARDWARE', 'Windows 11 PowerShell remains the board-proven reference',
        'COPY B3 TO B0', 'INSTALL STR8-N 1.32', 'READ THE SCREEN', 'CTRL+U once',
        'CTRL+D once', 'J0 is a complete handoff', 'Physical RESET is the designed return',
        'not a flaw', 'ADOPT B0')) {
    if (-not $pythonQuick.Contains($required)) { throw "Experimental Python wrapper lacks required safety text: $required" }
}
$quickStart = Get-Content -Raw -LiteralPath (Join-Path $root 'QUICKSTART.txt')
foreach ($required in @('COPY B3 TO B0', 'INSTALL STR8-N 1.32', 'PROPOSED D0 B3:$FFB0',
        'D0 FF WDCV2 FFFF FCFFFFFF', '-Details', 'Windows PowerShell 5.1',
        '[System.IO.Ports.SerialPort]::GetPortNames()', 'UBUNTU LINUX HOST',
        'NOT BOARD-TESTED', 'STR8-iN65-LOADER.py', 'Python 3 + pySerial',
        'PowerShell 7', 'Self-contained Linux executable', 'READ THE SCREEN AS YOU GO',
        'Ctrl+U and Ctrl+D send different packaged files', 'physical RESET button',
        'intentional and by design', 'not a flaw')) {
    if (-not $quickStart.Contains($required)) { throw "Quick-start card lacks required fast-path text: $required" }
}
$packageReadme = Get-Content -Raw -LiteralPath (Join-Path $root 'PACKAGE-README.txt')
foreach ($required in @('Windows PowerShell 5.1', 'USB COM-port driver',
        'writable folder', 'NOT NEEDED', 'powershell.exe', 'UBUNTU PYTHON UNTESTED',
        'ARCHIVE ROOT: STR8-N-v1.32-Migration-Kit', 'READ THE SCREEN',
        'CTRL+U and CTRL+D send different packaged files',
        'physical RESET is the designed return', 'intentional, not a flaw')) {
    if (-not $packageReadme.Contains($required)) { throw "Package README lacks Windows requirement: $required" }
}
& $loader -SelfTest
& $loader -ImagePath (Join-Path $root 'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19') -ValidateOnly
& $loader -ImagePath (Join-Path $root 'ARTIFACTS/STR8-iN65-LOADER-2000.s19') -ValidateOnly

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { throw 'Python is required to run the packaged experimental-loader offline checks' }
& $python.Source (Join-Path $root 'TOOLS/start_wdcmonv2_ram.py') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Python WDCMONv2 protocol self-test failed' }
& $python.Source (Join-Path $root 'TOOLS/start_wdcmonv2_ram.py') --validate-image (Join-Path $root 'ARTIFACTS/STR8-iN65-LOADER-2000.s19')
if ($LASTEXITCODE -ne 0) { throw 'Python WDCMONv2 S19 validation failed' }
& $python.Source (Join-Path $root 'TOOLS/start_wdcmonv2_ram.py') --validate-image (Join-Path $root 'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19')
if ($LASTEXITCODE -ne 0) { throw 'Python WDCMONv2 archive S19 validation failed' }
& $python.Source (Join-Path $root 'STR8-iN65-LOADER.py') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Python consumer-wrapper self-test failed' }

Write-Host ('MIGRATION KIT       = VERIFIED; {0} allowlisted files' -f $expected.Count)
Write-Host 'WDCMONV2 FIRMWARE    = NOT INCLUDED'
Write-Host 'LOCAL BANK ARCHIVES  = NOT INCLUDED'
Write-Host 'R-YORS PAYLOAD        = NOT INCLUDED'
Write-Host 'HARDWARE STATUS      = V1.32 FACTORY MIGRATION OPERATOR-DEFERRED'
