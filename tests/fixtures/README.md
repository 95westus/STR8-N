# Offline installer compatibility fixtures

`installer-profiles.zip` holds the four historical generic firmware profiles still
accepted by the current installer: `release-r9`, `source-store`, `maint-source`,
and `console-edit`. Each is the original 98,304-byte project image recorded by
Phase 1. The fixture manifest checks every image against both the immutable
Phase 1 manifest and the current installer registry. These are generic build
artifacts, with no board captures, RAM backups, owner settings, or serial logs.
The selected current target is built afresh from `src/current` by the regression
suite. The current target is again `asm-dev`, with the original G/CRC code.
`asm-dev-regression.bin` retains the earlier generic asm-dev image exclusively for
the historical upgrade/cleanup differential checks. Its SHA-256 must match the
installer registry (`aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6`).
An explicit `--firmware` argument supplies that historical regression image.

The ZIP uses sorted member names, a fixed 1980-01-01 timestamp, Unix regular-file
mode 0644, and DEFLATE level 9. Its SHA-256 and the uncompressed image hashes are
recorded in `installer-fixtures.json`. Extracted test files are disposable.

The two transaction JSON fixtures came from the successful Phase 4 isolated
historical differential run (`tmp/p4-final2/old-generic-plan/plan.json` and
`tmp/p4-final2/old-cleanup-plan/plan.json`). They describe synthetic test data.
Only the descriptive transaction `label` was omitted; every operation, source
and target digest, erase order, settings value, and wear reservation remains.
JSON keys are sorted, with two-space indentation and a final LF. The original
plan hash and canonical transaction-file hash are recorded in the fixture
manifest. No captured bank or application RAM bytes are stored in these files.

`tools/test_current_installer.py` checks all generated installer, transfer,
source-bank, and expected-bank hashes against the Phase 4 differential evidence.
That evidence is itself checked against the unchanged Phase 4 manifest. The
generated transactions must equal these frozen transaction fixtures, apart
from the label. This preserves the established byte and operation checks without
running retired preparers or depending on old `BUILD` directories. All 51 host
regression groups and 16 linked CPU cases remain in the suite.

These are compatibility oracles. Do not regenerate them to make a changed
implementation pass.
