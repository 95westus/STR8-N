param(
    [string]$S19Path = "BUILD/v1.21/s19/str8n-v1.21-bank-maint-menu-2000.s19",
    [string]$OutPath = "tools/bank-maint/str8n-v1.21-bank-maint-menu-2000.a"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$data = @{}
$entry = $null
foreach ($raw in Get-Content -LiteralPath $S19Path) {
    $line = $raw.Trim()
    if (-not $line) { continue }
    if ($line -notmatch '^S([19])([0-9A-Fa-f]+)$') {
        throw "Unsupported record: $line"
    }
    $kind = $Matches[1]
    $hex = $Matches[2]
    $bytes = for ($i = 0; $i -lt $hex.Length; $i += 2) {
        [Convert]::ToInt32($hex.Substring($i, 2), 16)
    }
    if ($bytes[0] -ne ($bytes.Count - 1)) { throw "Bad count: $line" }
    $sum = 0
    foreach ($byte in $bytes) { $sum = ($sum + $byte) -band 0xFF }
    if ($sum -ne 0xFF) { throw "Bad checksum: $line" }
    $address = ($bytes[1] -shl 8) -bor $bytes[2]
    if ($kind -eq '9') {
        $entry = $address
        continue
    }
    $length = $bytes[0] - 3
    for ($i = 0; $i -lt $length; $i++) {
        $target = $address + $i
        if ($data.ContainsKey($target)) { throw ('Duplicate byte ${0:X4}' -f $target) }
        $data[$target] = $bytes[3 + $i]
    }
}

if ($entry -ne 0x2000) { throw ('S9 entry is ${0:X4}; expected $2000' -f $entry) }
if ($data.Count -eq 0) { throw 'S19 contains no data' }
$addresses = @($data.Keys | Sort-Object)

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('; STR8N-V1.21-BANK-MAINT-MENU-2000.A')
$lines.Add('; GENERATED ASM-F2-NATIVE IMAGE CARRIER; EDIT THE .ASM SOURCES.')
$lines.Add(';')
$lines.Add('; ASSEMBLE AND RUN:')
$lines.Add(';   ASM NEW')
$lines.Add(';   PASTE THIS COMPLETE FILE')
$lines.Add(';   SEAL> .')
$lines.Add(';   G 2000')
$lines.Add(';')
$lines.Add('; U RUNS THE GUARDED B3:F UPDATE WITH A VERIFIED B1:F BACKUP.')
$lines.Add('; P AP INPUT=$5000; EMBEDDED TOP=$4000.')
$lines.Add('; STOP ON ANY ERR= LINE. DO NOT RUN AN INCOMPLETE IMAGE.')
$lines.Add('')

$index = 0
while ($index -lt $addresses.Count) {
    $start = [int]$addresses[$index]
    $lines.Add(('        ORG ${0:X4}' -f $start))
    while ($index -lt $addresses.Count) {
        $rowStart = [int]$addresses[$index]
        $row = [System.Collections.Generic.List[string]]::new()
        while ($index -lt $addresses.Count -and $row.Count -lt 8) {
            $address = [int]$addresses[$index]
            if ($address -ne ($rowStart + $row.Count)) { break }
            $row.Add(('${0:X2}' -f [int]$data[$address]))
            $index++
        }
        $lines.Add(('        DB ' + ($row -join ',')))
        if ($index -ge $addresses.Count) { break }
        if ([int]$addresses[$index] -ne ($rowStart + $row.Count)) { break }
    }
    $lines.Add('')
}
$lines.Add('        END')

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
Set-Content -LiteralPath $OutPath -Value $lines -Encoding ASCII
Write-Host ('BANK MAINT MENU .A = {0}; bytes={1}; spans=${2:X4}-${3:X4}' -f
    $OutPath, $data.Count, $addresses[0], $addresses[-1])
