param(
    [string]$Str8MapPath = "BUILD/s19/str8n-f000.map",
    [string]$WorkerMapPath = "BUILD/s19/str8n-worker-0200.map",
    [string]$TopBinPath = "BUILD/bin/str8n-bank3-f000-ffff.bin",
    [string]$WorkerS19Path = "BUILD/s19/str8n-worker-0200.s19",
    [string]$ManifestPath = "BUILD/str8n-manifest.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-MapSymbol {
    param([string]$Path, [string]$Name)
    $pattern = '^\s*([0-9A-Fa-f]{8})\s+' + [Regex]::Escape($Name) + '$'
    $match = Select-String -LiteralPath $Path -Pattern $pattern | Select-Object -First 1
    if (-not $match) { throw "Missing symbol '$Name' in $Path" }
    return [Convert]::ToInt32($match.Matches[0].Groups[1].Value, 16)
}

foreach ($path in @($Str8MapPath, $WorkerMapPath, $TopBinPath, $WorkerS19Path)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required artifact not found: $path" }
}

[byte[]]$top = [System.IO.File]::ReadAllBytes($TopBinPath)
if ($top.Length -ne 4096) { throw "Top-sector BIN is $($top.Length) bytes; expected 4096" }

$commit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'Unable to read the STR8-N Git commit'
}
$dirty = -not [string]::IsNullOrWhiteSpace((& git status --porcelain))

$residentStart = Get-MapSymbol $Str8MapPath 'START'
$residentEnd = Get-MapSymbol $Str8MapPath '_END_DATA'
$workerRun = Get-MapSymbol $WorkerMapPath 'START'
$workerEnd = Get-MapSymbol $WorkerMapPath 'STR8W_LINKED_END'
$workerStore = Get-MapSymbol $Str8MapPath 'STR8_WORKER_STORE'
$selectorEntry = Get-MapSymbol $WorkerMapPath 'STR8W_BANK_SELECT_SERVICE'
$selectorEnd = Get-MapSymbol $WorkerMapPath 'STR8W_LINKED_SELECT_END'

$manifest = [ordered]@{
    schema = 1
    project = 'STR8-N'
    repository = 'https://github.com/95westus/STR8-N.git'
    commit = $commit.ToLowerInvariant()
    dirty = $dirty
    artifacts = [ordered]@{
        topSector = [ordered]@{
            file = 'BUILD/bin/str8n-bank3-f000-ffff.bin'
            size = $top.Length
            cpuStart = 'F000'
            cpuEnd = 'FFFF'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $TopBinPath).Hash
        }
        workerS19 = [ordered]@{
            file = 'BUILD/s19/str8n-worker-0200.s19'
            size = $workerEnd - $workerRun
            runStart = ('{0:X4}' -f $workerRun)
            runEnd = ('{0:X4}' -f ($workerEnd - 1))
            storeStart = ('{0:X4}' -f $workerStore)
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $WorkerS19Path).Hash
        }
    }
    layout = [ordered]@{
        residentStart = ('{0:X4}' -f $residentStart)
        residentEnd = ('{0:X4}' -f ($residentEnd - 1))
        unusedMargin = $workerStore - $residentEnd
        directoryStart = 'FFB0'
        directoryEnd = 'FFEF'
        configurationStart = 'FFF0'
        configurationEnd = 'FFF9'
        vectorsStart = 'FFFA'
        vectorsEnd = 'FFFF'
    }
    abi = [ordered]@{
        retiredF003 = 'F003'
        retiredF006 = 'F006'
        recordService = 'F009'
        recordVersion = 2
        recordCapabilities = 3
        bankSelectService = 'F010'
        selectorEntry = ('{0:X4}' -f $selectorEntry)
        selectorEnd = ('{0:X4}' -f ($selectorEnd - 1))
    }
}

$parent = Split-Path -Parent $ManifestPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$json = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($ManifestPath, $json + [Environment]::NewLine, [System.Text.Encoding]::UTF8)

Write-Host ('STR8-N MANIFEST     = {0}' -f $ManifestPath)
Write-Host ('GIT COMMIT          = {0}{1}' -f $manifest.commit, $(if ($dirty) { ' (dirty)' } else { '' }))
Write-Host ('TOP BIN SHA-256     = {0}' -f $manifest.artifacts.topSector.sha256)
Write-Host ('WORKER SHA-256      = {0}' -f $manifest.artifacts.workerS19.sha256)
