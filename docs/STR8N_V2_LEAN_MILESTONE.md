# STR8-N v2-alpha7 lean validation

Historical milestone. The [alpha8 pass](STR8N_V2_SCRATCH_MILESTONE.md)
reclaims another 142 bytes without relaxing further checks.

Saves another **77 bytes**, reducing the complete monitor from **3676 to
3599 bytes**. There are **465 bytes free** before $FFE0. Together with
alpha6, the two passes reclaim **283 bytes** from alpha5's 3882-byte image.
No commands were removed or added. Hardware qualification remains pending.

## Deliberately relaxed checks

| Check | New behavior | Protection retained |
| --- | --- | --- |
| L must receive an S1 before S9 | A valid S9-only transfer prints its entry address without changing application RAM. | S19 checksum, syntax, record length and write bounds; L still never executes the entry. |
| Reserved configuration bytes must be zero | Bytes +6 through +13 are ignored semantically. C still writes zeros. | All sixteen bytes remain covered by the two integrity sums; format, enable, bank, target and delay are validated. |
| Every erased byte must read FF before reconstruction | Removed the separate blank-sector sweep. | Bounded erase polling, per-byte transition checks, and a final comparison of the entire sector against the desired image. |

The last change reduces erase diagnostics, not the required final result.
An imperfect erase no longer aborts solely because a residual zero already
matches the desired image. A remaining zero that must become one still
fails before that byte is programmed, and the final full-sector comparison
must pass. A flash failure can leave a partly changed sector, as before;
there is no rollback or journal.

I still requires complete, dense coverage of its requested range before S9
can report success. Empty S1 records remain invalid in both L and I.
Only L's requirement for at least one data record was removed.

## Additional size reductions

M and L share the short gated copy of a fully preflighted edit/record.
Snapshot, transition analysis, and flash mutation share bank/pointer setup.
D and L use the existing address printer. Hex word accumulation uses a
small loop instead of four repeated shift pairs, favoring ROM size over
execution speed.

| Component | Alpha6 | Alpha7 |
| --- | ---: | ---: |
| Resident executable code | 2796 | 2742 |
| Text | 322 | 322 |
| Dispatch tables | 30 | 30 |
| Stored RAM worker | 472 | 449 |
| Stored interrupt entries | 56 | 56 |
| **Total** | **3676** | **3599** |

Retained protections include full-line edit preflight, protected RAM and I/O
bounds, F's one-sector limit, I's resident/recovery top protection, S19
checksums, configuration integrity, flash timeouts, final sector verification,
safe cancellation boundaries, and the RAM-only result/hold after self-edit.
Public entry/vector addresses and application RAM reservations are unchanged.

## Validation and artifacts

Run `make v2-check` for all five host execution suites. Updated tests check
S9-only L with unchanged application RAM, rejection of a bad S9 checksum,
checksummed nonzero reserved configuration bytes, and all 128 single-bit
configuration corruptions. Flash tests cover both rejected erase defects
and a residual zero that already matches the desired image. A corruption
of an earlier byte after programming explicitly exercises the final sector
comparison. Existing timeout, self-edit, NMI gate, cancellation, installer,
bank-handoff and startup-timing checks remain.

Artifacts are in `BUILD/v2-alpha7/`, including
`str8n-v2-alpha7-e000-ffff.s19`, its `.bin`, build statistics and five test
receipts. Configuration format and compact help remain as documented in
[alpha5](STR8N_V2_CONFIG_MILESTONE.md) and [alpha6](STR8N_V2_COMPACT_MILESTONE.md),
subject to the explicit relaxations above.

The E-F image can be installed with v1.35 I into a disposable Bank 0-2,
retaining v1.35 in Bank 3. It replaces both E and F sectors. No physical
board was flashed or tested during this pass. Host validation example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha7/str8n-v2-alpha7-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha7/validated-bank0.s19
```
