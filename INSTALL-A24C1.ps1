param(
    [string]$Port,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Release ZIP: these files sit beside this launcher. Repository: use build paths.
function Resolve-KitFile {
    param([string]$Name, [string]$RepositoryPath)
    foreach ($relative in @($Name, $RepositoryPath)) {
        $candidate = Join-Path $PSScriptRoot $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "Missing $Name. Extract the complete release ZIP, or build the a24c1 files in the repository."
}

$bridge = Resolve-KitFile 'start_wdcmonv2_ram.ps1' 'tools/wdcmonv2/start_wdcmonv2_ram.ps1'
$installer = Resolve-KitFile 'str8n-v2-a24c1-wdcmonv2-install-2000.s19' 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-wdcmonv2-install-2000.s19'
$core = Resolve-KitFile 'str8n-v2-a24c1-f000-ffff.bin' 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-f000-ffff.bin'
$maint = Resolve-KitFile 'str8n-bank-maint-2000.s19' 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19'

if ($ValidateOnly) {
    & $bridge -ImagePath $installer -ValidateOnly
    if ((Get-Item -LiteralPath $core).Length -ne 4096) { throw 'Core BIN must be exactly 4096 bytes.' }
    & $bridge -ImagePath $maint -ValidateOnly
    Write-Host 'A24C1 LAUNCHER FILE CHECK = PASS (no COM port opened)' -ForegroundColor Green
    return
}

Write-Host 'STR8-N 2.0a24c1 stock WDCMONv2 installer - C02 / 816' -ForegroundColor Cyan
Write-Host 'Use this installer on a board running stock WDCMONv2 in B3.' -ForegroundColor Cyan
Write-Host 'Close other terminals using the board port.' -ForegroundColor Yellow
$available = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
Write-Host ('Detected ports: ' + $(if ($available.Count) { $available -join ', ' } else { '(none)' })) -ForegroundColor Cyan
while ($true) {
    if (-not $Port) {
        Write-Host 'Enter the board COM port (for example COM3); Q to quit: ' -NoNewline -ForegroundColor Yellow
        $Port = Read-Host
    }
    $Port = $Port.Trim().ToUpperInvariant()
    if ($Port -eq 'Q') { return }
    if ($Port -match '^COM[1-9][0-9]*$') { break }
    Write-Host 'Enter a COM port such as COM3.' -ForegroundColor Yellow
    $Port = ''
}
Write-Host "Using $Port. At PHYSICAL RESET GATE, press RESET, wait two seconds, then press Enter here." -ForegroundColor Yellow
Write-Host 'For board confirmation, type W65C02SXB or W65C816SXB exactly in uppercase.' -ForegroundColor Yellow
Write-Host 'After verified installation, press physical RESET again when the installer waits for reset.' -ForegroundColor Yellow
& $bridge -Port $Port -NoReset -PhysicalResetGate -ImagePath $installer -TransferPath $core -Transfer2Path $maint
