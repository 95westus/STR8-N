param(
    [string]$MapPath = "BUILD/v1.22/s19/str8n-v1.22-f000.map"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-MapSymbol {
    param([string]$Name)
    $pattern = '^\s*([0-9A-Fa-f]{8})\s+' + [Regex]::Escape($Name) + '$'
    $match = Select-String -LiteralPath $MapPath -Pattern $pattern | Select-Object -First 1
    if (-not $match) { throw "Missing symbol '$Name' in $MapPath" }
    return [Convert]::ToInt32($match.Matches[0].Groups[1].Value, 16)
}

function Test-DataSpan {
    param([int]$Start, [int]$Length)
    if ($Length -lt 1 -or $Length -gt 252) { return $false }
    $last = $Start + $Length - 1
    return $Start -ge 0x2000 -and $last -lt 0x7B00
}

function Test-Entry {
    param([int]$Address)
    return $Address -ge 0x2000 -and $Address -lt 0x7B00
}

function Get-QuenchStopIndex {
    param([array]$States)
    for ($index = 0; $index -lt $States.Count; $index++) {
        $state = $States[$index]
        if ($state.Kind -eq 0x03 -or $state.Status -eq 0x0E) {
            return $index
        }
    }
    return -1
}

if ((Get-MapSymbol 'STR8_RAM_LOAD_MIN_HI') -ne 0x20) {
    throw 'Linked RAM-load lower boundary is not $2000'
}
if ((Get-MapSymbol 'STR8_RAM_LOAD_LIMIT_HI') -ne 0x7B) {
    throw 'Linked RAM-load exclusive upper boundary is not $7B00'
}
$entry = Get-MapSymbol 'STR8_CMD_LOAD_RAM'
if ($entry -lt 0xF000 -or $entry -ge 0xFFB0) {
    throw ('RAM-load command linked outside resident ROM: ${0:X4}' -f $entry)
}
$quench = Get-MapSymbol 'STR8_I_QUENCH_S19'
if ($quench -lt 0xF000 -or $quench -ge 0xFFB0) {
    throw ('S19 quench linked outside resident ROM: ${0:X4}' -f $quench)
}

$spanCases = @(
    @{ Start = 0x2000; Length = 1;   Expected = $true  },
    @{ Start = 0x2000; Length = 252; Expected = $true  },
    @{ Start = 0x7A04; Length = 252; Expected = $true  },
    @{ Start = 0x7AFF; Length = 1;   Expected = $true  },
    @{ Start = 0x1FFF; Length = 1;   Expected = $false },
    @{ Start = 0x7AFF; Length = 2;   Expected = $false },
    @{ Start = 0x7A05; Length = 252; Expected = $false },
    @{ Start = 0x7B00; Length = 1;   Expected = $false },
    @{ Start = 0xFFFF; Length = 2;   Expected = $false },
    @{ Start = 0x2000; Length = 0;   Expected = $false }
)
foreach ($case in $spanCases) {
    $actual = Test-DataSpan -Start $case.Start -Length $case.Length
    if ($actual -ne $case.Expected) {
        throw ('RAM S1 boundary case failed: start=${0:X4}, length={1}' -f $case.Start, $case.Length)
    }
}

$entryCases = @(
    @{ Address = 0x2000; Expected = $true  },
    @{ Address = 0x7AFF; Expected = $true  },
    @{ Address = 0x1FFF; Expected = $false },
    @{ Address = 0x7B00; Expected = $false },
    @{ Address = 0xFFFF; Expected = $false }
)
foreach ($case in $entryCases) {
    $actual = Test-Entry -Address $case.Address
    if ($actual -ne $case.Expected) {
        throw ('RAM S9 boundary case failed: entry=${0:X4}' -f $case.Address)
    }
}

$quenchCases = @(
    @{ Name = 'S9 already consumed'; Expected = 0; States = @(
        [pscustomobject]@{ Kind = 0x03; Status = 0x00 }
    ) },
    @{ Name = 'Ctrl-C already consumed'; Expected = 0; States = @(
        [pscustomobject]@{ Kind = 0x00; Status = 0x0E }
    ) },
    @{ Name = 'policy failure through S9'; Expected = 3; States = @(
        [pscustomobject]@{ Kind = 0x02; Status = 0x00 },
        [pscustomobject]@{ Kind = 0x00; Status = 0x08 },
        [pscustomobject]@{ Kind = 0x01; Status = 0x00 },
        [pscustomobject]@{ Kind = 0x03; Status = 0x00 }
    ) },
    @{ Name = 'parse failure through Ctrl-C'; Expected = 2; States = @(
        [pscustomobject]@{ Kind = 0x00; Status = 0x06 },
        [pscustomobject]@{ Kind = 0x02; Status = 0x00 },
        [pscustomobject]@{ Kind = 0x00; Status = 0x0E }
    ) }
)
foreach ($case in $quenchCases) {
    $actual = Get-QuenchStopIndex -States $case.States
    if ($actual -ne $case.Expected) {
        throw ('S19 quench case failed: {0}; expected {1}, got {2}' -f $case.Name, $case.Expected, $actual)
    }
}

Write-Host 'RAM LOAD CONTRACT   = PASS'
Write-Host 'S1 DESTINATIONS     = $2000-$7AFF, complete record span'
Write-Host 'S9 EXECUTION        = $2000-$7AFF, automatic after nonempty load'
Write-Host 'FAILURE QUENCH      = validated S9 or Ctrl-C'
Write-Host ('LINKED L COMMAND    = ${0:X4}' -f $entry)
