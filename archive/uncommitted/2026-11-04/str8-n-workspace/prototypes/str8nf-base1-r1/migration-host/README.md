# N/F migration hosts — 0.3.0

`nf_migrate.py` prepares and inspects an exact private migration plan. It has
**no serial import, port-opening command, device execution, reset or flash
operation**. The reviewed WDC and programmer-F paths passed on
2512/65C02/FT245; see [release status](../docs/RELEASE_STATUS.md). Migration
through the extracted rc1 existing-SNBT upgrade also passed on 2609. The
final ZIP has no additional live trial; packaged WDC/programmer-F provisioning
remains NOT RUN. A plan's `installation_permitted` and
`execution_qualified` fields stay false. The separate `nf_migrate_live.py`
implements explicit WDC capture/execution; it refuses to open a port without
`--allow-unqualified` for the broader platform/layout qualification limits.
The ZIP includes the Python terminal; disconnect it before a CLI owns its port.

The public tool ships project code only. The operator's captured WDC firmware,
RAM, wear-history records and per-run plans stay private. Nothing is copied to
B0 automatically; B0/B1/B2 and B3:8/9/A/B/E remain available to their owner.

## Required private capture

Supply separate, agreeing read files. A copied filename or hardlink does not
establish an independent device read; the capture procedure must obtain the
two observations independently. This preparation tool checks their bytes but
cannot attest that live acquisition occurred.

```text
capture.json
b0.bin                 b0-repeat.bin
b1.bin                 b1-repeat.bin
b2.bin                 b2-repeat.bin
b3.bin                 b3-repeat.bin
owner-ram.bin          owner-ram-repeat.bin
owner-zp.bin           owner-zp-repeat.bin
```

Each bank is exactly 32768 bytes, CPU addresses 8000-FFFF. `owner-ram` is
exactly 25856 bytes, CPU addresses 0200-66FF. `owner-zp` is exactly 224 bytes,
addresses 0000-00DF; the migrator's E0-FF runtime scratch and stack are separate.
The RAM copies are escrow, not proof of subsequent restoration.

Example `capture.json` fields:

```json
{
  "schema": 1,
  "cpu": "65c02",
  "board_model": "W65C02SXB",
  "source_kind": "wdcmonv2",
  "method": "independent-double-read",
  "wdc_info_hex": "<the actual 12-byte WDC debugger identity, as hex>"
}
```

For the 65C816, declare `cpu` as `65c816` and `board_model` as `W65C816SXB`.
`nf-recovery` is the separate preparation route for a programmer-installed,
byte-identical F image; it does not require a WDC debugger identity. CPU/model
fields are saved declarations. The live executor verifies the real
debugger identity, current source bytes and loaded RAM before execution.

## Prepare and inspect

From this directory, using newly created private output paths:

```text
python nf_migrate.py prepare --capture PRIVATE-CAPTURE --cpu 65c02 --source-kind wdcmonv2 --f-image ../firmware/payload/STR8N-F-BOOT-4096.bin --provision-cd --out PRIVATE-PLAN
python nf_migrate.py inspect --plan PRIVATE-PLAN
```

Only the frozen 4096-byte STR8N-F 0.3.0 BASE1/PR05 F is admitted:
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
The command writes/fsyncs and rereads the private members, an `erase-intent.json`
receipt, exact transfer/final sector files, complete expected banks and the plan.
An automatically created `.gitignore` excludes all contents of the private plan.
The receipt records planned attempts; it does not update authoritative history.

With a built RAM engine template, add `--template PATH/engine-template.bin`.
This renders a private 8192-byte RAM image and S19; it does not execute them.
The actual template filename is supplied by its build manifest. Template bytes
and their hash are retained in the plan for inspection; serialization does not
establish that an arbitrary template is an approved engine.

Typical preparation messages:

```text
CAPTURE: four complete banks and owner RAM/ZP; repeated bytes agree
F TARGET: 4096 bytes; PR05 SHA-256 ...
JOURNAL: occupied-unrecognized
KEEP: B0/B1/B2 and B3:8/9/A/B/E; no WDC backup copied into user banks
PLAN 1/3: erase/program/verify B3:F000, 4096 bytes
PLAN 2/3: erase/program/verify B3:D000, 4096 bytes; journal commit byte written last
PLAN 3/3: erase/program/verify B3:C000, 4096 bytes; journal commit byte written last
RAM: escrowed; restoration has NOT been performed by this preparation tool
STOP: no device opened; no flash written; execution/hardware qualification pending
```

## Admission and journal policy

- Blank or unrecognized occupied C/D require the explicit `--provision-cd`
  choice and the complete original capture. The latter is a declared conversion
  source, not an automatic repair of a recognized damaged journal.
- Damaged/torn SNBT, legacy WC records, mixed known/unknown pages, conflicting
  committed snapshots or regressing counters are refused. A separate inspected
  history import/repair is needed.
- Clean existing SNBT plus identical F is a no-op: retain all settings/history.
  Reinitialization is refused. This factory executor also refuses existing-SNBT
  F upgrades; it has no onboard append-before-erase reservation operation.
  The separate NFU1 upgrade implements that reservation for the
  known b15 F and an available erased append page; it is not this factory path.
  See [existing-journal F upgrade](../docs/JOURNAL_F_UPGRADE.md). Its known-b15
  2512 case passed, and its prebuilt engine is included in 0.3.0-rc1.
- New provisioning installs F first if needed, then D and C. The engine erases
  each listed destination, including a blank journal sector. Each attempt is
  reserved in the private host receipt. D's committed snapshot reserves C's
  later attempt before C is erased. Commit is byte FF of the first page, written
  zero last. Each resulting journal sector is otherwise erased.
- A new journal starts with default `S`, no enabled banks and entries 8000.
  Prior lifetime remains unknown for every sector; zero denotes no imported or
  observed attempt, not unused flash. Fresh migration reserves F/D/C as one
  each; programmer-installed identical F provisions only D/C and does not
  manufacture a recorded F erase.
- An optional `--history HISTORY.json` imports owner-supplied lower bounds for
  first provisioning. It must declare schema 1, `semantics` equal to
  `tracked-lower-bounds`, the exact current four `source_sha256` values, 32
  `counts`, `sequence`, `unknown_mask` equal to `ffffffff`, and a nonempty
  `provenance` description. Its assertions remain owner supplied; the tool does
  not independently certify prior erases.

## Engine serialization contract

The RAM image occupies 2000-3FFF. WDC 65C02 entry is 2000; WDC 65C816 entry is
2010 for its native/emulation shim. An F-recovery loader enters at 2000 in
emulation mode. Stage buffer is 4000-4FFF. NFM1 parameters at 3000 contain the
initial four complete-bank FNV values and up to three F/D/C operations. Each row
binds current B3, the uncommitted 4096-byte transfer and final B3. FNV32 detects
accidental corruption/stale preimages; it is not authentication. The self-check
at 3FFC covers 2000-3FFB. This host tool does not claim RAM restoration or a
physical-reset/recovery pass.

## Source-development checks

```text
python -m unittest -v test_nf_migrate
```

These are for the source ZIP when changing the host, not routine packaging.
They check admission, counter preservation/exhaustion, commit serialization,
scope and private-file tamper detection. They do not emulate a CPU, NOR device
or serial link and do not qualify live flashing.


## Explicit live WDC path

`nf_migrate_live.py migrate` supplies the concrete WDC USB path. The
[2512 WDC acceptance](../docs/2512_WDC_MIGRATION_ACCEPTANCE.md) passed it on real
hardware with independent preservation checks. Other CPUs/adapters/layouts and
interruption remain unqualified. Packaging/check commands never run migration.

The live command requires an explicit port/model, the built read-only archiver
and its manifest, the frozen RAM engine template, the exact F BIN, the matching
BASE1 READBACK image/component manifest, and new private capture/plan/run folders.
It does not enumerate or select an owner's board automatically.

Example arguments from this directory, after reviewing the selected board's scope:

```powershell
$nfArgs = @(
  'migrate', '--port', 'COMx', '--cpu', '65c02',
  '--archiver', '../migrator/payload/archive.bin',
  '--archiver-manifest', '../migrator/payload/archive-manifest.json',
  '--engine-template', '../migrator/payload/template.bin',
  '--f-image', '../firmware/payload/STR8N-F-BOOT-4096.bin',
  '--readback', '../firmware/payload/STR8N-F-READBACK-RAM.bin',
  '--readback-manifest', '../firmware/minimal-manifest.json',
  '--provision-cd', '--capture-out', 'PRIVATE-CAPTURE',
  '--plan-out', 'PRIVATE-PLAN', '--out', 'PRIVATE-RUN',
  '--allow-unqualified'
)
python nf_migrate_live.py @nfArgs
```

Replace `COMx` with the explicitly assigned port, released by its terminal.
For the 65C816 use `65c816`; the 2010 WDC entry shim handles native/emulation
entry. No terminal application is closed by this tool.

The command performs these phases:

1. Observe the real WDC debugger identity (SXB2/SXB6), save B3 twice, and save
   original owner RAM/ZP twice **before** the first helper upload.
2. Upload/read back the read-only archiver. It reads all four banks twice from
   RAM, streaming 32768 bytes plus FNV per bank. B3 must also match the separate
   WDC reads. It restores B3 selection and halts without a ROM-return assumption.
3. Request physical RESET back to WDC and intercept the debugger. Recheck its
   identity and complete B3 twice. Vendor startup/SPI side effects remain a
   separate unqualified boundary; the helper itself has no flash or EDU writes.
4. Prepare/fsync exact F/D/C transfers and the host erase-intent receipt.
   Load/read back the entire RAM engine, then execute its read-only preflight.
   The engine freshly checks **all four bank FNV guards** before its Y prompt.
   This is device admission, not an independent host SHA read of B0-B2 after
   the intervening RESET.
5. Save a durable phase before the one transaction confirmation. Send each
   exact 4096-byte transfer only after its destination's ready marker, paced in
   64-byte chunks. Record device erase/program/commit/readback results. There
   is no flash retry or automatic reset.
6. Request physical RESET and verify the N/F recovery face and `REC>`.
7. Load the new **BASE1** RAM service, independently read/save all four complete
   flash banks, and compare SHA-256 to the plan. Restore original pre-archiver
   RAM 0200-66FF and ZP 00-DF, read both back, and return to `REC>`. Only that
   completed callback sets restoration/preservation flags true. The old
   25344-byte readback protocol is not used.

Original owner escrow is never replaced by helper working RAM. Fresh working
RAM observed before migration is archived separately in the run. Per-phase
JSON and serial traces are private. A failure stops with no automatic replay;
retain power, original backups and the phase log for inspection.

The separate `capture` command stops back at WDC with original RAM **still
escrowed and unrestored**. Separate `execute` accepts a rendered private WDC
plan and requires matching READBACK. `migrate` combines capture, preparation,
execution and the completion callback. Existing-SNBT F upgrades and generic
live F-recovery provisioning remain outside this WDC CLI. The latter is now
implemented separately in `nf_provision_live.py`; see
[live C/D provisioning](../docs/LIVE_CD_PROVISIONING.md). It requires original
pre-helper RAM escrow and defaults to capture/plan/verify/restore without flash
writes. Its [2512 acceptance](../docs/2512_PROGRAMMER_F_CD_ACCEPTANCE.md) passed,
and the command, engine and wrapper dependency are included under their tested
paths. The next [ZIP test](../docs/RELEASE_WORKFLOW.md) must use only extracted
files and retain the archive SHA-256 in its result.

`recovery_callback(...)` and `execute_wdc(...)` also accept the already owned
link and retain its private serial trace. No imported module opens a port.

Additional narrow host protocol checks:

```text
python -m unittest -v test_nf_migrate_live
```

These use a fake transport to check ordering, admission and completion flags.
They execute no target instructions and run no NOR or USB timing model.
