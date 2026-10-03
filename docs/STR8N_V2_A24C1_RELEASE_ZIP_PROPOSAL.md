# STR8-N 2.0a24c1 release ZIP contents

Local archive: `str8n-v2-a24c1-board-test.zip`. The agreed contents
are the scripts, BIN/S19 images, documentation, and public assembly include.
This is the original board-test package inventory. The archive is built locally at
`output/release/str8n-v2-a24c1-board-test.zip` using
`python tools/package_v2_a24c1.py`. The ZIP is distributed through the repository.
The owner reported a successful native Linux run on 2026-10-02.

Beta 1 is `str8n-v2-b1.zip`, built with
`python tools/package_v2_a24c1.py --beta1`. It retains all 18 kit files and
their tested firmware/launcher names, and adds five Markdown files:
`BETA1-RELEASE-NOTES.md`, `MIGRATION-RESET-ACCEPTANCE.md`,
`COLD-CONFIG-ACCEPTANCE.md`, `REGRESSION-ACCEPTANCE.md`, and
`BACKUP-RECOVERY-ACCEPTANCE.md`, all under `docs/`. PDFs are refreshed.
See the [beta notes](STR8N_V2_BETA1_RELEASE_NOTES.md) for scope and identity.

## Agreed file list

```text
INSTALL-A24C1.ps1
start_wdcmonv2_ram.ps1
INSTALL-A24C1.sh
install_a24c1_linux.py
str8n-v2-a24c1-wdcmonv2-install-2000.s19
str8n-v2-a24c1-f000-ffff.bin
str8n-bank-maint-2000.s19

docs/
  QUICKSTART.pdf
  QUICKSTART.md
  TECHNICAL-GUIDE.md
  OPERATORS-MANUAL.pdf
  OPERATORS-MANUAL.md
  MAPS.pdf
  MAPS.md
  CONFIGURATION.md
  INSTALLER-GUIDE.md
  BANK-MAINTENANCE.md

PUBLIC/
  str8n-v2-public.inc
```

The public include comes from `src/v2-config/str8n-v2-public.inc`. It provides
named entry addresses, capability flags and interrupt pointers for application
developers. Installation does not require assembling it.

The detailed technical guide contains the Mermaid diagrams. The quick start
is the entry point. Package document names above are shorter than repository
source names; rewrite local document links when staging the package.

## Preparation checks

Keep both launchers, their bridge scripts, and the three image files together
at the ZIP root. Linux requires Python 3 and pyserial; these system dependencies
are not bundled. The Linux shell launcher uses its own location to resolve files.
Check that the installer and core match and that maintenance remains version
1.0. Validate the extracted launcher with `-ValidateOnly`, check file hashes
against the build inputs, and inspect document links before distribution.
These checks are performed during packaging; their logs are not bundled.

## Excluded files

No onboarding document, package manifests, checksum inventories, verification
script, validation receipts, source listings, objects, temporary files,
firmware dumps, private backups, historical installers, or a24c2 proposals.
Board-specific installed-firmware updaters are generated separately.
