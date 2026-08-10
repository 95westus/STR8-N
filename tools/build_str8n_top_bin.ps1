param(
    [string]$Str8MapPath = "BUILD/s19/str8n-f000.map",
    [string]$Str8S19Path = "BUILD/s19/str8n-f000.s19",
    [string]$WorkerMapPath = "BUILD/s19/str8n-worker-0200.map",
    [string]$WorkerS19Path = "BUILD/s19/str8n-worker-0200.s19",
    [string]$BinPath = "BUILD/bin/str8n-bank3-f000-ffff.bin"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TopBase = 0xF000
$TopEndExclusive = 0x10000
$TopSize = 0x1000
$VectorBase = 0xFFFA

function Get-SymbolAddress {
    param(
        [Parameter(Mandatory = $true)][string]$MapPath,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $pattern = "^\s*([0-9A-Fa-f]{8})\s+$([Regex]::Escape($Name))$"
    $match = Select-String -LiteralPath $MapPath -Pattern $pattern |
        Select-Object -First 1
    if (-not $match) { throw "Missing symbol '$Name' in $MapPath" }
    return [Convert]::ToInt32($match.Matches[0].Groups[1].Value, 16)
}

function Read-S19 {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing S19: $Path" }
    $records = New-Object System.Collections.Generic.List[object]
    $lineNumber = 0
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $lineNumber++
        $line = $raw.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line -notmatch '^S([019])([0-9A-Fa-f]+)$') {
            throw "${Path}:$lineNumber unsupported or malformed record: $line"
        }
        $type = [int]$Matches[1]
        $hex = $Matches[2]
        if (($hex.Length -band 1) -ne 0 -or $hex.Length -lt 8) {
            throw "${Path}:$lineNumber malformed record length"
        }
        $count = [Convert]::ToInt32($hex.Substring(0, 2), 16)
        if ($line.Length -ne (4 + (2 * $count))) {
            throw "${Path}:$lineNumber count/length mismatch"
        }
        $sum = 0
        for ($offset = 0; $offset -lt $hex.Length; $offset += 2) {
            $sum += [Convert]::ToInt32($hex.Substring($offset, 2), 16)
        }
        if (($sum -band 0xFF) -ne 0xFF) {
            throw "${Path}:$lineNumber checksum failure"
        }
        $address = [Convert]::ToInt32($hex.Substring(2, 4), 16)
        $dataLength = $count - 3
        [byte[]]$data = New-Object byte[] ([Math]::Max(0, $dataLength))
        for ($i = 0; $i -lt $dataLength; $i++) {
            $data[$i] = [Convert]::ToByte($hex.Substring(6 + (2 * $i), 2), 16)
        }
        $records.Add([pscustomobject]@{ Type = $type; Address = $address; Data = $data })
    }
    return $records.ToArray()
}

function Set-ImageByte {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Image,
        [Parameter(Mandatory = $true)][int]$Address,
        [Parameter(Mandatory = $true)][byte]$Value,
        [Parameter(Mandatory = $true)][string]$Source
    )
    if ($Address -lt $TopBase -or $Address -ge $TopEndExclusive) {
        throw ('{0} address ${1:X4} is outside $F000-$FFFF' -f $Source, $Address)
    }
    $offset = $Address - $TopBase
    if ($Image[$offset] -ne 0xFF -and $Image[$offset] -ne $Value) {
        throw ('Conflict at ${0:X4}: {1:X2} versus {2:X2} from {3}' -f `
            $Address, $Image[$offset], $Value, $Source)
    }
    $Image[$offset] = $Value
}

function Import-Resident {
    param([object[]]$Records, [byte[]]$Image)
    foreach ($record in $Records) {
        if ($record.Type -ne 1) { continue }
        if ($record.Data.Length -le 0) { throw "Resident contains empty S1 data" }
        for ($i = 0; $i -lt $record.Data.Length; $i++) {
            Set-ImageByte -Image $Image -Address ($record.Address + $i) `
                -Value $record.Data[$i] -Source "resident"
        }
    }
}

function Import-RelocatedWorker {
    param(
        [object[]]$Records,
        [byte[]]$Image,
        [int]$RunStart,
        [int]$RunEndExclusive,
        [int]$StoreStart
    )
    $size = $RunEndExclusive - $RunStart
    [bool[]]$seen = New-Object bool[] $size
    foreach ($record in $Records) {
        if ($record.Type -ne 1) { continue }
        for ($i = 0; $i -lt $record.Data.Length; $i++) {
            $runAddress = $record.Address + $i
            $delta = $runAddress - $RunStart
            if ($delta -lt 0 -or $delta -ge $size) {
                throw ('Worker address ${0:X4} is outside ${1:X4}-${2:X4}' -f `
                    $runAddress, $RunStart, ($RunEndExclusive - 1))
            }
            if ($seen[$delta]) { throw ('Duplicate worker byte at ${0:X4}' -f $runAddress) }
            $seen[$delta] = $true
            Set-ImageByte -Image $Image -Address ($StoreStart + $delta) `
                -Value $record.Data[$i] -Source "relocated unified worker"
        }
    }
    for ($i = 0; $i -lt $seen.Length; $i++) {
        if (-not $seen[$i]) { throw ('Worker is missing run byte ${0:X4}' -f ($RunStart + $i)) }
    }
}

foreach ($path in @($Str8MapPath, $Str8S19Path, $WorkerMapPath, $WorkerS19Path)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required file not found: $path" }
}

$str8Start = Get-SymbolAddress -MapPath $Str8MapPath -Name 'START'
$str8End = Get-SymbolAddress -MapPath $Str8MapPath -Name '_END_DATA'
$str8Nmi = Get-SymbolAddress -MapPath $Str8MapPath -Name 'STR8_IVY_ENTRY_NMI'
$str8Irq = Get-SymbolAddress -MapPath $Str8MapPath -Name 'STR8_IVY_ENTRY_IRQ_MASTER'
$workerStore = Get-SymbolAddress -MapPath $Str8MapPath -Name 'STR8_WORKER_STORE'
$directoryStart = Get-SymbolAddress -MapPath $Str8MapPath -Name 'STR8_DIR_BASE'
$directoryEnd = Get-SymbolAddress -MapPath $Str8MapPath -Name 'STR8_DIR_END'
$workerRunStart = Get-SymbolAddress -MapPath $WorkerMapPath -Name 'START'
$workerRunEnd = Get-SymbolAddress -MapPath $WorkerMapPath -Name 'STR8W_LINKED_END'
$workerSize = $workerRunEnd - $workerRunStart

if ($str8Start -ne $TopBase) { throw ('STR8 START is ${0:X4}; expected $F000' -f $str8Start) }
if ($str8End -gt $workerStore) { throw ('Resident end ${0:X4} crosses worker ${1:X4}' -f $str8End, $workerStore) }
if (($workerStore - $str8End) -lt 8) {
    throw ('Resident/worker margin is {0} bytes; expected at least 8' -f ($workerStore - $str8End))
}
if ($workerRunStart -ne 0x0200) { throw ('Worker starts at ${0:X4}; expected $0200' -f $workerRunStart) }
if (($workerStore + $workerSize) -ne $directoryStart) {
    throw ('Worker storage ${0:X4}+${1:X} does not end at directory ${2:X4}' -f `
        $workerStore, $workerSize, $directoryStart)
}
if ($directoryStart -ne 0xFFB0 -or $directoryEnd -ne 0xFFEF) {
    throw ('Directory is ${0:X4}-${1:X4}; expected $FFB0-$FFEF' -f `
        $directoryStart, $directoryEnd)
}

[byte[]]$image = New-Object byte[] $TopSize
for ($i = 0; $i -lt $image.Length; $i++) { $image[$i] = 0xFF }
Import-Resident -Records (Read-S19 -Path $Str8S19Path) -Image $image
Import-RelocatedWorker -Records (Read-S19 -Path $WorkerS19Path) -Image $image `
    -RunStart $workerRunStart -RunEndExclusive $workerRunEnd -StoreStart $workerStore

for ($address = $directoryStart; $address -le $directoryEnd; $address++) {
    if ($image[$address - $TopBase] -ne 0xFF) {
        throw ('New-image directory byte ${0:X4} is not erased' -f $address)
    }
}
for ($address = 0xFFF0; $address -lt $VectorBase; $address++) {
    if ($image[$address - $TopBase] -ne 0xFF) {
        throw ('Configuration byte ${0:X4} is not erased' -f $address)
    }
}

[byte[]]$vectors = @(
    [byte]($str8Nmi -band 0xFF), [byte](($str8Nmi -shr 8) -band 0xFF),
    [byte]($str8Start -band 0xFF), [byte](($str8Start -shr 8) -band 0xFF),
    [byte]($str8Irq -band 0xFF), [byte](($str8Irq -shr 8) -band 0xFF)
)
for ($i = 0; $i -lt $vectors.Length; $i++) {
    Set-ImageByte -Image $image -Address ($VectorBase + $i) `
        -Value $vectors[$i] -Source "hardware vectors"
}

$parent = Split-Path -Parent $BinPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllBytes($BinPath, $image)
[byte[]]$check = [System.IO.File]::ReadAllBytes($BinPath)
if ($check.Length -ne $TopSize) { throw "BIN is $($check.Length) bytes; expected 4096" }

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BinPath).Hash
$tail = $check[0x0FFA..0x0FFF] | ForEach-Object { '{0:X2}' -f $_ }
Write-Host ('STR8 RESIDENT       = ${0:X4}-${1:X4}' -f $str8Start, ($str8End - 1))
Write-Host ('UNIFIED WORKER      = run ${0:X4}-${1:X4}; stored ${2:X4}-${3:X4}' -f `
    $workerRunStart, ($workerRunEnd - 1), $workerStore, ($workerStore + $workerSize - 1))
Write-Host ('NEW V2 DIRECTORY    = ${0:X4}-${1:X4}; all FF' -f $directoryStart, $directoryEnd)
Write-Host ('VECTORS FFFA-FFFF   = {0}' -f ($tail -join ' '))
Write-Host ('CPU RANGE           = $F000-$FFFF; 4096 bytes')
Write-Host ('SST39SF010A B3 PHYS = $1F000-$1FFFF; file offset $000-$FFF')
Write-Host ('SHA-256             = {0}' -f $hash)
Write-Host ('T48 BIN             = {0}' -f $BinPath)
