param(
    [string]$PackageDir = 'BUILD/v1.29/str8n-v1.29-release',
    [string]$ZipPath = 'BUILD/v1.29/str8n-v1.29-release.zip'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$files = [ordered]@{
    'ARTIFACTS/str8n-v1.29-bank3-f000-ffff.bin' = 'BUILD/v1.29/bin/str8n-v1.29-bank3-f000-ffff.bin'
    'ARTIFACTS/str8n-v1.29-f000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-f000.s19'
    'ARTIFACTS/str8n-v1.29-worker-0200.s19' = 'BUILD/v1.29/s19/str8n-v1.29-worker-0200.s19'
    'ARTIFACTS/str8n-v1.29-bank-maint-2000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-bank-maint-2000.s19'
    'ARTIFACTS/str8n-v1.29-bank-maint-menu-2000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-bank-maint-menu-2000.s19'
    'ARTIFACTS/str8n-v1.29-bank-maint-menu-2000.a' = 'tools/bank-maint/str8n-v1.29-bank-maint-menu-2000.a'
    'ARTIFACTS/str8n-v1.29-top-update-2000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-top-update-2000.s19'
    'ARTIFACTS/str8n-v1.29-directory-refresh-2000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-directory-refresh-2000.s19'
    'ARTIFACTS/str8n-v1.29-console-abi-test-2000.s19' = 'BUILD/v1.29/s19/str8n-v1.29-console-abi-test-2000.s19'
    'INCLUDE/str8n-public.inc' = 'BUILD/v1.29/include/str8n-public.inc'
    'MANIFEST/str8n-manifest.json' = 'BUILD/str8n-manifest.json'
    'PACKAGES/str8n-v1.29-wdcmonv2-str8n-migration-kit.zip' = 'BUILD/v1.29/str8n-v1.29-wdcmonv2-str8n-migration-kit.zip'
    'DOC/README.md' = 'README.md'
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
STR8-N v1.29 release package

This package contains only STR8-N v1.29 deliverables and documentation.
It contains no WDCMONv2 firmware, owner bank archive, HIMON, ASM-F2, or R-YORS payload.

Primary installation images:
  ARTIFACTS/str8n-v1.29-bank3-f000-ffff.bin  external programmer, B3:F
  ARTIFACTS/str8n-v1.29-f000.s19             resident S19

Maintenance and recovery:
  ARTIFACTS/str8n-v1.29-bank-maint-2000.s19
  ARTIFACTS/str8n-v1.29-bank-maint-menu-2000.s19
  ARTIFACTS/str8n-v1.29-top-update-2000.s19
  ARTIFACTS/str8n-v1.29-directory-refresh-2000.s19

Factory WDCMONv2 onboarding is the separately verified nested ZIP in PACKAGES.
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
