# Current installer

`python -B tools/install_current.py` is the current development installer entry
point. Board identities and candidate hashes live in `profiles.json`; capture,
planning, admission, execution and RAM recovery each have one implementation.
Sealed kits carry this same library and use `python -B KIT/install.py`.

This phase is verified offline. It does not add hardware qualification or
authorize an operation on either board. Published r9/stock/beta4 upgrade packages
and their instructions retain their existing frozen workflows.

## Profiles and ownership

| Profile | Identity or purpose |
| --- | --- |
| Board `2604` | USB `A10MQGVHA`, 65C02 |
| Board `2609` | USB `A10MPQXCA`, 65C816 in emulation mode |
| `release-r9` | Phase 1 released generation-50 reference |
| `source-store` | Phase 1 named-source candidate |
| `maint-source` | Phase 1 MAINT/source candidate |
| `console-edit` | Phase 1 console editing candidate |
| `asm-dev` | Phase 1–3 current source, EQU/listings/symbols/diagnostics |
| `asm-dev-cleanup-2604` | Explicit named-demo and UCHESS erase policy |

Ordinary profiles own B1:9000/A000/E000/F000, B2:8000–FFFF and
B3:8000/A000/B000/E000/F000. They preserve all B0, nonowned application sectors,
the complete B3:9000 sector including TZ history, and current settings. Only
changed owned sectors and wear-journal reservations are written. Banner and
generation alone never identify a source: every owned sector, the immutable
RTC code prefix, and a clean generation-50 journal must match.

Cleanup requires a separate kit, board 2604, and a validated capture proving
the exact E311/E312/CS1/CS2 source records, empty remaining B0, and the canonical
UCHESS sector. It erases those four B0 sectors and UCHESS. No ordinary profile
does this. Cleanup has no automatic reverse/restore action.

## Offline commands

Create a kit in a new directory from at least two registered full-system
images, including its target. The current image can come directly from
`tools/build_current.py`; historical installer directories, hardware receipts,
private backups and the old preparation chain are not package inputs.

```powershell
python -B tools/install_current.py profiles
python -B tools/build_current.py --out BUILD/current-install
python -m zipfile -e tests/fixtures/installer-profiles.zip BUILD/installer-profiles
python -B tools/install_current.py package --candidate asm-dev --image asm-dev=BUILD/current-install/firmware.bin --image console-edit=BUILD/installer-profiles/console-edit.bin --out BUILD/current-kit
python -B tools/install_current.py plan --kit BUILD/current-kit --capture PRIVATE/before --out PRIVATE/plan
python -B tools/install_current.py verify --kit BUILD/current-kit --plan PRIVATE/plan
python -B tools/install_current.py qualify --kit BUILD/current-kit --plan PRIVATE/plan --deps-02 BUILD/v1.30/local/test-deps --deps-816 BUILD/test-deps-816 --out PRIVATE/proof.json
```

Add `--image PROFILE=FILE` for each additional registered source/restore target.
Images must match their Phase 1 hash. `--board 2604` or `--board 2609` optionally
restricts a kit. Cleanup additionally requires `--board 2604
--cleanup-capture PRIVATE/before` and the cleanup candidate name.
The four historical generic images now come from the committed compatibility
fixture ZIP; no old builder or `BUILD/rc1-*` firmware output is required.
Packaging verifies their registered hashes before creating a kit.

An already-current plan has no installer or transfers. It still validates its
complete repeated capture and fresh state; execution performs no RAM load,
flash write or RESET. Its qualification receipt explicitly reports no CPU
execution. Ordinary restore uses `restore --kit KIT --original-plan OLD_PLAN
--capture FRESH_CAPTURE --out NEW_PLAN`. It restores the previous registered
firmware profile while preserving newer owner data/settings and reserving
additional wear; it never replays old journals or a whole-bank backup.

## Identity, escrow and recovery

Explicit `preflight`, `execute` and `recover` operations are the only commands
that can import the serial adapter. They require board, kit, run directory,
operation marker, authorization file and shared coordination directory.
`--coordination` is required explicitly so a portable kit cannot silently create
a different lease location from existing board workers.
Execution additionally requires a verified plan and a matching offline proof.
This phase has not invoked any of those operations against hardware.

Authorization requires `owner_authorized: true`, the exact `action` (`capture`,
`execute` or `recover`), `board`, `usb_serial`, `manifest_sha256`, and for
execution/recovery `plan_sha256`. Other-board and RTC-campaign authorization
must be false. Markers must name the same board and have both campaign owners
stopped with no active workers or pending operation. Recovery instead requires
the exact pending plan/run and stopped workers. The marker is reread under the
existing exclusive serial lease before unique USB discovery. Synthetic
captures are refused before entering the live adapter.

Preflight requires idle B3, the correct board/CPU, both valid generation-50
monitor slots and an inactive debugger. It records discovery, active monitor
and preferences, independently reads all four flash banks twice and the full
available application RAM twice, and creates a checked restore S19. Execution
rechecks all source banks, RAM and RAM limit before borrowing RAM. The unchanged
RAM installer loader performs host readback; the transaction performs its
device hash checks, durable wear reservation and verified transfers.

After the transaction, physical RESET remains required. The host verifies the
full four-bank result, firmware identity, settings, active monitor and TZ
sector, then restores the original application RAM with loader readback and
two further full RAM rereads. An interruption keeps RAM/reset flags and escrow;
unknown availability never triggers an attempted RAM restoration. Failures are
reported as inspection required. Recovery accepts only exact known transaction
states and restores RAM only after identity checks. A partial flash state stays
blocked for inspection even after RAM recovery; there is no blind reflash.

Captures, plans, logs and receipts use private ignored directories. Kits contain
generic reference images, profiles and code; cleanup policy includes only the
named-sector hashes. No backup is distributed. Original board captures and
markers are never package outputs.

## Verification and historical references

```powershell
python -B tools/test_current_installer.py --out tmp/installer-check --deps-02 BUILD/v1.30/local/test-deps --deps-816 BUILD/test-deps-816
```

The suite uses synthetic captures and an in-memory monitor, blocks serial
imports, compares generated device artifacts against frozen Phase 4 historical
generic/cleanup hashes and transactions, and executes the linked installer on 65C02 and
65C816 emulation-mode models. It covers both boards, EDU/non-EDU RAM limits,
MON A/B, all registered sources, restore, no-write, interruption recovery,
changed inputs and failed readbacks. CPU faults cover stale source and corrupt
transfers. Later FNV loops, flash busy timing and transport pacing are
accelerated; electrical power-loss behavior is not newly qualified.

| Historical scripts | Shared current implementation |
| --- | --- |
| `prepare_rc1_*_installer.py`, `prepare_rc1_asm_dev_cleanup.py` | `package.py` + board/candidate profiles |
| `source-store/installer_plan.py`, kit-local planner copies | `capture.py`, `plan.py` |
| `preflight_rc1_*` | `workflow.preflight` |
| `admit_rc1_*`, `rc1_asm_dev_cpu_model.py` | `model.qualify` |
| `flash_rc1_*` and repeated RAM restoration helpers | `workflow.execute`, `workflow.recover_ram` |

Dated scripts are now in the [verified history archive](../../archive/README.md).
Sealed release kits remain immutable reproduction references, including the
previously sealed stale asm-dev kit identified in Phase 1. New development uses
this entry point. Regression fixtures preserve all four registered source image
hashes; the current target builds fresh. Tests need no historical installer,
private capture or old firmware output directory.

`provenance.json` records imported engine/template/model origins and exact
hashes. Engine adaptation is limited to package imports and explicit checked
owner erase rows; its generated flashing bytes, operation order and wear
reservations are compared directly. The portable kit needs only Python for
packaging/planning/verification, explicit model dependencies for qualification,
and pyserial plus Windows serial coordination for a future authorized live run.
