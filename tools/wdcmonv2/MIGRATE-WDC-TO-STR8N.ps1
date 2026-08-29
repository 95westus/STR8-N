param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [int]$PhysicalResetArmSeconds = 0,
    [string]$TranscriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$kitRoot = $PSScriptRoot
$bridge = Join-Path $kitRoot 'TOOLS/start_wdcmonv2_ram.ps1'
$installer = Join-Path $kitRoot 'ARTIFACTS/str8n-v1.28-wdcmonv2-install-2000.s19'
foreach ($path in @($bridge, $installer)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Migration kit is incomplete: $path"
    }
}

if (-not $TranscriptPath) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $TranscriptPath = Join-Path $kitRoot "LOCAL/factory-migration-$stamp.raw"
}

Write-Host ''
Write-Host 'FACTORY WDCMONV2 -> STR8-N 1.28'
Write-Host '  1. Complete stock Bank 3 is copied and verified in Bank 0.'
Write-Host '  2. STR8-N 1.28 is installed in Bank 3 sector F.'
Write-Host '  3. D0 publishes retained WDCMONv2 as WDCM2 for selector 0 and J0.'
Write-Host 'Do not reset, assert NMI, or remove power during active flash writes.'
Write-Host ''

$arguments = @{
    Port = $Port
    NoReset = $true
    ImagePath = $installer
    TranscriptPath = $TranscriptPath
}
if ($PhysicalResetArmSeconds -gt 0) {
    $arguments.PhysicalResetArmSeconds = $PhysicalResetArmSeconds
} else {
    $arguments.PhysicalResetGate = $true
}

& $bridge @arguments

Write-Host ''
Write-Host 'NEXT: connect any serial terminal at 115200 baud, 8 data bits, no parity, 1 stop bit.'
Write-Host 'Examples: minicom, Tera Term, PuTTY, or another serial terminal emulator.'
Write-Host 'Press physical RESET: STR8-N 1.28 must appear.'
Write-Host 'At the selector choose S for the shell or 0 for retained WDCMONv2.'
Write-Host 'From the shell, J0 also starts retained WDCMONv2 after the CS0-CS3 chase.'
Write-Host 'Physical RESET always returns to STR8-N in Bank 3.'
