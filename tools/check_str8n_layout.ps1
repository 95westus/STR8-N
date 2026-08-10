param(
    [string]$Str8MapPath = "BUILD/s19/str8n-f000.map",
    [string]$WorkerMapPath = "BUILD/s19/str8n-worker-0200.map",
    [string]$WorkerS19Path = "BUILD/s19/str8n-worker-0200.s19",
    [string]$WorkerEqPath = "src/str8-worker-eq.inc"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TopStart = 0xF000
$DirectoryStart = 0xFFB0
$DirectoryEnd = 0xFFEF
$ConfigStart = 0xFFF0
$VectorStart = 0xFFFA
$WorkerRunStart = 0x0200
$WorkerSelectEntry = 0x0203
$MinimumMargin = 32

function Get-MapSymbol {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path)) { throw "Required map not found: $Path" }
    $pattern = '^\s*([0-9A-Fa-f]{8})\s+' + [Regex]::Escape($Name) + '$'
    $match = Select-String -LiteralPath $Path -Pattern $pattern | Select-Object -First 1
    if (-not $match) { throw "Missing symbol '$Name' in $Path" }
    return [Convert]::ToInt32($match.Matches[0].Groups[1].Value, 16)
}

function Get-EquValue {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path)) { throw "Required include not found: $Path" }
    $pattern = '^\s*' + [Regex]::Escape($Name) + '\s+EQU\s+\$([0-9A-Fa-f]+)\s*$'
    $match = Select-String -LiteralPath $Path -Pattern $pattern | Select-Object -First 1
    if (-not $match) { throw "Missing hexadecimal constant '$Name' in $Path" }
    return [Convert]::ToInt32($match.Matches[0].Groups[1].Value, 16)
}

function Assert-Equal {
    param([int]$Actual, [int]$Expected, [string]$Name)
    if ($Actual -ne $Expected) {
        throw ('{0} is ${1:X4}; expected ${2:X4}' -f $Name, $Actual, $Expected)
    }
}

$residentStart = Get-MapSymbol $Str8MapPath 'START'
$residentEnd = Get-MapSymbol $Str8MapPath '_END_DATA'
$directoryMapStart = Get-MapSymbol $Str8MapPath 'STR8_DIR_BASE'
$directoryMapEnd = Get-MapSymbol $Str8MapPath 'STR8_DIR_END'
$workerStore = Get-MapSymbol $Str8MapPath 'STR8_WORKER_STORE'

$workerStart = Get-MapSymbol $WorkerMapPath 'START'
$workerSelect = Get-MapSymbol $WorkerMapPath 'STR8W_BANK_SELECT_SERVICE'
$workerSelectEnd = Get-MapSymbol $WorkerMapPath 'STR8W_LINKED_SELECT_END'
$workerEnd = Get-MapSymbol $WorkerMapPath 'STR8W_LINKED_END'
$workerSize = $workerEnd - $workerStart
$workerStoreEnd = $workerStore + $workerSize
$margin = $workerStore - $residentEnd

Assert-Equal $residentStart $TopStart 'Resident start'
Assert-Equal (Get-MapSymbol $Str8MapPath 'STR8_RUN_WORKER_SERVICE') 0xF003 '$F003 retired gate'
Assert-Equal (Get-MapSymbol $Str8MapPath 'STR8_RETIRED_F006') 0xF006 '$F006 retired gate'
Assert-Equal (Get-MapSymbol $Str8MapPath 'STR8_RECORD_SERVICE_ENTRY') 0xF009 '$F009 record gate'
Assert-Equal (Get-MapSymbol $Str8MapPath 'STR8_BANK_SELECT_SERVICE_ENTRY') 0xF010 '$F010 selector gate'
Assert-Equal $directoryMapStart $DirectoryStart 'Directory start'
Assert-Equal $directoryMapEnd $DirectoryEnd 'Directory end'
Assert-Equal $workerStart $WorkerRunStart 'Worker run start'
Assert-Equal $workerSelect $WorkerSelectEntry 'Worker selector entry'
Assert-Equal $workerStoreEnd $DirectoryStart 'Worker storage end'

Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_RUN') $workerStart 'Published worker start'
Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_SELECT_END') $workerSelectEnd 'Published selector end'
Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_SELECT_SIZE') ($workerSelectEnd - $workerStart) 'Published selector size'
Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_END') $workerEnd 'Published worker end'
Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_SIZE') $workerSize 'Published worker size'
Assert-Equal (Get-EquValue $WorkerEqPath 'STR8_WORKER_STORE') $workerStore 'Published worker store'

if ($workerSelectEnd -gt 0x0300) {
    throw ('Selector prefix ends at ${0:X4}; it must not overwrite HIMON at $0300' -f $workerSelectEnd)
}
if ($margin -lt $MinimumMargin) {
    throw ('Protected-sector margin is {0} bytes; at least {1} are required' -f $margin, $MinimumMargin)
}
if ($ConfigStart -ne ($DirectoryEnd + 1) -or $VectorStart -ne 0xFFFA) {
    throw 'Protected-sector tail boundaries are inconsistent'
}
if (-not (Test-Path -LiteralPath $WorkerS19Path)) { throw "Worker S19 not found: $WorkerS19Path" }
$workerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $WorkerS19Path).Hash

Write-Host ('RESIDENT            = ${0:X4}-${1:X4}; {2} bytes' -f $residentStart, ($residentEnd - 1), ($residentEnd - $residentStart))
Write-Host ('UNUSED MARGIN        = ${0:X4}-${1:X4}; {2} bytes (minimum {3})' -f $residentEnd, ($workerStore - 1), $margin, $MinimumMargin)
Write-Host ('UNIFIED WORKER       = run ${0:X4}-${1:X4}; store ${2:X4}-${3:X4}; {4} bytes' -f $workerStart, ($workerEnd - 1), $workerStore, ($workerStoreEnd - 1), $workerSize)
Write-Host ('SELECTOR PREFIX      = ${0:X4}-${1:X4}; {2} bytes' -f $workerStart, ($workerSelectEnd - 1), ($workerSelectEnd - $workerStart))
Write-Host ('WORKER S19 SHA-256   = {0}' -f $workerHash)
Write-Host ('DIRECTORY/CONFIG/VEC = $FFB0-$FFEF / $FFF0-$FFF9 / $FFFA-$FFFF')
Write-Host 'LAYOUT CHECK         = PASS'
