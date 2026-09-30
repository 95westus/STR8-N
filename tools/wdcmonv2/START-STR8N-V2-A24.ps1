param(
    [string]$Port,
    [ValidateSet('Auto', 'SXB?', 'SXB2', 'SXB3', 'SXB6')][string]$ExpectedBoardTag = 'SXB?',
    [int]$PhysicalResetArmSeconds = 60,
    [string]$TranscriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$kit = $PSScriptRoot
$bridge = Join-Path $kit 'TOOLS/start_wdcmonv2_ram.ps1'
$installer = Join-Path $kit 'FIRMWARE/str8n-v2-alpha24-wdcmonv2-install-2000.s19'
$candidate = Join-Path $kit 'FIRMWARE/str8n-v2-alpha24-f000-ffff.bin'
foreach ($path in @($bridge, $installer, $candidate)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Candidate package file missing: $path" }
}
if ((Get-Item -LiteralPath $candidate).Length -ne 4096) { throw 'Top BIN must be 4096 bytes' }
$expected = '43E6EE966963E1CC401986581742CC75B302CD0A02CFAF22965FE7AB8A43EC1A'
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash -ne $expected) {
    throw 'Top BIN does not match the qualified a24 candidate'
}
if ($PhysicalResetArmSeconds -lt 0 -or $PhysicalResetArmSeconds -gt 120) {
    throw '-PhysicalResetArmSeconds must be 0..120'
}
if (-not $Port) {
    $ports = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
    if ($ports.Count -eq 0) { throw 'No serial ports were found' }
    Write-Host ('Available ports: {0}' -f ($ports -join ', '))
    $Port = Read-Host 'Enter the stock-board COM port'
    if ($ports -notcontains $Port) { throw "Port is not present: $Port" }
}
if (-not $TranscriptPath) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $local = Join-Path $kit 'LOCAL'
    New-Item -ItemType Directory -Path $local -Force | Out-Null
    $TranscriptPath = Join-Path $local "v2-a24-migration-$stamp.raw"
}
Write-Host 'WDCMONv2 -> STR8-N 2.0a24 F-sector migration'
Write-Host 'Stock B3 is copied to erased B0 and verified before B3:F changes.'
Write-Host 'Confirm the physical board model before RAM loading.'
Write-Host 'At SEND STR8-N TOP BIN, press Ctrl+U once for the packaged BIN.'
Write-Host 'Confirm INSTALL STR8-N 2.0A24 only after reviewing board identity.'
Write-Host 'After verification, press physical RESET. E installation is a separate step.'
& $bridge -Port $Port -ExpectedBoardTag $ExpectedBoardTag -ImagePath $installer -TransferPath $candidate `
    -NoReset -PhysicalResetArmSeconds $PhysicalResetArmSeconds -TranscriptPath $TranscriptPath
