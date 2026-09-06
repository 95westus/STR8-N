param(
    [string]$PackageDir = 'BUILD/v1.30/str8n-v1.30-release',
    [string]$ZipPath = 'BUILD/v1.30/str8n-v1.30-release.zip',
    [string]$RyorsRelease = '../R-YORS/RELEASE'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$files = [ordered]@{
    'ARTIFACTS/str8n-v1.30-bank3-f000-ffff.bin' = 'BUILD/v1.30/bin/str8n-v1.30-bank3-f000-ffff.bin'
    'ARTIFACTS/str8n-v1.30-f000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-f000.s19'
    'ARTIFACTS/str8n-v1.30-worker-0200.s19' = 'BUILD/v1.30/s19/str8n-v1.30-worker-0200.s19'
    'ARTIFACTS/str8n-v1.30-bank-maint-2000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-bank-maint-2000.s19'
    'ARTIFACTS/str8n-v1.30-bank-maint-menu-2000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-bank-maint-menu-2000.s19'
    'ARTIFACTS/str8n-v1.30-bank-maint-menu-2000.a' = 'tools/bank-maint/str8n-v1.30-bank-maint-menu-2000.a'
    'ARTIFACTS/str8n-v1.30-top-update-2000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-top-update-2000.s19'
    'ARTIFACTS/str8n-v1.30-directory-refresh-2000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-directory-refresh-2000.s19'
    'ARCHIVE/TESTS/str8n-v1.30-console-abi-test-2000.s19' = 'BUILD/v1.30/s19/str8n-v1.30-console-abi-test-2000.s19'
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/ryors-v1.2-himon-bank3-c-e.s19')
    'OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/ryors-v1.2-asm-bank3-8-b.s19')
    'OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19' = (Join-Path $RyorsRelease 'ryors-v1.2-himon-asm-bank3-8-e.s19')
    'OPTIONAL/HIMON-ASM/INSTALL.md' = 'docs/HIMON_ASMF2_AFTER_STR8N.md'
    'SOFTWARE/README.md' = 'docs/SOFTWARE_CATALOG.md'
    'SOFTWARE/GAMES/life-2000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/life-2000.s19')
    'SOFTWARE/DEMOS/pia-led-show-2000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/pia-led-show-2000.s19')
    'SOFTWARE/UTILITIES/bank-audit-2000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/bank-audit-2000.s19')
    'SOFTWARE/UTILITIES/bank-dump-2000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/bank-dump-2000.s19')
    'SOFTWARE/ASM-SOURCES/asm-session-report-ap-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/asm-session-report-v1.2-ap-2000.a')
    'SOFTWARE/ASM-SOURCES/bank-audit-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/bank-audit-2000.a')
    'SOFTWARE/ASM-SOURCES/bank-crc-all-3000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/str8n-v1.2-bank-crc-all-3000.a')
    'SOFTWARE/ASM-SOURCES/bank-dump-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/bank-dump-2000.a')
    'SOFTWARE/ASM-SOURCES/flash-bank-dump-ap-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/str8n-v1.2-flash-bank-dump-ap-2000.a')
    'SOFTWARE/ASM-SOURCES/flash-bank-read-ap-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/str8n-v1.2-flash-bank-read-ap-2000.a')
    'SOFTWARE/ASM-SOURCES/pia-led-show-2000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/pia-led-show-2000.a')
    'SOFTWARE/ASM-SOURCES/terminal-answerback-vt100-3000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/terminal-answerback-vt100-3000.a')
    'SOFTWARE/ASM-SOURCES/vt102-exerciser-7000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/vt102-exerciser-7000.a')
    'SOFTWARE/ASM-SOURCES/vt525-exerciser-7000.a' = (Join-Path $RyorsRelease 'ARTIFACTS/SOURCES/vt525-exerciser-7000.a')
    'SOFTWARE/ADVANCED/APMAN/apman-7000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/apman-7000.s19')
    'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/apman-v1-bank2-8000.s19')
    'SOFTWARE/ADVANCED/APMAN/apman-v1-bank2-8000.bin' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/apman-v1-bank2-8000.bin')
    'SOFTWARE/ADVANCED/APMAN/apman-v1.ap' = (Join-Path $RyorsRelease 'ARTIFACTS/COMPONENT-IMAGES/apman-v1.ap')
    'SOFTWARE/ADVANCED/APMAN/APMAN_V1_BOARD_TEST.md' = (Join-Path $RyorsRelease 'BOARD-CARDS/APMAN_V1_BOARD_TEST.md')
    'SOFTWARE/ADVANCED/AP-STORE/ap-store-v1-chain-install-tool-package-4000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/AP-STORE/ap-store-v1-chain-install-tool-package-4000.s19')
    'SOFTWARE/ADVANCED/AP-STORE/ap-store-v1-slice6-catalog-tool-package-4000.s19' = (Join-Path $RyorsRelease 'ARTIFACTS/AP-STORE/ap-store-v1-slice6-catalog-tool-package-4000.s19')
    'SOFTWARE/UTILITIES/BANK_AUDIT_AP_CARD.md' = (Join-Path $RyorsRelease 'BOARD-CARDS/BANK_AUDIT_AP_CARD.md')
    'SOFTWARE/UTILITIES/BANK_DUMP_AP_CARD.md' = (Join-Path $RyorsRelease 'BOARD-CARDS/BANK_DUMP_AP_CARD.md')
    'INCLUDE/str8n-public.inc' = 'BUILD/v1.30/include/str8n-public.inc'
    'MANIFEST/str8n-manifest.json' = 'BUILD/str8n-manifest.json'
    'PACKAGES/str8n-v1.30-wdcmonv2-str8n-migration-kit.zip' = 'BUILD/v1.30/str8n-v1.30-wdcmonv2-str8n-migration-kit.zip'
    'DOC/README.md' = 'README.md'
    'DOC/STR8N_V1_30_RECLAIM.md' = 'docs/STR8N_V1_30_RECLAIM.md'
    'DOC/STR8N_V1_30_BOARD_TRANSCRIPT.txt' = 'docs/STR8N_V1_30_BOARD_TRANSCRIPT.txt'
    'DOC/OPERATORS_GUIDE.md' = 'docs/OPERATORS_GUIDE.md'
    'DOC/TECHNICAL_GUIDE.md' = 'docs/TECHNICAL_GUIDE.md'
    'DOC/STR8_IN65_BANK_MAINTENANCE.md' = 'docs/STR8_IN65_BANK_MAINTENANCE.md'
    'DOC/WDCMONV2_MIGRATION.md' = 'docs/WDCMONV2_MIGRATION.md'
    'VERIFY-PACKAGE.ps1' = 'tools/verify_release_package.ps1'
    'LICENSE' = 'LICENSE'
}

foreach ($source in $files.Values) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing release input: $source" }
}

$packageFull = [IO.Path]::GetFullPath($PackageDir)
$zipFull = [IO.Path]::GetFullPath($ZipPath)
if (Test-Path -LiteralPath $packageFull) { Remove-Item -LiteralPath $packageFull -Recurse -Force }
New-Item -ItemType Directory -Path $packageFull | Out-Null

foreach ($entry in $files.GetEnumerator()) {
    $destination = Join-Path $packageFull $entry.Key
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $entry.Value -Destination $destination
}

$readme = @'
STR8-N v1.30 release package

This package contains STR8-N v1.30 deliverables, documentation, and clearly
separated optional HIMON/ASM-F2 payloads. It contains no WDCMONv2 firmware or
owner bank archive.

Primary installation images:
  ARTIFACTS/str8n-v1.30-bank3-f000-ffff.bin  external programmer, B3:F
  ARTIFACTS/str8n-v1.30-f000.s19             resident S19

Maintenance and recovery:
  ARTIFACTS/str8n-v1.30-bank-maint-2000.s19
  ARTIFACTS/str8n-v1.30-bank-maint-menu-2000.s19
  ARTIFACTS/str8n-v1.30-top-update-2000.s19
  ARTIFACTS/str8n-v1.30-directory-refresh-2000.s19

Archived hardware proof:
  ARCHIVE/TESTS/str8n-v1.30-console-abi-test-2000.s19

Optional HIMON and ASM-F2:
  OPTIONAL/HIMON-ASM/ryors-v1.2-himon-bank3-c-e.s19
  OPTIONAL/HIMON-ASM/ryors-v1.2-asm-bank3-8-b.s19
  OPTIONAL/HIMON-ASM/ryors-v1.2-himon-asm-bank3-8-e.s19
  OPTIONAL/HIMON-ASM/INSTALL.md

Use the combined 8-E image for the simplest new Bank-3 installation, or use
the separate C-E and 8-B images when installing/updating one component at a time.

Current compatible software:
  SOFTWARE/README.md
  SOFTWARE/GAMES                 ready-to-load game S19
  SOFTWARE/DEMOS                 ready-to-load hardware demo S19
  SOFTWARE/UTILITIES             ready-to-load maintenance S19 and cards
  SOFTWARE/ASM-SOURCES           maintained onboard ASM-F2 sources
  SOFTWARE/ADVANCED              APMAN and AP Store packages

Factory WDCMONv2 onboarding is the separately verified nested ZIP in PACKAGES.
Read its QUICKSTART.txt and follow the screen. CTRL+U and CTRL+D send different
packaged files; press each once and only when requested. After J0, physical
RESET is the designed return from the preserved factory system to STR8-N.
Run VERIFY-PACKAGE.ps1 after extracting this archive.
'@
[IO.File]::WriteAllText((Join-Path $packageFull 'PACKAGE-README.txt'), $readme, [Text.UTF8Encoding]::new($false))

$rows = Get-ChildItem -LiteralPath $packageFull -Recurse -File |
    Where-Object Name -ne 'SHA256SUMS.txt' |
    ForEach-Object {
        $relative = $_.FullName.Substring($packageFull.TrimEnd('\', '/').Length + 1).Replace('\', '/')
        '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash, $relative
    } | Sort-Object
[IO.File]::WriteAllLines((Join-Path $packageFull 'SHA256SUMS.txt'), $rows, [Text.UTF8Encoding]::new($false))

if (Test-Path -LiteralPath $zipFull) { Remove-Item -LiteralPath $zipFull -Force }
Compress-Archive -LiteralPath $packageFull -DestinationPath $zipFull -CompressionLevel Optimal
Write-Host "STR8-N RELEASE PACKAGE = $zipFull"
Write-Host "SHA-256 = $((Get-FileHash -Algorithm SHA256 -LiteralPath $zipFull).Hash)"
