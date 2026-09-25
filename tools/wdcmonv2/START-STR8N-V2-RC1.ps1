param(
    [string]$Port,
    [ValidateSet('Auto', 'SXB2', 'SXB3')][string]$ExpectedBoardTag = 'Auto',
    [int]$PhysicalResetArmSeconds = 60,
    [string]$TranscriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$kit = $PSScriptRoot
$bridge = Join-Path $kit 'TOOLS/start_wdcmonv2_ram.ps1'
$installer = Join-Path $kit 'FIRMWARE/str8n-v2-rc1-wdcmonv2-install-2000.s19'
$candidate = Join-Path $kit 'FIRMWARE/str8n-v2-alpha21-f000-ffff.bin'
foreach ($path in @($bridge, $installer, $candidate)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "RC1 package file missing: $path" }
}
if ((Get-Item -LiteralPath $candidate).Length -ne 4096) { throw 'RC1 top BIN must be 4096 bytes' }
$expected = '3738EAB501C50EF0470E9A81EF573B563DA7DC656CC18A83573D16C9BD2E6E49'
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash
if ($actual -ne $expected) { throw 'RC1 top BIN does not match board 2512 readback identity' }
if ($PhysicalResetArmSeconds -lt 0 -or $PhysicalResetArmSeconds -gt 120) {
    throw '-PhysicalResetArmSeconds must be 0..120 (0 probes an already running stock monitor)'
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
    $TranscriptPath = Join-Path $local "v2-rc1-migration-$stamp.raw"
}

Write-Host 'WDCMONv2 -> STR8-N 2.0a21 RC1 RAM migration'
Write-Host 'Stock Bank 3 is copied and verified in erased Bank 0 before Bank 3 F changes.'
Write-Host 'A used, different Bank 0 is refused. Keep owner-local stock archives private.'
Write-Host 'After RAM readback, follow the on-screen COPY and INSTALL confirmations.'
Write-Host 'At SEND STR8-N TOP BIN, press Ctrl+U once to transfer the packaged 4096-byte BIN.'
Write-Host 'After MIGRATION VERIFIED, press physical RESET to initialize alpha21 RAM.'
Write-Host 'Keep USB power and host connected throughout active transfer and flash writes.'

& $bridge -Port $Port -ExpectedBoardTag $ExpectedBoardTag -ImagePath $installer -TransferPath $candidate `
    -NoReset -PhysicalResetArmSeconds $PhysicalResetArmSeconds `
    -TranscriptPath $TranscriptPath
