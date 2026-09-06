param(
    [string]$Str8MapPath = "BUILD/v1.30/map/str8n-v1.30-f000.map",
    [string]$WorkerMapPath = "BUILD/v1.30/map/str8n-v1.30-worker-0200.map",
    [string]$ConsoleAbiTestMapPath = "BUILD/v1.30/map/str8n-v1.30-console-abi-test-2000.map",
    [string]$TopBinPath = "BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin",
    [string]$WorkerS19Path = "BUILD/v1.30/s19/str8n-v1.30-worker-0200.s19",
    [string]$BankMaintS19Path = "BUILD/v1.30/s19/str8n-v1.30-bank-maint-2000.s19",
    [string]$ConsoleAbiTestS19Path = "BUILD/v1.30/s19/str8n-v1.30-console-abi-test-2000.s19",
    [string]$TopUpdateS19Path = "BUILD/v1.30/s19/str8n-v1.30-top-update-2000.s19",
    [string]$DirectoryRefreshS19Path = "BUILD/v1.30/s19/str8n-v1.30-directory-refresh-2000.s19",
    [string]$Wdcmonv2ArchiveMapPath = "BUILD/v1.30/map/str8n-v1.30-wdcmonv2-archive-2000.map",
    [string]$Wdcmonv2ArchiveS19Path = "BUILD/v1.30/s19/str8n-v1.30-wdcmonv2-archive-2000.s19",
    [string]$Wdcmonv2InstallMapPath = "BUILD/v1.30/map/str8n-v1.30-wdcmonv2-install-2000.map",
    [string]$Wdcmonv2InstallS19Path = "BUILD/v1.30/s19/str8n-v1.30-wdcmonv2-install-2000.s19",
    [string]$Wdcmonv2InstallTopBinPath = "BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin",
    [string]$PublicContractPath = "BUILD/v1.30/include/str8n-public.inc",
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

foreach ($path in @($Str8MapPath, $WorkerMapPath, $ConsoleAbiTestMapPath, $TopBinPath, $WorkerS19Path, $BankMaintS19Path, $ConsoleAbiTestS19Path, $TopUpdateS19Path, $DirectoryRefreshS19Path, $Wdcmonv2ArchiveMapPath, $Wdcmonv2ArchiveS19Path, $Wdcmonv2InstallMapPath, $Wdcmonv2InstallS19Path, $Wdcmonv2InstallTopBinPath, $PublicContractPath)) {
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
$consoleAbiTestStart = Get-MapSymbol $ConsoleAbiTestMapPath 'CAT_START'
$consoleAbiTestEnd = Get-MapSymbol $ConsoleAbiTestMapPath '_END_CODE'
$wdcmonv2ArchiveStart = Get-MapSymbol $Wdcmonv2ArchiveMapPath 'START'
$wdcmonv2ArchiveEnd = Get-MapSymbol $Wdcmonv2ArchiveMapPath '_END_DATA'
$wdcmonv2InstallStart = Get-MapSymbol $Wdcmonv2InstallMapPath 'START'
$wdcmonv2InstallEnd = Get-MapSymbol $Wdcmonv2InstallMapPath '_END_CODE'

$manifest = [ordered]@{
    schema = 3
    project = 'STR8-N'
    version = '1.30'
    repository = 'https://github.com/95westus/STR8-N.git'
    commit = $commit.ToLowerInvariant()
    dirty = $dirty
    artifacts = [ordered]@{
        topSector = [ordered]@{
            file = 'BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin'
            size = $top.Length
            cpuStart = 'F000'
            cpuEnd = 'FFFF'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $TopBinPath).Hash
            hardwareStatus = 'conservative v1.30: COM4 guarded update/readback, cold-power startup, boot-path and console ABI checks passed; 2026-09-05; see report for scope'
            validationReport = 'docs/STR8N_CONSERVATIVE_RESIDENT_PASS.md'
        }
        workerS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-worker-0200.s19'
            size = $workerEnd - $workerRun
            runStart = ('{0:X4}' -f $workerRun)
            runEnd = ('{0:X4}' -f ($workerEnd - 1))
            storeStart = ('{0:X4}' -f $workerStore)
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $WorkerS19Path).Hash
        }
        bankMaintenanceS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-bank-maint-2000.s19'
            ramStart = '2000'
            ramEnd = '39B2'
            entry = '2000'
            privateWorkerStore = '3400'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $BankMaintS19Path).Hash
        }
        consoleAbiTestS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-console-abi-test-2000.s19'
            ramStart = ('{0:X4}' -f $consoleAbiTestStart)
            ramEnd = ('{0:X4}' -f ($consoleAbiTestEnd - 1))
            entry = '2000'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ConsoleAbiTestS19Path).Hash
        }
        topUpdateS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-top-update-2000.s19'
            ramStart = '2000'
            ramEnd = '4FFF'
            candidateStart = '4000'
            candidateEnd = '4FFF'
            entry = '2000'
            backup = 'Bank 1 CPU F000-FFFF / physical 0F000-0FFFF'
            hardwareEvidence = 'docs/STR8N_CONSERVATIVE_RESIDENT_PASS.md: conservative candidate guarded update, exact readback, console ABI; COM4, 2026-09-05'
            historicalCanonicalTopSha256 = '60B7FE19E42766AACFCDEF8320A35D9D5AB7C5F91F0FE3130041F2CFF4799734'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $TopUpdateS19Path).Hash
        }
        directoryRefreshS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-directory-refresh-2000.s19'
            ramStart = '2000'
            ramEnd = '4FFF'
            candidateStart = '4000'
            candidateEnd = '4FFF'
            entry = '2000'
            backup = 'Bank 1 CPU F000-FFFF / physical 0F000-0FFFF'
            clears = 'Bank 3 CPU FFB0-FFEF / physical 1FFB0-1FFEF'
            installs = 'Bank 3 CPU FFF0=1E (B1:E WORK); FFF1=1F (B1:F protected B3:F backup); FFF2-FFF9 erased'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $DirectoryRefreshS19Path).Hash
        }
        wdcmonv2ArchiveS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-wdcmonv2-archive-2000.s19'
            ramStart = ('{0:X4}' -f $wdcmonv2ArchiveStart)
            ramEnd = ('{0:X4}' -f ($wdcmonv2ArchiveEnd - 1))
            entry = '2000'
            flashMutation = $false
            export = 'selected complete 32K bank as dense S1/S9 plus FNV receipt'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Wdcmonv2ArchiveS19Path).Hash
        }
        wdcmonv2InstallS19 = [ordered]@{
            file = 'BUILD/v1.30/s19/str8n-v1.30-wdcmonv2-install-2000.s19'
            ramStart = ('{0:X4}' -f $wdcmonv2InstallStart)
            ramEnd = ('{0:X4}' -f ($wdcmonv2InstallEnd - 1))
            entry = '2000'
            receiveBufferStart = '4000'
            receiveBufferEnd = '4FFF'
            externalCandidate = 'exact canonical 4096-byte top BIN; directory empty; FFF0=1E WORK; FFF1=1F top backup'
            destinationPolicy = 'B0 erased or byte-identical to B3; B1/B2 untouched; B3:F last'
            hardwareStatus = 'v1.30 host-verified; factory migration hardware proof operator-deferred'
            candidateTopBin = 'BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin'
            candidateTopSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Wdcmonv2InstallTopBinPath).Hash
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Wdcmonv2InstallS19Path).Hash
        }
        publicContract = [ordered]@{
            file = 'BUILD/v1.30/include/str8n-public.inc'
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $PublicContractPath).Hash
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
        workSectorAddress = 'FFF0'
        workSector = 'B1:E'
        workSectorPacked = '1E'
        topBackupSectorAddress = 'FFF1'
        topBackupSector = 'B1:F'
        topBackupSectorPacked = '1F'
        reservedConfigurationStart = 'FFF2'
        reservedConfigurationEnd = 'FFF9'
        vectorsStart = 'FFFA'
        vectorsEnd = 'FFFF'
    }
    abi = [ordered]@{
        ramVersion = 18
        lowUserStart = '1A00'
        lowUserEnd = '1FFF'
        highToolStart = '7C00'
        highToolEnd = '7DBF'
        himonApLinkStart = '7DC0'
        himonApLinkEnd = '7DC7'
        str8StateStart = '7DE9'
        str8StateEnd = '7DFF'
        bankJumpRecordStart = '7DFD'
        bankJumpRecordEnd = '7DFF'
        bankJumpSig0 = '7DFD'
        bankJumpSig1 = '7DFE'
        bankLastJump = '7DFF'
        bankJumpSignature = 'BJ'
        bankCount = 4
        bankNone = 255
        bankStateByte = '7FEC'
        asmTargetEndExclusive = '7D00'
        residentVersion = 1
        residentCapabilities = 63
        consoleInitService = 'F003'
        abiQueryService = 'F006'
        recordService = 'F009'
        recordVersion = 2
        recordCapabilities = 3
        bankSelectService = 'F010'
        charInService = 'F013'
        charOutService = 'F019'
        charReadyService = 'F03E'
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
Write-Host ('BANK MAINT SHA-256  = {0}' -f $manifest.artifacts.bankMaintenanceS19.sha256)
Write-Host ('CONSOLE ABI SHA-256 = {0}' -f $manifest.artifacts.consoleAbiTestS19.sha256)
Write-Host ('TOP UPDATE SHA-256   = {0}' -f $manifest.artifacts.topUpdateS19.sha256)
Write-Host ('DIR REFRESH SHA-256  = {0}' -f $manifest.artifacts.directoryRefreshS19.sha256)
Write-Host ('WDC ARCHIVE SHA-256  = {0}' -f $manifest.artifacts.wdcmonv2ArchiveS19.sha256)
Write-Host ('WDC INSTALL SHA-256  = {0}' -f $manifest.artifacts.wdcmonv2InstallS19.sha256)
Write-Host ('WDC TOP BIN SHA-256  = {0}' -f $manifest.artifacts.wdcmonv2InstallS19.candidateTopSha256)
Write-Host ('PUBLIC ABI SHA-256   = {0}' -f $manifest.artifacts.publicContract.sha256)
