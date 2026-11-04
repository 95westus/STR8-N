# b15 EDU/SRAM onboarding for 2609

The **read-only ES1 provider is installed in B3:8 on 2609**. The 6760-byte
`2609-EDU-SRAM-INSTALL-RAM.bin` committed C600 before erasing/programming B3:8.
Independent double reads before, immediately after and after runtime acceptance
verified the exact planned result. B0, B1/B2, B3:9, MON A/B, VX1 E, F and all
old journal rows remain intact. See the
[installation receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step17-EDU-SRAM-install/receipt.md)
and [complete installation console](../output/qualification/2609-b15-onboarding-20261027T212009Z/step17-EDU-SRAM-install/console-log.txt).

Two original 131072-byte SRAM backups, a fresh pre-install read and two complete
post-install reads all match byte for byte, mode 40 throughout, SHA-256
`56cd2490028e7c6b4ee07fb26c87ea75d9d665f10c6406263c0c0f4000116a9e`.
The original [RAM preflight/backup receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step16-EDU-SRAM-preflight-live/receipt.md)
remains available. The installed-provider client passed its startup guards and
its immutable prefix matched an independent MON dump.

2609 is back at REC with F, C/D, MON A/B, VX1 E and ES1 B3:8, default S,
banks disabled, sequence **1021**. B3:8 has one recorded erase, **26 → 27**;
all other counts and the unknown-lifetime mask are retained. No saved setting,
SRAM data/mode, RTC or EEPROM write was requested. The port is closed; stop
before configuration changes. This exact installer is now stale and must not
be replayed. C600 is occupied; regenerate the older CONFIG exercise plan.

The existing full-system EDU/SRAM utilities depend on private services absent
from this b15 checkpoint. Copying their old ROM sector or RAM gateway would
not install a matching service. The ES1 candidate supplies explicit RAM-tool
access without changing F or the MONs. It is separate from VX1 VERSION/CAPS.

## Place in the operator sequence

1. Original WDC backup, F-only install and REC verification.
2. C/D journals with owner wear provenance, then MON A/B and VERSION/CAPS.
3. Admit matching CONFIG, readback/export and read-only MAINT tools. Inspect
   default S, disabled banks, counts, addresses and protected targets.
4. **Optional EDU/SRAM chapter:** RAM-only inspection and retained-array backup;
   separately authorize the provider install, verify it, inspect through the
   installed provider and compare retained contents again.
5. Later, qualify preserving hardware presence/alias tests and port named SRAM
   storage, WORK and the saved EDU ON/OFF lifecycle. Back up before any probe,
   write, format or allocation change. Never initialize an existing array
   automatically. C/D remain the flash journals.
6. Opaque-image installation/readback/launch/restore lesson, language images,
   B1 selector and final acceptance. Peripheral services remain optional.

The read-only MAINT lesson and the first opaque-image lesson do not require
EDU. Optional hardware must not become an implicit prerequisite for F boot.
The proposed full-core installer should offer this module explicitly and keep
B3:8/9 unchanged when it is not selected.

## Prepared files and ownership

The owner-local [ready kit](../output/qualification/2609-b15-onboarding-20261027T212009Z/step15-EDU-SRAM-ready/receipt.md)
binds the final binaries, hashes, archived pre-install source banks and offline
test receipts. It is an exact 2609 plan, not a generic factory distribution;
its source no longer matches the completed board.

| File | Purpose / destination |
|---|---|
| `2609-EDU-SRAM-PREFLIGHT-RAM.bin` | Load at `$0200` through F L; driver and inspection UI entirely in RAM. Works before ROM installation. |
| `2609-EDU-SRAM-INSTALL-RAM.bin` | Load at `$0200`; guarded installer for one B3:8 sector and one C/D journal append. |
| `2609-EDU-SRAM-B3-8.bin` | Exactly 4096 bytes, resident provider at B3:`$8000–$8FFF`. **Not** executable RAM-loader input. |
| `2609-EDU-SRAM-RAM.bin` | Load at `$0200`; inspection UI for the installed, matching ES1 provider. |

The provider body measures 961 bytes. Its 64-byte ES1 locator, code, FF fill
and CRC occupy one 4096-byte sector. B3:9 is retained. E remains VX1; A/B
remain monitors; C/D remain journals; F remains the exact installed bootstrap.
B0–B2 are retained in full, including the original B0 WDCMONV2 backup.

The request is `$6000–$601F`, normal read buffer `$6100–$613F`, provider
workspace `$6500–$65FF`. The RAM preflight also uses `$6300–$630C` for UI state.
Tools own their loaded RAM, stack and ZP D0/D1 plus E0–FF. F already protects
the service window; no additional permanent application-RAM boundary is
introduced. ES1 has no automatic reset activation, published F service-table
entry, named-storage manager or compatibility claim with the old `$6500`
gateway. Call only with B3 visible, foreground, 65C02 or 65C816 emulation,
D/DBR/PBR zero. Provider entry restores I/D flags; A/X/Y and ZP D0/D1 may change.
No NMI caller or concurrent peripheral owner is admitted.

## First hardware step: RAM preflight and preservation

This RAM-only procedure and the later ROM install are complete on 2609.
Its VIA snapshot was `00 00 00 00 80`, so no A acknowledgment was needed.
For a subsequent separately directed run, keep power on,
reserve the correct USB port/board identity, and preserve owner RAM if needed.
First double-read all four flash banks. Match every byte against the appropriate
current checkpoint. Before the original install this was sequence 1020, S,
banks 00; B3:8 was saved separately. The current installed checkpoint is
sequence 1021 with B3:8 count 27. Preserve the complete current owner history.

At REC, each command below takes Enter:

```text
C1
L
```

After `SEND BIN`, send **`2609-EDU-SRAM-PREFLIGHT-RAM.bin`** as raw binary.
The three-second receive idle starts it. Expected prompt: `EDU RO>`.

```text
?
S
V
```

S reports configured capacity `$00020000` (131072 bytes) and **physical presence
UNPROVEN**. INIT and S touch no SPI/VIA registers. V reads DDR/PCR/ACR/IFR/IER;
it does not read ORB or clear flags. An array of bytes read without error is
not proof of capacity, address decoding, data integrity or battery retention.
Absent/high MISO and invalid modes return status 07; stuck-low wiring can
produce valid-looking zero data and mode 00. Always retain this distinction.

If idle disabled CB flags `$18` are pending, an R command returns status 01
without reading ORB or driving pins. After examining V, the explicit command:

```text
A
V
```

checks disabled CB interrupts, compatible CB mode, idle shift/latch controls
and undriven SPI pins, then reads ORB **once** to acknowledge only those flags.
For the earlier observed 2609 state `00 00 00 1A 80`, IFR becomes 02. It makes
no GPIO register writes or SPI clocks. Any active owner or flags that fail to
clear cause refusal. Do not change VIA settings merely to force acceptance.
This reuses the policy documented in the
[closed disabled-CB issue](issues/SPI_2609_DISABLED_CB_FLAGS.md); it does not
acknowledge RTC power-fail evidence or touch an RTC latch.

```text
R 00000 10
R 0FFFE 04
R 10000 10
R 1FFFF 01
Q
```

R takes exactly five hex address digits and two count digits, 01–40 (1–64
bytes). It prints `STATUS COMPLETED MODE`, then data on success. Mode is
00/40/80. Only status is meaningful after an error. Q restarts F; saved S
returns to REC. It does not restore borrowed RAM or install anything.

For a complete baseline, save **two independent ordered 131072-byte exports**,
addresses 00000 through 1FFFF, using 64-byte reads at 00000, 00040, …, 1FFC0.
Record requested address, exact returned count, status and mode for every
chunk; stop on any error or missing/duplicate chunk. Compare the assembled
exports byte for byte and SHA-256. The ready kit includes an ordered address
list. Console excerpts and a few sample reads do not replace this backup.
Use a prompt-paced host capture, with a separate log for each complete pass;
do not paste the whole command list into an unpaced terminal. The supplied
file-only checker assembles both logs and rejects missing, duplicate or
unordered addresses, failed/short replies, mode changes or differing arrays:

```text
python edu_sram_backup.py --first pass1-console.txt --second pass2-console.txt --out SRAM-backup
```

Every data byte uses a fresh READ `$03` with its three-byte address, so the
reader preserves byte/page/sequential mode without WRMR `$01`. There is no
SRAM WRITE `$02`, probe, format or repartition command in these tools.

## Separately authorized ROM installation

This stage was separately authorized and completed on 2609. The following is
the recorded original transaction, not a replay instruction for the current
board. For any future install, prepare a new exact-current-state plan and
recheck its exact preimage and
port lease immediately before any later live install. Create a durable host
attempt record and retain the source/target hashes and console log. The
installer's on-board transaction is:

| Order | Action | Planned resulting state |
|---|---|---|
| 1 | Program/verify C600 SNBT row, commit byte last; no journal erase | seq1021, S, banks 00; B3:8 count 26 → 27 |
| 2 | Erase B3:8000; verify blank; program/verify provider; commit `$801F` last | New ES1 provider, all other sector counts retained |
| 3 | Verify all four bank hashes and return through F | REC with original F, MONs, VX1 and B0 |

All 32 prior counts and unknown-lifetime mask FFFFFFFF are imported. Only
the planned B3:8 erase attempt adds one. B3 C/D counts stay 78/47 because
C600 is an append. Its 16-byte config body is unchanged; no boot-policy or
saved EDU switch change is part of this install. The old byte-13 EDU setting
does not activate an old driver on b15. Do not copy 2609's counts to a new board.

Load **`2609-EDU-SRAM-INSTALL-RAM.bin`** using C1/L and raw SEND BIN. At
`RAM MINSTALL ? V W I Q>`:

```text
?
V
W
```

These are inspections. The flash-writing path starts only with:

```text
I
INSTALL EDU
```

The confirmation is deliberately within the installer's 15-character line
limit. Progress names C600 and 8000 and reports blank verification, body
programming/readback and final commit. After `ALL COMPONENTS VERIFIED`:

```text
V
Q
```

Then independently double-read all four banks and compare exact expected
images, including C600, B3:8, B0 and unchanged other sectors. Only verified
actual execution can update host wear history. An interrupted or completed
plan is stale: inspect REC/current journals, retain the attempted erase
reservation and create a new plan. Never blindly replay this BIN.

## Installed-provider acceptance and later work

Load **`2609-EDU-SRAM-RAM.bin`**, repeat `? S V`, use explicit A only if the
guarded pending-flag acknowledgment is needed, repeat boundary R reads, and
export the full array twice again. Compare every retained byte and mode with
the pre-install baseline. Finish with Q and REC, close the port and preserve
the entire console log, filenames, hashes, counts and evidence.

The inspection client verifies its immutable CRC, exact F and RAM service
CRCs, RA descriptor, complete ES1 header and provider CRC before entering the
provider. A damaged/missing provider returns to REC without touching VIA.
Incompatible F/RAM services halt before calling their console. CRC is a
corruption check; raw L executes before the tool can validate itself.

Offline CPU/NOR/bit-level SPI results are linked in the ready receipt.
The kit passed 48 offline groups, including independent reproduction of all
four BINs and complete-export parser fault cases. USB hardware read-only
acceptance now passed on 2609; electrical margins, repeated cold-reset,
battery retention, physical 65C02 and ACIA qualification remain outstanding.
This provider reads and preserves the existing layout; it does
not yet offer full legacy `EDU`, `SRAM SAVE/RESTORE/RUN/DELETE/RECLAIM/FORMAT`,
WORK, RAM reclaim on EDU OFF, or SRAM-backed boot journals. Those need a
separate matching port, explicit activation policy and preserving tests.

Sources: [builder](../prototypes/boot-record-v2/prepare_edu_sram_2609.py),
[provider](../prototypes/boot-record-v2/edu-sram-ro-provider.asm),
[RAM client](../prototypes/boot-record-v2/edu-sram-ro-client.asm),
[RAM preflight builder](../prototypes/boot-record-v2/prepare_edu_sram_preflight_2609.py),
[CPU/SPI/installer tests](../prototypes/boot-record-v2/test_edu_sram_2609.py).
