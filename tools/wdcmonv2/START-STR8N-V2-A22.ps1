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
$installer = Join-Path $kit 'FIRMWARE/str8n-v2-alpha22-wdcmonv2-install-2000.s19'
$candidate = Join-Path $kit 'FIRMWARE/str8n-v2-alpha22-f000-ffff.bin'
foreach ($path in @($bridge, $installer, $candidate)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Candidate package file missing: $path" }
}
if ((Get-Item -LiteralPath $candidate).Length -ne 4096) { throw 'Top BIN must be 4096 bytes' }
$expected = '1BAE74704DD5C66CA34FA8D3B1BDFA9F2CF65FFAB72A724A8EBA87888420A439'
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash -ne $expected) {
    throw 'Top BIN does not match the qualified a22 candidate'
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
    $TranscriptPath = Join-Path $local "v2-a22-migration-$stamp.raw"
}
Write-Host 'WDCMONv2 -> STR8-N 2.0a22 F-sector migration'
Write-Host 'Stock B3 is copied to erased B0 and verified before B3:F changes.'
Write-Host 'At SEND STR8-N TOP BIN, press Ctrl+U once for the packaged BIN.'
Write-Host 'Confirm INSTALL STR8-N 2.0A22 only after reviewing board identity.'
Write-Host 'After verification, press physical RESET. The E extension is a separate step.'
& $bridge -Port $Port -ExpectedBoardTag $ExpectedBoardTag -ImagePath $installer -TransferPath $candidate `
    -NoReset -PhysicalResetArmSeconds $PhysicalResetArmSeconds -TranscriptPath $TranscriptPath
