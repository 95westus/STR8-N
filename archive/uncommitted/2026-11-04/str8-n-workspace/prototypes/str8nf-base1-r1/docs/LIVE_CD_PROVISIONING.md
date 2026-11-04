# Live C/D provisioning with programmer-installed BASE1 F

Implemented in source: `migration-host/nf_provision_live.py`. This is the
separate F-recovery route; it never uses the WDC debugger or programs F.
It reuses the existing NFM1 engine and generates only its per-run plan and
raw-L relocation wrapper. No assembly or change to frozen F is needed.

Status: [2512 hardware acceptance](2512_PROGRAMMER_F_CD_ACCEPTANCE.md)
passed the reviewed existing-journal no-op and occupied non-SNBT first-journal
paths on 65C02/FT245, with source-bound history import and independent owner
preservation. The [C/D scope](2512_PROGRAMMER_F_CD_SCOPE_REVIEW.md) used four
erases, zero F writes and no power cuts. Other layouts/platforms and interrupted
provisioning remain unqualified; `--allow-unqualified` remains explicit.
No CPU or flash model ran. The 0.3.0-rc1 operator ZIP includes the command,
matching engines and `migrator/build.py` for its pure wrapper generator under
their tested paths. No assembler is needed. Do not copy this file alone into
an old kit. Live migration from the new extracted ZIP remains pending.

## Required original RAM escrow

Recovery L overwrites RAM before the new readback service can inspect it.
Consequently, this path requires an original owner escrow captured before
any RAM helper or programmer migration activity that borrowed that RAM. It
does not silently declare RAM disposable, treat helper bytes as owner data,
or attempt to reconstruct an overwritten prefix.

Supply a private directory with these independently captured file pairs:

| Files | Exact extent and bytes each |
| --- | --- |
| owner-ram.bin, owner-ram-repeat.bin | 0200-66FF, 25856 bytes |
| owner-zp.bin, owner-zp-repeat.bin | 0000-00DF, 224 bytes |

Each pair must be separate files with identical bytes. Include `escrow.json`:

```json
{
  "schema": 1,
  "cpu": "65c02",
  "board_model": "W65C02SXB",
  "usb_serial": "YOUR-EXACT-USB-SERIAL",
  "original_before_helpers": true,
  "method": "independent-double-read",
  "owner_RAM_range": "0200-66FF",
  "owner_ZP_range": "0000-00DF",
  "files": {
    "owner-ram.bin": {"bytes": 25856, "sha256": "SHA256-OF-FIRST-RAM-READ"},
    "owner-ram-repeat.bin": {"bytes": 25856, "sha256": "SHA256-OF-SECOND-RAM-READ"},
    "owner-zp.bin": {"bytes": 224, "sha256": "SHA256-OF-FIRST-ZP-READ"},
    "owner-zp-repeat.bin": {"bytes": 224, "sha256": "SHA256-OF-SECOND-ZP-READ"}
  }
}
```

Use `65c816` / `W65C816SXB` for that CPU. These declarations must describe
actual independent original captures; duplicating a post-helper file does
not make an original escrow. The transport verifies file sizes, hashes,
separate repeated files and USB/CPU declarations. It cannot independently
authenticate when the owner captured them. Receipts state that limitation:
restoration is to the supplied original escrow, not a fresh pre-upload read.
Without that escrow, the command refuses before opening a port.

## Default: live capture, plan and restore, no flash writes

Install the existing pyserial dependency. From the complete source root:

```text
python migration-host/nf_provision_live.py --port COMx --usb-serial YOUR-EXACT-USB-SERIAL --cpu 65c02 --owner-escrow PRIVATE-ORIGINAL --out PRIVATE-PREVIEW --provision-cd --allow-unqualified
```

`--provision-cd` is an explicit first-journal conversion declaration, not an
execution flag. With no `--execute`, this command makes no flash changes.
For existing valid SNBT, omit `--provision-cd` and `--history`: it will retain
the complete history/settings byte-for-byte and report a no-op.

1. Validate all inputs before opening the explicitly selected USB port. DTR
   and RTS are requested off. No auto-reset or WDC sync/probe is issued.
2. Durably save supplied original escrow before the first helper upload.
   Ask for physical RESET; observe the exact BASE1 version/generation/profile
   and chooser, select S, then observe recovery. Select temporary USB-only C1.
3. Load matching BASE1 READBACK through L. Read B3 first and verify the actual
   frozen F bytes. Read all four complete banks twice, with CRCs and independent
   equality checks; durably save the capture. CPU is operator/escrow declared;
   the F startup text does not independently identify the CPU family.
4. Derive and inspect a fresh private `nf-recovery` plan. Permit only D then C;
   an F operation or opaque-image destination is rejected. Existing recognized
   history never becomes a factory plan. Default new policy is S/recovery,
   disabled banks, entries 8000; prior lifetime stays unknown.
5. Independently compare all four flash banks to their source hashes, restore
   supplied original RAM/ZP, read both back byte-for-byte, and return to REC>.
   A passing preview does not mean journals have been installed.

The output contains private captures, original escrow, a plan/expected images,
erase intent and fsynced phase/results. It must not enter Git or a public kit.

## Explicit execution, after separate authorization

The implementation accepts `--execute` in addition to the above arguments,
with a fresh output directory. The reviewed 2512 trial exercised this entry;
other platforms/layouts and interrupted provisioning remain unqualified.

Execution repeats live capture and planning; it never replays an old plan.
The rendered 8192-byte engine is wrapped for L at 0200, relocated backwards
to 2000-3FFF and entered at 2000. Physical F reset already normalizes the
supported CPU to the required mode. Raw L has no readback/CRC guarantee for
the wrapper; NFM1 must report its complete self-image/plan, all four bank
preimages and supported BF/B5 chip check before the host can send Y.

The host durably marks possible mutation **before** Y. It waits for each
destination's ready marker, sends exactly 4096 bytes in paced chunks, and
waits for sector/full-bank verification. The only order is D then C, commit
last. F is neither transferred nor counted as an observed erase. Optional
`--history` uses the existing source-bound lower-bound import policy; new
C/D attempts increment those lower bounds without claiming a known lifetime.
D's committed snapshot reserves the subsequent C attempt before C is erased.

After engine completion the host requests physical RESET, verifies the same
BASE1 face, loads READBACK again, independently checks all four planned final
bank hashes, then restores/verifies the original RAM/ZP and returns to REC>.
Only this completed sequence can report successful provisioning and restoration.

## Refusal and interruption

Valid SNBT plus identical F is always a no-op, even with `--execute`.
Requesting reinitialization/import over valid history is refused. Torn, damaged,
conflicting, regressing or recognized legacy history is refused, never erased
as unknown vendor data. An F mismatch is refused; F upgrades are outside this
path. A recognized valid journal is not rewritten to fill an erased peer sector.

A semantic admission refusal while the verified read-only RAM service is still
idle restores/verifies escrow before stopping. A protocol error, uncertain
active program, or possible flash mutation stops without blind restore, retry
or auto-reset; `owner_RAM_restore_required` remains true when appropriate.
Failed/partial operations are not resumed automatically. Retain power, escrow,
bank captures and phase logs for an inspected recovery procedure. Qualification
of interrupted-migration repair remains a separate release gate.

The 2512 acceptance proves real F reset/loading, C/D commit and wear
accounting, independent flash preservation and original-RAM restoration for
the declared happy path. Power/interruption behavior, other occupied layouts
and other supported platforms retain separate qualification limits.
Board 2205 was excluded from qualification. The candidate now packages these
unchanged files and receipts; see [ZIP acceptance](RELEASE_WORKFLOW.md).
