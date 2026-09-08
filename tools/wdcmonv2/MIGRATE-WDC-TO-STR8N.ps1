param(
    [string]$Port,
    [int]$PhysicalResetArmSeconds = 0,
    [string]$TranscriptPath,
    [switch]$Details
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$kitRoot = $PSScriptRoot
$bridge = Join-Path $kitRoot 'TOOLS/start_wdcmonv2_ram.ps1'
$installer = Join-Path $kitRoot 'ARTIFACTS/STR8-iN65-LOADER-2000.s19'
$candidate = Join-Path $kitRoot 'ARTIFACTS/STR8-N-v1-30.bin'
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
Write-Host 'STR8-iN/65 LOADER - FAST PATH'
Write-Host 'Factory WDCMONv2 -> STR8-N 1.32'
Write-Host ''
Write-Host 'Release package .............................. PASS'
Write-Host ('Port ......................................... {0}' -f $Port)
Write-Host 'Top image .................................... 4096 bytes; $F000-$FFFF'
Write-Host 'Evidence ..................................... full raw + event logs'
Write-Host ''
Write-Host 'READ THE SCREEN: enter commands and press control keys only when requested.'
Write-Host 'Confirmations: COPY B3 TO B0, then INSTALL STR8-N 1.32.'
Write-Host 'When the screen asks for the top BIN, press CTRL+U once.'
Write-Host 'After boot, follow the screen: S, L, CTRL+D once, D, then 0, FF, WDCV2, ADOPT B0.'
Write-Host 'Do not reset, assert NMI, or remove power during active flash writes.'
Write-Host 'On an EDU, solid LED $F0 marks active flash mutation and clears after verification.'
if ($Details) {
    Write-Host ''
    Write-Host 'DETAILS'
    Write-Host '  Bank 3 is preserved byte-for-byte as an opaque 32K Bank-0 guest.'
    Write-Host '  B1 and B2 are not migration destinations.'
    Write-Host '  D0 is written only in the Bank-3 directory after verified v1.32 boot.'
    Write-Host ('  STR8-N TOP BIN    = {0}' -f (Split-Path -Leaf $candidate))
    Write-Host ('  BIN SHA-256       = {0}' -f $candidateSha256)
    Write-Host '  T48 DEVICE OFFSET = $1F000'
    Write-Host ('  RAW TRANSCRIPT    = {0}' -f $TranscriptPath)
    Write-Host ('  HOST EVENT LOG    = {0}.events.txt' -f $TranscriptPath)
}
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
Write-Host 'Press physical RESET: STR8-N 1.32 must appear.'
Write-Host 'Require D0 FF WDCV2 FFFF FCFFFFFF before testing selector 0 and J0.'
Write-Host 'J0 is a complete handoff to the preserved factory system.'
Write-Host 'Physical RESET is the designed return to STR8-N; this is not a flaw.'
Write-Host ('Detailed raw transcript: {0}' -f $TranscriptPath)
Write-Host ('Detailed host event log: {0}.events.txt' -f $TranscriptPath)
