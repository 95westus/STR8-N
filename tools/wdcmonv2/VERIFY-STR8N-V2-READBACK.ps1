param(
    [Parameter(Mandatory = $true)][string]$TranscriptPath,
    [string]$BinPath = 'FIRMWARE/str8n-v2-alpha21-f000-ffff.bin'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($path in @($TranscriptPath, $BinPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "File not found: $path" }
}
[byte[]]$expected = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $BinPath).Path)
if ($expected.Length -ne 4096) { throw 'Expected top BIN must contain exactly 4096 bytes' }
$cells = New-Object int[] 4096
for ($i = 0; $i -lt $cells.Length; $i++) { $cells[$i] = -1 }
$rows = 0
foreach ($line in [System.IO.File]::ReadAllLines((Resolve-Path -LiteralPath $TranscriptPath).Path)) {
    if ($line -notmatch '^\s*([0-9A-Fa-f]{4}):\s+(.+)$') { continue }
    $address = [Convert]::ToInt32($Matches[1], 16)
    if ($address -lt 0xF000 -or $address -gt 0xFFFF) { continue }
    $tokens = @($Matches[2] -split '\s+' | Where-Object { $_ -ne '' })
    $n = 0
    foreach ($token in $tokens) {
        if ($token -notmatch '^[0-9A-Fa-f]{2}$') { break }
        if ($n -ge 16) { throw ('More than 16 bytes on dump row ${0:X4}' -f $address) }
        $offset = $address + $n - 0xF000
        if ($offset -ge 4096) { throw 'Dump row extends past $FFFF' }
        $value = [Convert]::ToInt32($token, 16)
        if ($cells[$offset] -ge 0 -and $cells[$offset] -ne $value) {
            throw ('Conflicting captured byte at ${0:X4}' -f ($address + $n))
        }
        $cells[$offset] = $value
        $n++
    }
    if ($n -gt 0) { $rows++ }
}
for ($i = 0; $i -lt 4096; $i++) {
    if ($cells[$i] -lt 0) { throw ('Incomplete readback: missing ${0:X4}' -f (0xF000 + $i)) }
    if ($cells[$i] -ne $expected[$i]) {
        throw ('Readback differs from alpha21 BIN at ${0:X4}: board=${1:X2}, expected=${2:X2}' -f (0xF000 + $i), $cells[$i], $expected[$i])
    }
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BinPath).Hash
Write-Host ('BANK 3 F READBACK = BYTE-EXACT PASS; {0} rows; SHA256={1}' -f $rows, $hash)
