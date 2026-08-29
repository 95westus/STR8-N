param(
    [string]$Port,
    [int]$PhysicalResetArmSeconds = 0,
    [string]$TranscriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$kitRoot = $PSScriptRoot
$bridge = Join-Path $kitRoot 'TOOLS/start_wdcmonv2_ram.ps1'
$installer = Join-Path $kitRoot 'ARTIFACTS/STR8-iN65-LOADER-2000.s19'
$candidate = Join-Path $kitRoot 'ARTIFACTS/STR8-N-v1-29.bin'
$bankMaint = Join-Path $kitRoot 'ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19'
foreach ($path in @($bridge, $installer, $candidate, $bankMaint)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Migration kit is incomplete: $path"
    }
}

if (-not $Port) {
    $ports = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object { [int]($_ -replace '\D', '') })
    if ($ports.Count -eq 0) { throw 'No serial ports were found. Connect the WDC board and try again.' }
    Write-Host 'SERIAL PORTS'
    for ($i = 0; $i -lt $ports.Count; $i++) { Write-Host ('  [{0}] {1}' -f ($i + 1), $ports[$i]) }
    $defaultPort = if ($ports.Count -eq 1) { $ports[0] } else { '' }
    $portPrompt = if ($defaultPort) { "Enter COM port [$defaultPort]" } else { 'Enter COM port' }
    $answer = Read-Host $portPrompt
    if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $defaultPort }
    if ($answer -match '^\d+$') {
        $choice = [int]$answer
        if ($choice -lt 1 -or $choice -gt $ports.Count) { throw "Serial-port choice is out of range: $answer" }
        $Port = $ports[$choice - 1]
    } else {
        $Port = $answer.Trim().ToUpperInvariant()
    }
    if ($ports -notcontains $Port) { throw "Serial port is not currently present: $Port" }
}

[byte[]]$candidateBytes = [System.IO.File]::ReadAllBytes($candidate)
if ($candidateBytes.Length -ne 4096) { throw "Canonical STR8-N BIN is $($candidateBytes.Length) bytes; expected 4096" }
$candidateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash

if (-not $TranscriptPath) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $TranscriptPath = Join-Path $kitRoot "LOCAL/factory-migration-$stamp.raw"
}

Write-Host ''
Write-Host 'FACTORY WDCMONV2 -> STR8-N 1.29'
Write-Host '  1. Complete stock Bank 3 is copied and verified in Bank 0.'
Write-Host '  2. The canonical 4096-byte STR8-N BIN is sent and installed in Bank 3 sector F.'
Write-Host '  3. STR8-N boots with an empty Bank-3 directory; D0 adoption is a later prompt.'
Write-Host 'Do not reset, assert NMI, or remove power during active flash writes.'
Write-Host ''
Write-Host ('PORT                 = {0}' -f $Port)
Write-Host ('STR8-N TOP BIN       = {0}' -f (Split-Path -Leaf $candidate))
Write-Host ('BIN SIZE             = {0} bytes' -f $candidateBytes.Length)
Write-Host ('BIN SHA-256          = {0}' -f $candidateSha256)
Write-Host 'IMAGE START          = $F000'
Write-Host 'T48 DEVICE OFFSET    = $1F000'
Write-Host 'When the board prints SEND STR8-N TOP BIN, press CTRL+U once.'
Write-Host 'After STR8-N 1.29 boots: select S, enter L, then press CTRL+D to send Bank Maintenance.'
Write-Host 'At Bank Maintenance enter D, accept defaults, and type ADOPT B0.'
Write-Host ''

$arguments = @{
    Port = $Port
    NoReset = $true
    ImagePath = $installer
    TransferPath = $candidate
    Transfer2Path = $bankMaint
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
Write-Host 'Press physical RESET: STR8-N 1.29 must appear.'
Write-Host 'Require D0 FF WDCM2 FFFF FCFFFFFF before testing selector 0 and J0.'
Write-Host 'Physical RESET always returns to STR8-N in Bank 3.'
