param(
    [string]$PackageDir = 'BUILD/v1.35/str8n-v1.35-release',
    [string]$ZipPath = 'BUILD/v1.35/str8n-v1.35-release.zip'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Every distributable input is explicit. Owner archives and other products
# are intentionally outside this standalone product's release inventory.
$files = [ordered]@{
    'README.md' = 'docs/RELEASE_MANUALS.md'
    'CHECK-LINKS.ps1' = 'tools/prepare_release_docs.ps1'
    'DOC/HIMON_ASMF2_AFTER_STR8N.md' = 'docs/HIMON_ASMF2_AFTER_STR8N.md'
    'DOC/SOFTWARE_CATALOG.md' = 'docs/SOFTWARE_CATALOG.md'
    'DOC/R_YORS_INTEGRATION.md' = 'docs/R_YORS_INTEGRATION.md'
    'ARTIFACTS/str8n-v1.35-bank3-f000-ffff.bin' = 'BUILD/v1.35/bin/str8n-v1.35-bank3-f000-ffff.bin'
    'ARTIFACTS/str8n-v1.35-f000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-f000.s19'
    'ARTIFACTS/str8n-v1.35-worker-0200.s19' = 'BUILD/v1.35/s19/str8n-v1.35-worker-0200.s19'
    'ARTIFACTS/str8n-v1.35-bank-maint-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-bank-maint-2000.s19'
    'ARTIFACTS/str8n-v1.35-bank-maint-menu-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-bank-maint-menu-2000.s19'
    'APPLICATIONS/str8n-v1.35-bank-maint-menu-2000.a' = 'tools/bank-maint/str8n-v1.35-bank-maint-menu-2000.a'
    'ARTIFACTS/str8n-v1.35-top-update-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-top-update-2000.s19'
    'ARTIFACTS/str8n-v1.35-directory-refresh-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-directory-refresh-2000.s19'
    'TESTS/str8n-v1.35-console-abi-test-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-console-abi-test-2000.s19'
    'TESTS/str8n-v1.35-irq-test-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-irq-test-2000.s19'
    'TESTS/str8n-v1.35-led-worker-test-2000.s19' = 'BUILD/v1.35/s19/str8n-v1.35-led-worker-test-2000.s19'
    'TESTS/README.md' = 'tools/interrupt-test/README.md'
    'TOOLS/convert_guest_bin_to_s19.ps1' = 'tools/convert_guest_bin_to_s19.ps1'
    'TOOLS/compose_str8n_install_s19.ps1' = 'tools/compose_str8n_install_s19.ps1'
    'INCLUDE/str8n-public.inc' = 'BUILD/v1.35/include/str8n-public.inc'
    'MANIFEST/str8n-manifest.json' = 'BUILD/str8n-manifest.json'
    'PACKAGES/str8n-v1.35-wdcmonv2-str8n-migration-kit.zip' = 'BUILD/v1.35/str8n-v1.35-wdcmonv2-str8n-migration-kit.zip'
    'DOC/OPERATORS_GUIDE.md' = 'docs/OPERATORS_GUIDE.md'
    'DOC/TECHNICAL_GUIDE.md' = 'docs/TECHNICAL_GUIDE.md'
    'DOC/CONFIGURATION_BYTES.md' = 'docs/CONFIGURATION_BYTES.md'
    'DOC/EXAMPLES.md' = 'docs/EXAMPLES.md'
    'DOC/MAPS.md' = 'docs/MAPS.md'
    'DOC/BANK_0_2_GUEST_S19.md' = 'docs/BANK_0_2_GUEST_S19.md'
    'DOC/RESET_SOURCE_CONTRACT.md' = 'docs/RESET_SOURCE_CONTRACT.md'
    'DOC/STR8_IN65_BANK_MAINTENANCE.md' = 'docs/STR8_IN65_BANK_MAINTENANCE.md'
    'DOC/WDCMONV2_MIGRATION.md' = 'docs/WDCMONV2_MIGRATION.md'
    'DOC/WDCMONV2_MIGRATION_PROVENANCE.md' = 'docs/WDCMONV2_MIGRATION_PROVENANCE.md'
    'DOC/STR8N_V1_34_SIZE_OPTIMIZATION.md' = 'docs/STR8N_V1_34_SIZE_OPTIMIZATION.md'
    'DOC/STR8N_V1_35_BOARD_TEST_2026-09-16.md' = 'docs/STR8N_V1_35_BOARD_TEST_2026-09-16.md'
    'DOC/STR8N_V1_34_BOARD_TEST_2026-09-15.md' = 'docs/STR8N_V1_34_BOARD_TEST_2026-09-15.md'
    'DOC/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md' = 'docs/STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md'
    'DOC/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md' = 'docs/STR8N_V1_34_FACTORY_MIGRATION_BOARD_TEST_2026-09-15.md'
    'VERIFY-PACKAGE.ps1' = 'tools/verify_release_package.ps1'
    'LICENSE' = 'LICENSE'
}

foreach ($source in $files.Values) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing release input: $source" }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $files['ARTIFACTS/str8n-v1.35-bank3-f000-ffff.bin']).Hash -ne
        '96416190B7E1A37E2C01A407AB9C8EA4ADE06855BBFD0DDCC306FF68418A359A') {
    throw 'Canonical firmware differs from the accepted v1.35 image'
}

$releaseRoot = [IO.Path]::GetFullPath('BUILD/v1.35').TrimEnd('\', '/')
$packageFull = [IO.Path]::GetFullPath($PackageDir)
$zipFull = [IO.Path]::GetFullPath($ZipPath)
if ($packageFull -ne (Join-Path $releaseRoot 'str8n-v1.35-release') -or
        $zipFull -ne (Join-Path $releaseRoot 'str8n-v1.35-release.zip')) {
    throw 'Release outputs must be the named v1.35 package directory and ZIP under BUILD/v1.35'
}
# Reject junctions/symlinks before the only recursive deletion.
foreach ($target in @($packageFull, $zipFull)) {
    $ancestor = $target
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and
                ((Get-Item -Force -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Release output traverses a reparse point: $ancestor"
        }
        $ancestor = Split-Path -Parent $ancestor
    }
}
if (Test-Path -LiteralPath $packageFull) { Remove-Item -LiteralPath $packageFull -Recurse -Force }
New-Item -ItemType Directory -Path $packageFull | Out-Null
foreach ($entry in $files.GetEnumerator()) {
    $destination = Join-Path $packageFull $entry.Key
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $entry.Value -Destination $destination
}

& tools/prepare_release_docs.ps1 -Root $packageFull -SourceFiles $files -RepositoryRoot (Get-Location).Path -Commit ((& git rev-parse HEAD).Trim())

$readme = @'
STR8-N v1.35 standalone release

Start with README.md for the manual index, then DOC/OPERATORS_GUIDE.md.

Installation:
  ARTIFACTS/str8n-v1.35-bank3-f000-ffff.bin is the exact 4096-byte
  programmer image for Bank 3 CPU F000-FFFF (device offset 1F000).
  ARTIFACTS/str8n-v1.35-f000.s19 is the resident image for build/integration;
  the resident I command cannot overwrite its own protected top sector.
  Existing STR8-N installations use the guarded RAM top-update image and
  its documented backup/confirmation procedure.

Factory WDC-to-STR8 migration:
  Extract PACKAGES/str8n-v1.35-wdcmonv2-str8n-migration-kit.zip separately.
  Read QUICKSTART.txt and follow the screen. The prior accepted v1.34 Windows
  procedure used -PhysicalResetArmSeconds 60 and RESET during its arm window.
  CTRL+U and CTRL+D send different files; press each once and only when requested.
  After J0, physical RESET is the designed return from the factory system.
  This kit supplies project-written migration tools, not WDC firmware.
  Keep any bank archives created during migration owner-local.

Maintenance:
  ARTIFACTS contains RAM Bank Maintenance, its expanded menu, guarded top
  update, and directory refresh. STR8 L loads and starts their S9 entry.
  Directory refresh replaces directory records; follow its operator guide.
  APPLICATIONS/str8n-v1.35-bank-maint-menu-2000.a is the corresponding
  ASM-F2 DB image carrier: ASM NEW, send the complete file, SEAL> ., G 2000.
  It emits 12288 bytes at 2000-4FFF and embeds the canonical top at 4000.
  ASM-F2 and HIMON are separate prerequisites for this .a workflow.
  Stop on any ERR= response. Its maintenance menu includes flash writes.
  TOOLS supplies guest BIN conversion and dense installer-S19 preparation.
  TESTS contains optional console/interrupt/worker qualification programs;
  the worker test writes/erases a selected sector. Follow its test report.

Qualification:
  v1.35 passed guarded update/readback, policy restoration, physical/software
  reset, and post-reset AM03 handoff checks with exact four-bank readback.
  See DOC/STR8N_V1_35_BOARD_TEST_2026-09-16.md for artifact identities.
  The 2026-09-15 reports describe v1.34 only; their interrupt, worker and
  factory-migration results do not qualify v1.35. The v1.35 factory path,
  Linux migration and broader release matrix remain unqualified.

Verification and redistribution:
  Run powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\VERIFY-PACKAGE.ps1
  The verifier checks the exact inventory, hashes, S-records, canonical
  firmware, maintenance .a/S19 equality, and the nested migration inventory.
  CHECK-LINKS.ps1 checks local manual destinations and headings. Historical
  evidence not bundled here links to the source repository at the recorded commit.
  PACKAGE-MANIFEST.json records packaging time and unchanged firmware identity.
  SHA256SUMS.txt covers every other packaged file, including the manifest.
  LICENSE is the project MIT license. No WDC tools, WDCMON firmware, stock
  bank images, owner captures, HIMON/ASM payloads, or games are included.
  HIMON and ASM-F2 applications are distributed in their own release packages.
'@
$utf8 = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $packageFull 'PACKAGE-README.txt'), $readme, $utf8)
$rows = @(Get-ChildItem -LiteralPath $packageFull -Recurse -File | Sort-Object FullName | ForEach-Object {
    [ordered]@{
        file = $_.FullName.Substring($packageFull.Length + 1).Replace('\', '/')
        bytes = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
    }
})
$manifest = [ordered]@{
    schema = 1
    product = 'STR8-N'
    version = '1.35'
    packagedUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    canonicalTopSha256 = '96416190B7E1A37E2C01A407AB9C8EA4ADE06855BBFD0DDCC306FF68418A359A'
    sourceCommit = (& git rev-parse HEAD).Trim()
    sourceDirty = -not [string]::IsNullOrWhiteSpace((& git status --porcelain))
    stockWdcmonv2FirmwareIncluded = $false
    localBankArchivesIncluded = $false
    otherProductPayloadsIncluded = $false
    files = $rows
}
[IO.File]::WriteAllText((Join-Path $packageFull 'PACKAGE-MANIFEST.json'),
    ($manifest | ConvertTo-Json -Depth 5) + [Environment]::NewLine, $utf8)
$sums = @(Get-ChildItem -LiteralPath $packageFull -Recurse -File | ForEach-Object {
    '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash,
        $_.FullName.Substring($packageFull.Length + 1).Replace('\', '/')
} | Sort-Object)
[IO.File]::WriteAllLines((Join-Path $packageFull 'SHA256SUMS.txt'), $sums, $utf8)

& (Join-Path $packageFull 'VERIFY-PACKAGE.ps1') -Root $packageFull
if (Test-Path -LiteralPath $zipFull) { Remove-Item -LiteralPath $zipFull -Force }
Compress-Archive -LiteralPath $packageFull -DestinationPath $zipFull -CompressionLevel Optimal
& (Join-Path $packageFull 'VERIFY-PACKAGE.ps1') -Root $packageFull -ZipPath $zipFull
Write-Host "STR8-N RELEASE PACKAGE = $zipFull"
Write-Host "SHA-256 = $((Get-FileHash -Algorithm SHA256 -LiteralPath $zipFull).Hash)"
