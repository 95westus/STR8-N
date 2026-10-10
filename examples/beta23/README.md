# Runnable 65C02 examples for beta23

These programs use the public ABI described in the
[technical guide](../../docs/STR8N_V2_BETA23_TECHNICAL_GUIDE.md).
They are standalone WDC 65C02 assembly sources, linked at **$2000**.
Each checks the RAM console ABI, optional-service discovery and the relevant
service signature before calling it. They enter with SEI/CLD and return through
HOLD. On an 816, the caller must already use E=1, D=0, DBR=0, PBR=0;
native-mode execution is outside these examples' contract.

| Source | Purpose | Retained effects |
|---|---|---|
| [read-time.asm](read-time.asm) | Read/copy UTC and print its date/time | No SET, ACK, TRIM or EEPROM write |
| [read-spisram.asm](read-spisram.asm) | Read 16 external SRAM bytes at $10000 | No WRITE, PROBE, mount or format |
| [work-area.asm](work-area.asm) | Claim 64 bytes, back up, write/read/verify, restore/verify, release | WORK session/ticket/claim metadata changes; original claimed payload restored on success |

[example-abi.inc](example-abi.inc) provides the small discovery/printing helpers.
Read it alongside each source; the builder copies it into the assembly staging
directory. All three fit below $3000. They use ordinary CPU RAM at the addresses
listed below, so loading/running them overwrites that application scratch.
They do not modify firmware or flash records. Retained SRAM requires working
supplies and valid metadata; a successful API call does not certify battery life.

## Build and model check

From the repository root, with WDC02AS/WDCLN on PATH and the repository's Python
dependencies available:

```powershell
python tools/build_v2_beta23_examples.py
python tools/test_v2_beta23_examples.py
```

The builder emits source staging, listings, binaries, S19 files and hash metadata
under `BUILD/beta23-examples/<name>/`. The test executes the assembled code
against frozen beta23 generation 32. Normal UTC/SRAM/WORK paths use the real
bit-level device model; additional WORK failure cases use the ABI transfer-fault
model. The test's synthetic SRAM setup is not performed on any physical board.
Build and test tools open no COM port. These new programs are model-tested;
they have not been run on hardware by this documentation/example update.

## Required release-package contents

These examples are mandatory contents of the next beta23/RC release ZIP and
published source. [release-package.json](release-package.json) records the exact
source-to-package mapping. Keep this tutorial, all three `.asm` sources, the
shared include and checked S19 applications together. Packaged S19 files belong
under `examples/beta23/bin/`; local builds continue to use BUILD paths below.
Include the technical guide and build/test support, with its dependency closure
or a documented complete source kit. Final packaging must rebuild/check against
the firmware being shipped and include the example files in its checksum manifest.
Generated files being ignored by Git is not a reason to omit them from the ZIP.

## Load a read-only example

Use a beta23 board with active EDU ON. Select B3, enter `L`, send the generated
S19 as ASCII text with approximately 40 ms between lines, wait for the monitor
prompt, then enter `G 2000`. Load one example at a time. Typical source file:

```text
BUILD/beta23-examples/read-time/read-time.s19
```

The terminal file-send action is required between L and G; do not type the
filename as a monitor command. Use ordinary ASCII S19 transfer, not a firmware
installer or raw binary transfer. The examples contain no SAVE or erase command.

The RAM ABI must be present. If `RA`,1,13 is absent, the program deliberately
loops without calling an unverified console/HOLD entry; use physical RESET.
With verified RA but EDU OFF/missing service, it reports error `$80` and returns.
If the signature exists but hardware fails, it reports the service status.

## Reading UTC

Load `read-time.s19`, then `G 2000`. Example output:

```text
UTC 2026-10-08 19:53:15
B3>
```

The date is illustrative; hardware prints its current UTC. The code requires
SV clock bit $01 and `RG`,1,4, calls RTC_READ at $6504, checks Carry/A, and
copies the eight binary calendar bytes before formatting or returning.
It formats binary fields as decimal; the RTC result is not ASCII or raw BCD.

| CPU address | Meaning |
|---|---|
| $3000–$3007 | Copied year LE16, month, day, weekday, hour, minute, second |
| $3008 | Copied RTC flags |
| $3030 | Result: $00 success; use the copy only on success |

On failure it prints `TIME error: xx` and leaves earlier calendar scratch
unspecified. It never sets the clock, clears an outage or changes trim. For a
user application, consume the copied fields before loading another program.

## Reading external SPI SRAM

Load `read-spisram.s19`, then `G 2000`. The default external address is **$10000**,
which requires the third address byte and is distinct from CPU RAM $10000.
Received data goes into CPU **$3100–$310F**. The request is fully initialized:

```text
01 00 00 00 01 00 31 10 00 00 00 00 00 00 00 00
```

Operation READ=$01; address bytes `00 00 01`; CPU pointer `00 31`; count $10.
The code requires SV bit $08 and `SM`,1,1, calls $66A6, checks A/Carry and
exact completion, and copies the successful request/results to $3000–$300F.
Final status is at $3030. It prints data only after a verified complete read:

```text
SRAM READ: 00
DATA: 07 14 21 2E 3B 48 55 62 6F 7C 89 96 A3 B0 BD CA
B3>
```

Those are model-fixture bytes, not expected contents on a user's board. Raw
bytes do not establish a valid saved object or WORK allocation. To customize
the example, change REQUEST's LE24 address, CPU pointer and count; keep the
buffer in $0200–$64FF and count 1–64. Public raw WRITE is denied; use WORK for
owned writes. PROBE temporarily changes a reserved byte and is not used here.

## Using the WORK area

This example needs a **valid v2 allocation and session metadata** and a free
claim interval/slot. A valid layout header or successful capacity QUERY alone
does not prove the retained session/claim packets are usable.
Use `R WORK`, `?`, then `Q` to inspect current allocation. Errors $40/$41/$49
require deliberate inspection/administration; the example does not automatically
format, upgrade, repair or resize. Do not format retained user data merely to
make a demonstration pass. Back up first and choose the appropriate documented
WORK administration path if initialization is actually intended.

Load the paired library without running it, then load the example:

```text
B3> R 2 WORK L
... Done ...
B2> B3
B3> L
... send BUILD/beta23-examples/work-area/work-area.s19 ...
B3> G 2000
```

Select B3 explicitly regardless of the prompt returned by restore. WORK 1.2
must occupy $5000–$648A with `WK`,1,2 at $5006; its API is $5003. Loading another
program over that range invalidates the library. The example remains below
$3000, and its requests/buffers are outside WORK's range.

The source demonstrates these steps:

1. Discover SRAM and WORK; QUERY the current layout without initializing a claim.
2. Refuse legacy/secondary-only layouts that need explicit administration.
3. CLAIM 64 bytes with demonstration owner `$BEEF`; copy the entire eight-byte handle.
4. READ the original 64 bytes into a backup; require full completion.
5. Fill a CPU test pattern, mark the claim dirty before WRITE, and write/verify it.
6. READ and compare every test byte.
7. Restore the original backup, READ and compare it again.
8. RELEASE the owner/handle and return to the monitor.

Changing owner `$BEEF` to an application-specific nonzero value is straightforward.
Owner alone is insufficient: all eight handle bytes identify slot/epoch/ticket.
The source preserves the handle across operations and attempts cleanup after
an unconfirmed claim when a returned ticket is available.

Normal output:

```text
WORK: 00 operation=00 restore=00 release=00 claim-may-remain=00
B3>
```

| CPU address | Meaning |
|---|---|
| $3000–$301F | 32-byte WORK request/result |
| $3020–$3027 | Copied handle (slot, zero, epoch LE32, ticket LE16) |
| $3028 | Possible remaining claim flag |
| $3029/$302A | Complete-backup / attempted-write flags |
| $3030/$3031/$3032/$3033 | Primary operation / restore / release / overall status |
| $3100–$313F | Test pattern |
| $3200–$323F | Original claimed bytes |
| $3300–$333F | Verification readback |

The request pointer is passed as A=low/X=high. Relative offsets use bytes 12–14,
count byte 15 and CPU buffer LE16 at 16–17. WORK returns A=status/Carry and
clobbers X/Y, $D0–$D5 and its own scratch; it leaves IRQ disabled/decimal clear.
The demo assumes no RESET or competing caller during the transaction.

On a failed/partial test WRITE, the demo attempts to restore the complete
backup. If restoration verifies, it releases the handle while retaining the
original operation error in the report. If restoration cannot be verified,
it retains the possible claim/handle and reports the restore failure. A failed
RELEASE is also reported; its effects may be unconfirmed. Status zero for a
cleanup stage that was not attempted does not prove that stage succeeded;
interpret it with the primary status and possible-claim flag.

If `claim-may-remain=01`, preserve the handle, backup and status before loading
another application. Inspect/retry cleanup with the matching owner/handle.
RESET invalidates old WORK handles; it does not restore the workspace bytes.
The successful demo restores the payload, but session epochs, ticket history
and released claim metadata are intentionally updated. It is not a byte-for-byte
metadata rollback or a power-loss-atomic transaction.
