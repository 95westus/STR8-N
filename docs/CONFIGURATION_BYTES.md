# Bank-3 configuration, discovery policy, and metadata bytes

Applies to STR8-N 1.35 and the matching HIMON/AM03 workbench as of
2026-09-16. This is a reference, not authorization to program flash.
Addresses below are CPU addresses with **Bank 3 selected**. The same CPU
address in another bank is unrelated guest data, not a shared configuration.

## Address map and current values

The SST39SF010A image uses 32 KiB per bank. Bank-3 CPU `$FFF0` is device
offset `$1FFF0`, or offset `$0FF0` in a standalone B3:F 4096-byte image.

| CPU bytes | Purpose | Canonical 1.35 image | Last verified COM4 state |
| --- | --- | --- | --- |
| `$FFB0-$FFBF` | D0 identity and journal | All `$FF` | Board-specific; archive before changes |
| `$FFC0-$FFCF` | D1 identity and journal | All `$FF` | Board-specific; archive before changes |
| `$FFD0-$FFDF` | D2 identity and journal | All `$FF` | Board-specific; archive before changes |
| `$FFE0-$FFEF` | D3 identity and journal | All `$FF` | Board-specific; archive before changes |
| `$FFF0` | Flash WORK sector locator | `$FF`: none | `$FF` |
| `$FFF1` | Protected B3:F backup locator | `$2F`: B2:F | `$2F` |
| `$FFF2` | Scoped AP/FNV bank policy | `$FF`: disabled | `$A6`: B1 and B2 |
| `$FFF3-$FFF9` | Seven unassigned configuration bytes | Each `$FF` | Retain erased; no assigned feature |
| `$FFFA-$FFFB` | NMI vector, little endian | `$F0CF` (`CF F0`) | Firmware-owned |
| `$FFFC-$FFFD` | RESET vector, little endian | `$F000` (`00 F0`) | Firmware-owned |
| `$FFFE-$FFFF` | IRQ/BRK vector, little endian | `$F0E3` (`E3 F0`) | Firmware-owned |

The live `$A6` is deliberately not the release default. A fresh programmer
image does not enable external discovery. See the
[1.35 board record](STR8N_V1_35_BOARD_TEST_2026-09-16.md) for the tested image
identities; a historical readback is not a substitute for a fresh preflight.

## `$FFF2`: exact policy encoding

HIMON decodes this byte as follows, before switching away from Bank 3:

```text
valid     = (policy & $F8) == $A0
allowed   = valid ? (policy & $07) : $00
effective = requested_banks & allowed

bits 7..3 = 10100  signature; all five bits must match
bit 2     = Bank 2 eligible
bit 1     = Bank 1 eligible
bit 0     = Bank 0 eligible
```

| Value | Eligible external banks | Meaning |
| --- | --- | --- |
| `$A0` | None | Valid encoding, but no external bank search |
| `$A1` | B0 | B0 only |
| `$A2` | B1 | B1 only |
| `$A3` | B0, B1 | B2 excluded |
| `$A4` | B2 | B2 only |
| `$A5` | B0, B2 | B1 excluded |
| `$A6` | B1, B2 | Current workbench policy; B0 excluded |
| `$A7` | B0, B1, B2 | All external banks eligible |
| `$FF` | None | Erased/default; disabled, **not** all banks |
| Every other value | None | Invalid signature; fail closed |

For example, `$06` is not a shorthand for `$A6`, and `$A8` does not enable
RAM or Bank 3. `$00`, `$06`, `$A8`, `$FE`, and `$FF` all decode to zero.
Request masks can narrow policy, never expand it: requesting B0 under `$A6`
produces an empty effective mask. Bank 3's resident catalog is separate;
there is no Bank-3 bit in this policy. This byte is not an FNV hash or checksum.

### What it controls, and what it does not

- Resident executable FNV lookup happens first. A resident hit wins without
  staging external media. Automatic external dispatch is attempted only on
  a resident miss and only when the decoded bank mask is nonzero.
- HIMON's manager bootstrap searches allowed banks in order B2, B1, B0,
  sectors 8 through F. It skips both configured role sectors and requires a
  fully parsed compatible manager. Bootstrap uses the **allowed** mask;
  target named discovery uses the **requested AND allowed** mask.
- Named AP discovery scans selected 4 KiB carrier sectors, not arbitrary
  executable bytes. It validates the AP v2 envelope/seal, executable entry,
  FNV identity and exact canonical name. More than one matching provider is
  a duplicate error, not a first-match selection. A unique match is revalidated
  before load/link/entry; role sectors remain excluded even in an allowed bank.
- In AM03 automatic dispatch, the existing RAM provider window `$3000-$3FFF`
  is also considered. RAM enable/window selection is transient state, not
  extra bits in `$FFF2`. RAM and bank matches participate in uniqueness.
  However, `$A0`/`$FF`/invalid policy prevents the automatic fallback and its
  manager bootstrap, so these values do not create a RAM-only automatic mode.
- This is discovery eligibility, not a security boundary, flash write permit,
  STR8 `Jn` enrollment, or general ban on explicit bank access. Raw-address
  inspection/loading and explicit direct-RAM AP services have their own
  validation rules. Do not assume policy disables every access to a bank.

### Prerequisites before enabling a bank

1. Install a compatible HIMON and manager pair. The current HIMON expects
   **AM03 at runtime `$6C00`**, not the older AM02 `$7000` overlay. A policy
   byte cannot repair a mixed pair or install missing manager code.
2. Allow the manager's carrier bank as well as the desired provider bank.
   The verified manager is B2:8: `$A4-$A7` include it; `$A1-$A3` do not.
   In particular, B1-only `$A2` cannot bootstrap this B2 manager even though
   a valid application may exist in B1. No manager means manager-dependent
   discovery fails; explicit resident/direct-RAM recovery remains separate.
3. Inventory each allowed bank. B0 may contain an opaque factory/guest image;
   do not opt it into AP discovery merely because it exists or is bootable.
   Ensure candidate carriers are valid, unambiguous, and outside role sectors.
   Directory adoption and AP-provider validity are different contracts.
4. Respect foreground RAM ownership: Bank 3 selected at entry, decimal mode
   clear, no nested manager/search operation. AM03 uses `$6C00-$7BFF`,
   `$0A00-$19FF` staging, `$1A00` command shadow, `$1B00-$1B1F` transition
   state, and private `$7D40-$7D5F` search state. It invalidates ASM resume
   before overlay use. RAM providers must remain stable and fit wholly in
   `$3000-$3FFF`; they are not staging buffers. Child execution retires
   discovery state and does not resume a persistent manager menu.
5. Check image identity, role configuration and recovery resources before
   programming. Then prove disabled/enabled behavior, actual child execution,
   duplicates/refusals as applicable, physical-reset persistence, and exact
   flash isolation. Successful AM03 handoff is silent: no `GO` banner is required.

SPI SRAM is not installed in the verified system. Neither this byte nor a
reserved byte enables SPI storage, a new WORK allocation, or general HREC
execution. The separate HREC metadata proof is not automatic executable
provider support. NMI safety during foreign-bank access is a separate gate.

## `$FFF0` and `$FFF1`: role locators and prerequisites

A locator packs `(bank << 4) | sector`: valid bank numbers are 0-2 and CPU
sectors are 8-F. Thus `$18` means B1:$8000-$8FFF, `$2F` means
B2:$F000-$FFFF. `$FF` means unassigned; it does not mean B3:F. Other encodings
are not supported role assignments. Do not assume malformed locators receive
the policy byte's fail-closed treatment: several consumers compare them literally.

`$FFF0` reserves a flash WORK sector when assigned. Current `$FF` leaves
**no flash WORK**; it does not allocate replacement RAM or SPI SRAM. B1:E is
ordinary media under the current configuration, not automatically scratch.
Any future assignment requires an agreed owner, an inventoried safe sector,
compatible tools and a separately qualified allocation/recovery contract.

`$FFF1=$2F` reserves B2:F as a **raw, exact B3:F recovery copy**. It is not an
AP carrier or a standalone B2 operating system. Its reset vector belongs to
the copied top image and is not permission to boot B2. The role byte alone
does not prove the backup exists or is valid; verify the full 4096 bytes and
record which live-top generation it represents.

APMAN and role-aware maintenance tools exclude the two role sectors from
ordinary discovery/allocation or destructive operations. These are software
guards, not hardware write protection. The current ordinary top updater
explicitly uses B2:F; changing `$FFF1` does **not** relocate that updater's
backup destination. Do not move roles by editing a byte alone: first align
all producers/consumers, preserve old and new backups off-board, verify the
new copy, and qualify recovery before freeing the old sector. Do not assign
WORK and backup to the same location.

## `$FFF3-$FFF9` and interrupt vectors

Keep all seven reserved configuration bytes `$FF`. No supported bit assignments,
enable flags, version extensions or prerequisites exist for them yet. Assigning
one requires a new coordinated firmware/public-contract change, updated image
builders/consumers, migration rules and tests; erased space is not free scratch.

Vectors are firmware-owned little-endian addresses, not user configuration.
Their handlers must exist in the same compatible top image. Do not copy the
1.35 vector numbers into a different build or patch a single vector to bypass
an invalid directory. Preserve them in metadata-only updates and verify them
with the entire top sector. An erased or mismatched reset vector can prevent boot.

## Adjacent directory bytes and their prerequisites

The four 16-byte rows start at `$FFB0 + bank * $10`. They are distinct from
the role/policy pocket; `$FFDE`, for example, is D2 journal data, not a flag.

| Row offset | Meaning | Requirements |
| --- | --- | --- |
| `+0` | Type | Use the identity writer's accepted value; `$FF` alone does not prove an empty row |
| `+1..+3` | Reserved | Keep each `$FF` |
| `+4..+8` | Five-character description | Writer accepts uppercase letters, digits, hyphen, underscore, period |
| `+9` | Identity seal | `$FE` for a sealed identity; not a payload checksum |
| `+10..+11` | Entry, little endian | `$FFFF` for B0-B2; validated explicit entry for D3 |
| `+12..+15` | 16 START/COMPLETE bit pairs | Monotonic journal; never hand-edit to claim a failed install succeeded |

An empty row is all 16 bytes `$FF`. Each journal pair progresses unused `11`
to started `10` to complete `00`; `01` is illegal. Pairs are consumed from
the low bits of the first journal byte onward. A fresh successful transaction
therefore gives `FC FF FF FF`, then `F0 FF FF FF`, then `C0 FF FF FF`.
Changing journal bytes during an install is expected, but must match the
actual transaction sequence. An open START blocks normal B0-B2 launch and
requires the installer's recovery path; exhausted journal capacity requires
guarded maintenance before further transactions. Clearing more bits cannot
restore unused pairs or restore an erased row.

`D` adoption requires an empty destination row and an already present payload
with a usable RESET vector; D3 additionally requires the resident `SR 02 03`
signature and validated entry. Adoption publishes metadata, not payload code.
`N` is the guarded description-only rewrite; it is not a general identity
editor. Reclaiming D0-D2 requires proving the corresponding payload bank is
erased. D3 journal compaction has its own full-journal check. See
[directory and transaction journal](TECHNICAL_GUIDE.md#directory-and-transaction-journal).

## Safe changes and persistence across updates

All these bytes share the erase-sensitive B3:F boot sector with resident
code and vectors. Do not use a monitor memory poke, a one-byte S19, or an
unguarded flash write. Flash programming clears bits; restoring a bit from
0 to 1 requires sector erase. Even `$FF -> $A6` is not permission to bypass
the supported guarded transaction.

| Operation | Directory | Roles/policy/reserved bytes | Backup prerequisite |
| --- | --- | --- | --- |
| Ordinary top update | Preserves live `$FFB0-$FFEF` | Installs candidate `$FFF0-$FFF9`; canonical candidate resets policy to `$FF` | Verified immediate old top at B2:F; authorize overwriting its previous generation |
| Directory refresh | Replaces directory with erased candidate | Installs candidate configuration, including default disabled policy | Same guarded B2:F backup; loses enrollment/journal state deliberately |
| STR8-iN/65 Bank Maintenance `F` | Preserves all directory bytes | Changes only `$FFF2` in a freshly staged live top | One fully erased, non-role scratch sector in B0-B2 |
| Frozen task-specific policy updater | Preserves live directory | Uses its embedded candidate and expected-old-byte guards | Exact matching firmware/checkpoint plus its documented backup generation |

The `F` editor exists in the STR8-iN/65 maintenance variant, not every bank
menu. It accepts only `FF` or `A0`-`A7`; empty input selects **A6**, not cancel.
It prints `FLAG UNCHANGED` and does no write when the requested byte already
matches. Otherwise it searches B0, B1, B2 in order, sectors 8-F, for a wholly
erased sector excluding both configured roles, displays that scratch location,
and requires exact `FLAGS xx` confirmation. Verify that the displayed sector
is also operationally available: erased bytes alone do not establish ownership.

After confirmation it snapshots live B3:F, writes/verifies the scratch backup,
changes staged `$FFF2`, rewrites/verifies B3:F, then erases/verifies scratch.
The temporary copy is not retained as a permanent backup. `F` neither changes
role locators nor verifies that the installed HIMON/manager can use the policy.
It need not consume or reset directory journal pairs.

Before any protected-sector update: save fresh full-bank/top readbacks off-board,
check artifact identity and source/target roles, ensure stable power and exclusive
serial ownership, and have a compatible recovery procedure. Do not press RESET,
NMI or remove power during erase/program/verification. Ordinary top-update
RAM `R` retry / `O` restore prompts are specific to that updater; do not assume
the `F` editor offers the same recovery UI. A RAM backup/retry mechanism is
not a power-loss recovery guarantee. Stop on errors and retain the backup.

Afterward verify exact B3:F bytes, scratch/backup state and all unaffected
sectors, then physical reset and consumer behavior. Recheck `$FFF2` after
every top update: preserving the directory does **not** preserve policy.
Do not reuse older AM02-era frozen policy images over a different STR8 build.

## Implementation references

STR8-N: `src/str8-config-eq.inc`, `src/str8-directory-eq.inc`,
`tools/top-update/str8n-v1.23-top-update-2000.asm`,
`tools/bank-maint/str8n-v1.28-str8-in65-bank-maint-flags.inc`, and the shared
`tools/bank-maint/str8n-v1.23-bank-maint-2000.asm`.

Companion R-YORS: `SRC/AP/fnv-scope-policy.inc`, `SRC/AP/ap-manager.inc`,
`SRC/AP/fnv-scope-find.inc`, `SRC/HIMON/himon-fnv-fallback.inc`,
`SRC/APPS/apman-7000.asm`, and `DOC/GUIDES/AP/HIMON_AP_SCOPED_RAM_CONTRACT.md`.
The host policy test covers all 65,536 policy/request-byte combinations.
