param(
    [string]$Root = $PSScriptRoot,
    [string]$ZipPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
$canonicalHash = '96416190B7E1A37E2C01A407AB9C8EA4ADE06855BBFD0DDCC306FF68418A359A'
$expected = @(
    'README.md', 'CHECK-LINKS.ps1',
    'DOC/HIMON_ASMF2_AFTER_STR8N.md', 'DOC/SOFTWARE_CATALOG.md', 'DOC/R_YORS_INTEGRATION.md',
    'ARTIFACTS/str8n-v1.35-bank3-f000-ffff.bin',
    'ARTIFACTS/str8n-v1.35-f000.s19',
    'ARTIFACTS/str8n-v1.35-worker-0200.s19',
    'ARTIFACTS/str8n-v1.35-bank-maint-2000.s19',
    'ARTIFACTS/str8n-v1.35-bank-maint-menu-2000.s19',
    'APPLICATIONS/str8n-v1.35-bank-maint-menu-2000.a',
    'ARTIFACTS/str8n-v1.35-top-update-2000.s19',
    'ARTIFACTS/str8n-v1.35-directory-refresh-2000.s19',
    'TESTS/str8n-v1.35-console-abi-test-2000.s19',
    'TESTS/str8n-v1.35-irq-test-2000.s19',
    'TESTS/str8n-v1.35-led-worker-test-2000.s19',
    'TESTS/README.md',
    'TOOLS/convert_guest_bin_to_s19.ps1',
    'TOOLS/compose_str8n_install_s19.ps1',
    'INCLUDE/str8n-public.inc',
    'MANIFEST/str8n-manifest.json',
    'PACKAGES/str8n-v1.35-wdcmonv2-str8n-migration-kit.zip',
    'DOC/OPERATORS_GUIDE.md',
    'DOC/TECHNICAL_GUIDE.md',
    'DOC/CONFIGURATION_BYTES.md',
    'DOC/EXAMPLES.md',
    'DOC/MAPS.md',
    'DOC/BANK_0_2_GUEST_S19.md',
    'DOC/RESET_SOURCE_CONTRACT.md',
    'DOC/STR8_IN65_BANK_MAINTENANCE.md',
    'DOC/WDCMONV2_MIGRATION.md',
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md',
    'DOC/STR8N_V1_34_SIZE_OPTIMIZATION.md',
    'DOC/STR8N_V1_35_BOARD_TEST_2026-09-16.md',
    'DOC/STR8N_V1_34_BOARD_TEST_2026-09-15.md',
    'DOC/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md',
    'DOC/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md',
    'VERIFY-PACKAGE.ps1', 'LICENSE', 'PACKAGE-README.txt',
    'PACKAGE-MANIFEST.json', 'SHA256SUMS.txt'
) | Sort-Object
$actual = @(Get-ChildItem -LiteralPath $rootFull -Recurse -File | ForEach-Object {
    $_.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
} | Sort-Object)
if (($actual -join [char]10) -cne ($expected -join [char]10)) { throw 'Standalone release file allowlist mismatch' }

$checked = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $rootFull 'SHA256SUMS.txt')) {
    if ($line -notmatch '^([0-9A-F]{64})  (.+)$') { throw "Invalid checksum row: $line" }
    $hash, $relative = $Matches[1], $Matches[2]
    if ($relative -notin $expected -or $relative -eq 'SHA256SUMS.txt' -or $checked.ContainsKey($relative)) {
        throw "Unexpected or repeated checksum path: $relative"
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $rootFull $relative)).Hash -ne $hash) {
        throw "Checksum mismatch: $relative"
    }
    $checked[$relative] = $hash
}
if ($checked.Count -ne ($expected.Count - 1)) { throw 'Checksum inventory is incomplete' }

$manifest = Get-Content -Raw -LiteralPath (Join-Path $rootFull 'PACKAGE-MANIFEST.json') | ConvertFrom-Json
if ($manifest.schema -ne 1 -or $manifest.product -ne 'STR8-N' -or $manifest.version -ne '1.35' -or
        $manifest.canonicalTopSha256 -ne $canonicalHash -or
        $manifest.stockWdcmonv2FirmwareIncluded -ne $false -or
        $manifest.localBankArchivesIncluded -ne $false -or $manifest.otherProductPayloadsIncluded -ne $false) {
    throw 'Standalone release identity/provenance is invalid'
}
$manifestNames = @($manifest.files | ForEach-Object { $_.file } | Sort-Object)
$payloadNames = @($expected | Where-Object { $_ -notin @('PACKAGE-MANIFEST.json', 'SHA256SUMS.txt') })
if (($manifestNames -join [char]10) -cne ($payloadNames -join [char]10)) { throw 'Manifest inventory mismatch' }
foreach ($row in $manifest.files) {
    $path = Join-Path $rootFull $row.file
    if ([int64]$row.bytes -ne (Get-Item -LiteralPath $path).Length -or $row.sha256 -ne $checked[$row.file]) {
        throw "Manifest length/hash mismatch: $($row.file)"
    }
}

function Read-S19 {
    param([string]$Relative)
    $data = @{}
    $entry = -1
    foreach ($raw in Get-Content -LiteralPath (Join-Path $rootFull $Relative)) {
        $line = $raw.Trim()
        if (-not $line) { continue }
        if ($line -notmatch '^S([19])([0-9A-Fa-f]+)$' -or ($line.Length % 2) -ne 0 -or $entry -ge 0) {
            throw "Malformed or post-entry S-record in $Relative"
        }
        $kind, $hex = $Matches[1], $Matches[2]
        $bytes = @(for ($i = 0; $i -lt $hex.Length; $i += 2) { [Convert]::ToInt32($hex.Substring($i, 2), 16) })
        $sum = 0
        foreach ($value in $bytes) { $sum = ($sum + $value) -band 255 }
        if ($bytes.Count -lt 4 -or $bytes[0] -ne ($bytes.Count - 1) -or $sum -ne 255) {
            throw "S-record count/checksum mismatch in $Relative"
        }
        $address = ($bytes[1] -shl 8) -bor $bytes[2]
        if ($kind -eq '9') {
            if ($bytes.Count -ne 4) { throw "Malformed S9 in $Relative" }
            $entry = $address
        } else {
            for ($i = 3; $i -lt ($bytes.Count - 1); $i++) {
                if ($address -gt 65535 -or $data.ContainsKey($address)) { throw "Overlapping/wrapped data in $Relative" }
                $data[$address] = $bytes[$i]
                $address++
            }
        }
    }
    if ($entry -lt 0 -or $data.Count -eq 0) { throw "Incomplete S19: $Relative" }
    return [pscustomobject]@{ Data = $data; Entry = $entry }
}

$images = @{}
foreach ($relative in @($expected | Where-Object { $_.EndsWith('.s19') })) {
    $image = Read-S19 $relative
    $images[$relative] = $image
    $resident = $relative -eq 'ARTIFACTS/str8n-v1.35-f000.s19'
    $worker = $relative -eq 'ARTIFACTS/str8n-v1.35-worker-0200.s19'
    $low, $high, $entry = 0x2000, 0x4FFF, 0x2000
    if ($resident) { $low, $high, $entry = 0xF000, 0xFFFF, 0xF000 }
    elseif ($worker) { $low, $high, $entry = 0x0200, 0x0437, 0x0200 }
    if ($image.Entry -ne $entry) { throw "Unexpected S9 entry: $relative" }
    foreach ($address in $image.Data.Keys) {
        if ($address -lt $low -or $address -gt $high) { throw "Unexpected S19 address in $relative" }
    }
}

$topPath = Join-Path $rootFull 'ARTIFACTS/str8n-v1.35-bank3-f000-ffff.bin'
$top = [IO.File]::ReadAllBytes($topPath)
if ($top.Length -ne 4096 -or (Get-FileHash -Algorithm SHA256 -LiteralPath $topPath).Hash -ne $canonicalHash) {
    throw 'Canonical top differs from the hardware-accepted v1.35 firmware'
}
foreach ($item in $images['ARTIFACTS/str8n-v1.35-f000.s19'].Data.GetEnumerator()) {
    if ($top[$item.Key - 0xF000] -ne $item.Value) { throw 'Resident S19 differs from canonical BIN' }
}
foreach ($name in @('bank-maint-menu', 'top-update')) {
    $data = $images[('ARTIFACTS/str8n-v1.35-{0}-2000.s19' -f $name)].Data
    for ($i = 0; $i -lt 4096; $i++) {
        if (-not $data.ContainsKey(0x4000 + $i) -or $data[0x4000 + $i] -ne $top[$i]) {
            throw "Embedded top differs from canonical BIN: $name"
        }
    }
}

$source = @{}
$address = -1
$ended = $false
foreach ($raw in Get-Content -LiteralPath (Join-Path $rootFull 'APPLICATIONS/str8n-v1.35-bank-maint-menu-2000.a')) {
    $line = ($raw -split ';', 2)[0].Trim()
    if (-not $line) { continue }
    if ($ended -or $line.Length -gt 63) { throw 'Invalid maintenance .a line or data after END' }
    if ($line -match '^ORG \$([0-9A-F]{4})$') { $address = [Convert]::ToInt32($Matches[1], 16) }
    elseif ($line -match '^DB (\$[0-9A-F]{2})(,\$[0-9A-F]{2})*$') {
        foreach ($value in [regex]::Matches($line, '\$([0-9A-F]{2})')) {
            if ($address -lt 0 -or $source.ContainsKey($address)) { throw 'Invalid maintenance .a address' }
            $source[$address] = [Convert]::ToInt32($value.Groups[1].Value, 16)
            $address++
        }
    } elseif ($line -eq 'END') { $ended = $true }
    else { throw "Unexpected maintenance .a syntax: $line" }
}
$menu = $images['ARTIFACTS/str8n-v1.35-bank-maint-menu-2000.s19'].Data
if (-not $ended -or $source.Count -ne 12288 -or $source.Count -ne $menu.Count) { throw 'Maintenance .a size mismatch' }
foreach ($item in $source.GetEnumerator()) {
    if (-not $menu.ContainsKey($item.Key) -or $menu[$item.Key] -ne $item.Value) { throw 'Maintenance .a/S19 byte mismatch' }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Get-ZipBytes {
    param($Archive, [string]$Name)
    $entry = $Archive.GetEntry($Name)
    if ($null -eq $entry) { throw "Missing ZIP entry: $Name" }
    $input = $entry.Open()
    $buffer = [IO.MemoryStream]::new()
    try { $input.CopyTo($buffer); return ,$buffer.ToArray() }
    finally { $input.Dispose(); $buffer.Dispose() }
}
function Get-BytesHash {
    param([byte[]]$Bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '') }
    finally { $sha.Dispose() }
}
$migrationNames = @(
    'CHECK-LINKS.ps1',
    'STR8-iN65-LOADER.ps1', 'STR8-iN65-LOADER.py', 'QUICKSTART.txt',
    'ARTIFACTS/STR8-iN65-ARCHIVE-2000.s19', 'ARTIFACTS/STR8-iN65-BANK-MAINT-2000.s19',
    'ARTIFACTS/STR8-iN65-LOADER-2000.s19', 'ARTIFACTS/STR8-N-v1-30.bin', 'ARTIFACTS/STR8-N-v1-30.s19',
    'DOC/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md',
    'DOC/HIMON_ASMF2_AFTER_STR8N.md', 'DOC/STR8_IN65_BANK_MAINTENANCE.md',
    'DOC/CONFIGURATION_BYTES.md',
    'DOC/WDCMONV2_MIGRATION.md', 'DOC/WDCMONV2_MIGRATION_BOARD_TEST.md',
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md', 'LICENSE', 'PACKAGE-MANIFEST.json', 'PACKAGE-README.txt',
    'SOURCE/str8n-v1.35-wdcmonv2-install-image.inc', 'SOURCE/wdcmonv2str8n-archive-2000.asm',
    'SOURCE/wdcmonv2str8n-install-2000.asm', 'TOOLS/check_wdcmonv2_archive.ps1',
    'TOOLS/check_wdcmonv2_install.ps1', 'TOOLS/extract_wdcmonv2_archive.ps1',
    'TOOLS/start_wdcmonv2_ram.ps1', 'TOOLS/start_wdcmonv2_ram.py', 'VERIFY-PACKAGE.ps1'
) | Sort-Object
$prefix = 'STR8-N-v1.35-Migration-Kit/'
$zip = [IO.Compression.ZipFile]::OpenRead((Join-Path $rootFull 'PACKAGES/str8n-v1.35-wdcmonv2-str8n-migration-kit.zip'))
try {
    $names = @($zip.Entries | Where-Object Name | ForEach-Object FullName | Sort-Object)
    $wanted = @($migrationNames | ForEach-Object { $prefix + $_ } | Sort-Object)
    if (($names -join [char]10) -cne ($wanted -join [char]10)) { throw 'Nested migration ZIP allowlist mismatch' }
    $m = [Text.Encoding]::UTF8.GetString((Get-ZipBytes $zip ($prefix + 'PACKAGE-MANIFEST.json'))) | ConvertFrom-Json
    if ($m.stockWdcmonv2FirmwareIncluded -ne $false -or $m.localBankArchivesIncluded -ne $false -or
            $m.ryorsPayloadIncluded -ne $false -or $m.hardwareStatus -ne 'v1.35 factory migration has no board proof; prior v1.34 Windows factory migration passed on 2026-09-15; Linux has no board proof') {
        throw 'Nested migration provenance mismatch'
    }
    $rowNames = @($m.files | ForEach-Object file | Sort-Object)
    if (($rowNames -join [char]10) -cne (($migrationNames | Where-Object { $_ -ne 'PACKAGE-MANIFEST.json' }) -join [char]10)) {
        throw 'Nested migration manifest inventory mismatch'
    }
    foreach ($row in $m.files) {
        $bytes = Get-ZipBytes $zip ($prefix + $row.file)
        if ($bytes.Length -ne $row.bytes -or (Get-BytesHash $bytes) -ne $row.sha256) { throw 'Nested migration hash mismatch' }
    }
    if ((Get-BytesHash (Get-ZipBytes $zip ($prefix + 'ARTIFACTS/STR8-N-v1-30.bin'))) -ne $canonicalHash) {
        throw 'Nested migration BIN differs from canonical top'
    }
} finally { $zip.Dispose() }

if ($ZipPath) {
    $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($ZipPath))
    try {
        $prefix = 'str8n-v1.35-release/'
        $names = @($zip.Entries | Where-Object Name | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object)
        $wanted = @($expected | ForEach-Object { $prefix + $_ } | Sort-Object)
        if (($names -join [char]10) -cne ($wanted -join [char]10)) { throw 'Release ZIP allowlist mismatch' }
        foreach ($entry in $zip.Entries) {
            if (-not $entry.Name) { continue }
            $name = $entry.FullName.Replace('\', '/').Substring($prefix.Length)
            $hash = Get-BytesHash (Get-ZipBytes $zip $entry.FullName)
            if ($hash -ne (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $rootFull $name)).Hash) {
                throw "Release ZIP differs from staged file: $name"
            }
        }
    } finally { $zip.Dispose() }
}
& (Join-Path $rootFull 'CHECK-LINKS.ps1') -Root $rootFull
Write-Host ('STR8-N v1.35 standalone release PASS; {0} allowlisted files; {1} nested migration files; canonical BIN and maintenance .a verified' -f $expected.Count, $migrationNames.Count)
