# STR8-N v1.34 factory migration board test

Date: 2026-09-15 America/Chicago (serial event timestamps are 2026-09-16 UTC).
Port: COM4, 115200 baud. Board: `SXB2`, HW 3.00, WDCMON 2.00, flash
`BF/B5`, with the EDU expansion attached.

The complete v1.34 factory migration passed: reconstruct the stock Bank-3
baseline with Bank 0 erased, preserve stock B3 into B0, install the external
canonical 4096-byte top, adopt D0, boot B0 through both `J0` and reset selector
`0`, and return to STR8-N by physical RESET. Full before/after readbacks prove
the final contents of all four banks. This extends the earlier
[v1.34 update](STR8N_V1_34_BOARD_TEST_2026-09-15.md) and
[interrupt/worker tests](STR8N_V1_34_FOLLOWUP_BOARD_TEST_2026-09-15.md).

## Recovery image and factory restore

Before any flash mutation, the read-only archive tool exported all four banks.
The extractor checked all S-record checksums, density, reset vectors, and
whole-bank FNV receipts. The four 32768-byte BIN files were combined into an
owner-local 128 KiB recovery image. B3:F also matched the earlier qualified
live v1.34 top exactly.

The checked factory-restore RAM image identified the expected B0 source,
`FNV1A=1249E1F3 RESET=F818`, and supported flash. After the explicit
`RESTORE FACTORY BOARD` transaction it reported:

```text
COPY/VERIFY B0 -> B3 8-E .......
B3:F LAST .
B0 == B3 WHOLE BANK VERIFIED
ERASE/VERIFY FACTORY B0 ........
FACTORY BASELINE VERIFIED: B0 ERASED; B3 STOCK
BOOT STOCK B3
```

This replaced the former HIMON/ASM-F2 contents in B3. Their complete prior
bank image remains in the owner-local backup. B1 and B2 were not destinations.

## Packaged consumer migration

A fresh extraction of the migration ZIP passed its 25-file allowlist,
artifact hashes, and PowerShell/Python protocol checks. The earlier staging
directory had an extra Python `__pycache__` file and was rejected by the
allowlist; the clean extracted ZIP was used for the board run.

The first launch used the default physical-reset/Enter gate. By the time the
host attempted synchronization it received ASCII `$0D` instead of `$CC`.
The bridge stopped before any RAM transfer or migration flash operation.
That attempt and its event log are retained.

The retry used the unchanged packaged Windows PowerShell launcher with
`-PhysicalResetArmSeconds 60`. After the operator pressed RESET, it identified
`SXB2; HW=3.00; WDCMON=2.00`, wrote the RAM loader at `$2000`, and verified
every transferred byte before execution. The board accepted flash `BF/B5`
and stock B3 FNV `1249E1F3`.

The explicit `COPY B3 TO B0` transaction copied all eight sectors and reported
`B0 == ORIGINAL B3 VERIFIED`. Ctrl+U then sent the packaged 4096-byte BIN;
the loader checked its compiled expected FNV before accepting
`INSTALL STR8-N 1.34`. It reported `MIGRATION VERIFIED; STARTING STR8-N`,
followed by `RST S` and `STR8-N 1.34`.

The packaged Bank Maintenance image was loaded through resident `L` using
Ctrl+D. `D`, bank `0`, type `FF`, description `WDCV2`, and explicit
`ADOPT B0` published exactly:

```text
D0 FF WDCV2 FFFF FCFFFFFF
FF FF FF FF 57 44 43 56 32 FE FF FF FC FF FF FF
```

The map retained AP envelopes B1:9 `L06A6` and B2:8 `L0C2A`, plus configured
WORK B1:E and backup B1:F. D1-D3 remained erased, as expected from the clean
canonical migration image.

## Boot and complete readback proof

Both shell `J0` and physical-reset selector `0` reached the retained WDC/EDU
application, including its initialization completion and command menu.
Physical RESET returned through `RST H` and the v1.34 selector to the STR8
shell. The read-only archive tool then exported all four banks again.

All eight before/after bank archives passed the extractor. The independent
host comparison in the local `verify_migration.py` required:

- B0 after migration equals the complete original B0 byte-for-byte.
- B1 and B2 equal their complete pre-restore backups byte-for-byte.
- B3 `$8000-$EFFF` equals that range in the original WDC B0.
- B3 `$F000-$FFFF` equals the canonical v1.34 BIN with only the exact D0
  record above substituted; D1-D3 remain erased.

All comparisons passed. Final B3 FNV is `D199AB81`. HIMON/ASM-F2 were not
reinstalled; the board now has the factory-migration layout.
After readback, the operator pressed physical RESET once more. Capture
recorded `RST H`, `STR8-N 1.34`, selector `S`, and the `STR8-N>` prompt.
The capture then closed COM4, leaving the board at that prompt.

## Artifact identity

| Artifact | SHA-256 |
| --- | --- |
| Tested migration ZIP | `2E1EB81375CB6568AAC7AFF2AE50EC6459B421DB5812B143C30D124F39BDBFB4` |
| Factory-restore S19 | `54374209253B6E86BCA73F3ECB1A473AA8C4566C4C91BD6116324DA1D0C0B23F` |
| Packaged RAM migration S19 | `0958968D8857DB7DF79F766357544ABACB604DF0B129A571128BBA1A46D3F395` |
| Packaged Bank Maintenance S19 | `809B839CF8F8288F8AE51153B78E8C132CF792E090474E9EA2AD0EEB911905DA` |
| Canonical v1.34 top BIN | `9538D97854BA9D5D76143CBA0FEDB3B2E7CE18F977CE89557406E63404026CB7` |
| Pre-restore 128 KiB backup | `C7FF2D4FE003D9E9E2CBE2B2AD6CA310AAC2C1178B59885220127D93B09ABD81` |
| Retained B0, before and after | `2F0000C74ECEEC809A814E31F822702977D7BFED5EE6F3BC4869627864CA59A8` |
| Final full B3 | `2DF0C27DEEB0AD27101C8A75C07B1D6275D11A061C3AB4E94E3FA2B0CF05703C` |
| Final live top, including D0 | `C5017A50BAFB10BA5B4D60A85214F9FAADCD335475EEC1C87DD940A5B73650F3` |

Owner-local evidence is under `BUILD/v1.34/board/`:

- `2026-09-15-migration.jsonl`: append-only serial exchanges for inventory,
  bank exports, factory restore, selector test, and physical-reset returns.
- `factory-migration-20260915.raw.events.txt`: failed first synchronization.
- `factory-migration-20260915-retry.raw` and `.raw.events.txt`: packaged
  migration, D0 adoption, maintenance map, and J0 application startup.
- `pre-migration-backup/` and `post-migration-readback/`: complete BIN/S19
  archives and verified receipts, plus combined 128 KiB images.
- `migration-verification.json` and `verify_migration.py`: byte-exact results
  and the independent host comparison.

Successful consumer raw transcript SHA-256:
`0511CC528E3D68A228E1258BEE80C5B02B9AAA9BC4842D1CC0E0E08397841776`.
Its event-log SHA-256:
`886B2A8FE38ABBCC7999EA5D9BDFBB5771BC9B1179DBDB5A077A29F56643E8EA`.
Final append-only serial JSONL SHA-256:
`C3F6FEC6F88E2CFADBF028B3A98489E9C72B35421A48852A51E87F13BF7E4670`.
Byte-comparison result JSON SHA-256:
`5249B01B96B68ADBA231FEB41DA1E97E1AB8A039E8323BCFF49E237A3CD41786`.
Stock bank bytes and dense archives remain local and are not release payloads.

This run does not add visual LED observations, injected failure/recovery
proof, a power-cycle after migration, or Bank 1/2 guest-boot acceptance.
The default reset/Enter launch attempt failed; the accepted run used the
packaged reset-arm option. Firmware and host-tool code were unchanged.
