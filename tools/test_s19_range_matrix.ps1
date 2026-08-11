param(
    [string]$WorkDir = "BUILD/v1.2/test/range-matrix"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$converter = Join-Path $PSScriptRoot 'convert_guest_bin_to_s19.ps1'
$validator = Join-Path $PSScriptRoot 'compose_str8n_install_s19.ps1'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $root $WorkDir
New-Item -ItemType Directory -Force -Path $out | Out-Null

function Test-Range {
    param(
        [int]$Bank,
        [int]$Start,
        [int]$EndExclusive,
        [string]$Name
    )

    $size = $EndExclusive - $Start
    [byte[]]$bytes = New-Object byte[] $size
    for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = 0xEA }

    $entry = $Start
    if ($Bank -lt 3 -and $Start -eq 0x8000 -and $EndExclusive -eq 0x10000) {
        $bytes[0x7FFC] = 0x00
        $bytes[0x7FFD] = 0x80
        $entry = -1
    }

    $bin = Join-Path $out "$Name.bin"
    $raw = Join-Path $out "$Name.s19"
    $checked = Join-Path $out "$Name.checked.s19"
    [IO.File]::WriteAllBytes($bin, $bytes)

    $convertArgs = @{
        BinPath = $bin
        S19Path = $raw
        BaseAddress = $Start
        Bank = $Bank
    }
    if ($entry -ge 0) { $convertArgs.EntryAddress = $entry }
    & $converter @convertArgs *> $null

    $validateArgs = @{
        PayloadS19Path = $raw
        S19Path = $checked
        PayloadStart = $Start
        PayloadEndExclusive = $EndExclusive
        Bank = $Bank
    }
    & $validator @validateArgs *> $null
}

# Every top-aligned Bank 0-2 size: F, E-F, ... 8-F.
for ($sectors = 1; $sectors -le 8; $sectors++) {
    $start = 0x10000 - ($sectors * 0x1000)
    Test-Range -Bank 0 -Start $start -EndExclusive 0x10000 -Name ('bank0-{0}k-{1:X1}-f' -f ($sectors * 4), ($start -shr 12))
}

# Every top-aligned Bank-3 size below protected sector F: E, D-E, ... 8-E.
for ($sectors = 1; $sectors -le 7; $sectors++) {
    $start = 0xF000 - ($sectors * 0x1000)
    Test-Range -Bank 3 -Start $start -EndExclusive 0xF000 -Name ('bank3-{0}k-{1:X1}-e' -f ($sectors * 4), ($start -shr 12))
}

# Upper alignment is optional; keep representative middle spans covered too.
Test-Range -Bank 2 -Start 0xA000 -EndExclusive 0xE000 -Name 'bank2-16k-a-d'
Test-Range -Bank 3 -Start 0x9000 -EndExclusive 0xC000 -Name 'bank3-12k-9-b'

Write-Host 'S19 RANGE MATRIX    = PASS'
Write-Host 'BANKS 0-2 SIZES     = 4K, 8K, 12K, 16K, 20K, 24K, 28K, 32K'
Write-Host 'BANK 3 SIZES        = 4K, 8K, 12K, 16K, 20K, 24K, 28K'
Write-Host ('MATRIX ARTIFACTS    = {0}' -f $out)
