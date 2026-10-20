# rc1 DBG1 parent candidate and historical qualification

This directory retains the parent `v1f` builder/source and earlier candidate
package evidence. The current separately built candidate is
[`v1g`](../rc1-debugger-brkfix-r1/README.md), whose offline and hardware
qualification passed on 2604 and 2609, including both monitor slots and
rollback/reinstall. R3 and R4 closed cleanly with original RAM, flash/settings
and final drift verified. R5 also closed safely with its original-phase checkpoint
and final drift passed. The ten-pattern LED R6 continuation passed 93 new offline
checks, actual CPU qualification and both-board hardware preflight with restoration
and drift verified. R6 then closed cleanly at owner STOP after 12,803.703
monitored/active seconds, with 61/60 cycles and 976/960 hits on 2604/2609.
Both original full RAM images were restored/reread after final drift;
flash/settings matched and actual worker exit was verified. The ten-pattern
630-frame scope and prior runs remain separate evidence. Promotion stays held;
native applications/debugging remain excluded. See the
[current candidate status](../../../docs/rc1/DBG1_CANDIDATE_STATUS.md) for
closeout evidence and the immutable distribution r7 package/checksum review.

The parent source includes the MAINT compatibility correction (`v1f`). Its
guard compares all four bytes against the same DBG1 marker used by the boot
image. The prior `v1e` board candidate failed MAINT entry; its scoped debugger
and soak results do not qualify `v1f` or `v1g`. Fresh offline and
hardware requalification passed on 2604 and 2609, including both-slot MAINT,
registration/debugger/app checks and corrected-package rollback/reinstall.
The planned six-hour `v1f` soak was subsequently stopped by the owner; it is
not a completed six-hour qualification. Offline review found `$82` invalid-ID
and `$84` RAM-end boundary issues in `v1f`; the separate `v1g` candidate fixes
those paths. No new eight-hour soak is claimed for `v1f`. The MAINT correction
changes four comparison
bytes and the utility CRC, requiring B2:8000 and B2:D000 in the preserving
install/rollback plan. The frozen generation-49 release is unchanged.

Historical `v1f` requalification evidence is in
`output/qualification/rc1-dbg1-maint-requalification-2026-10-19-1718Z`:
72 hardware registration cases, 128 verified breakpoint hits and 84
device-verified transfers. Both original application RAM archives, monitor
preferences and RTC settings were preserved. See the
[board results](../../../docs/rc1/DEBUGGER_BOARD_RESULTS.md#maint-correction-and-requalification).

The parent generation-50 candidate is based on the frozen generation-49 rc1
sources. It installs automatic RAM BRK debugging in MON A and MON B.
The published rc1 tree is unchanged. The candidate passed scoped board trials
on 2604 (65C02) and 2609 (65C816 E=1), in both monitor slots on each board.
Offline qualification also covers separate 65C02 and 65C816 emulation models.
Native applications and native debugging are outside this candidate.

## Reproduce the parent build and tests

Historical `v1f` package staging uses `stage_corrected_candidate.py` with a
fresh `--out` directory and an offline review receipt. It copies the exact
tested `v1f` image and board kit, retaining preparation-time pending
soak/drift results and findings. These are historical status fields, not
current `v1g` acceptance. It does not promote the release. `package_candidate.py`
and the templates under `package/` describe the historical `v1e` distribution
r2; their eight-hour receipts must not be reused as `v1f` qualification.

Requires Python 3.10+, WDC02AS and WDCLN on PATH, and py65 for the tests.
Use a new, short output path each time:

```text
python release/candidates/rc1-debugger/build.py --out BUILD/rc1-debugger-v1
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1 --deps path/to/py65-parent
python tools/fetch_rc1_debugger_816_model.py
python tools/test_rc1_debugger.py --build BUILD/rc1-debugger-v1 --cpu 65c816-e --deps path/to/py65-parent
```

An installed py65 also works without `--deps`. The test's default dependency
path supports this repository's existing local py65 copy. `--skip-boot` runs
only the development subset; it is not a full qualification run. Fetching the
816 model is a one-time network setup step, pinned to a commit and SHA256 with
its license retained. Tests execute entirely offline. `--deps-816` selects a
different directory containing the pinned model; its hash is checked on import.

Outputs include `firmware.bin` (B1/B2/B3, 96 KiB),
`payload/debugger-a000.bin`, `debugger-build.json`, `debugger-test.json`,
`debugger-test-65c816-e.json`, and separate command transcripts. Development
subset reports have a `-subset` suffix so they cannot replace full reports.
The build checks the component fits its 4 KiB sector
and seals it with CRC16. It resolves ASM tables and MON A/B handlers from the
matching source build rather than assuming published private addresses.

## Use

The [rc1 debugger guide](../../../docs/rc1/DEBUGGER_GUIDE.md),
[ASM walkthroughs](../../../docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1),
[registration ABI](../../../docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
and [board result summary](../../../docs/rc1/DEBUGGER_BOARD_RESULTS.md) describe
the generation-50 extension separately from the published generation-49 release.
The test harness's `--manuals docs/rc1` option assembles and executes the four
marked manual examples in both slots, with separate `-manuals` reports.

Assemble `BRK $xx` (or `BRK #$xx`); bare `BRK` supplies `$00`. Each emits two
bytes. Load/run an application normally, such as `G 0200`. No debugger enable
command is required. `$00-$7F` stop at `DBG>`. The displayed PC is the next
instruction after an explicit BRK, or the original instruction at a patched
breakpoint. All numeric command fields below are hexadecimal.

| Command | Meaning |
| --- | --- |
| `C` | Continue, automatically rearming persistent breakpoints |
| `S` | One instruction, entering a RAM subroutine |
| `N` | One instruction, stepping over JSR; user breakpoints still interrupt |
| `B` / `B address` | List / set one of eight persistent RAM breakpoints |
| `BC address` / `BC *` | Clear one / all breakpoints |
| `R` | Show PC, A, X, Y, P and stack pointer |
| `R A=12`, `R PC=0200`, `R SP=FF` | Edit one saved register; P edits status |
| `D start [end]` | Shared monitor hex dump; low pages read saved application images |
| `M address byte ...` | Shared monitor atomic RAM edit; low pages edit saved images |
| `U [address] [count]` | Disassemble RAM; defaults to saved PC and eight instructions |
| `F` | List built-in and registered BRK function IDs |
| `?` | Command list |
| `X` | Abort and return to rc1 |

The shared D/M adapters return through the monitor's existing one-shot prompt
hook and preserve its previous hook. While paused, patched code is restored,
so D/M/U see original instructions. Editing a breakpoint address changes the
instruction that is saved when that breakpoint is next armed. Low-page D/M
requests must stay within one page; zero-page writes above `$DF` are refused.

Step-over checks the expected stack depth, including recursive calls. Branch,
jump, call and return instructions are emulated in the saved context; ordinary
instructions run on the CPU with a temporary successor breakpoint. `S` refuses
transfers out of application RAM; `N` can run a firmware call to its return.
WAI, STP and opcodes not supported by ASM cannot be stepped. Stepping is not
cycle accurate and does not virtualize IRQ/NMI execution. A program must not
overwrite armed breakpoint bytes. Source symbols, watchpoints and native 816
debugging are not included. Normal runtime preconditions remain 816 E=1,
the direct-page register, DBR and PBR zero for service calls, and IRQ masked.

On the 816, `U` and stepping support the 180 opcode encodings shared with ASM's
65C02 instruction set (178 step candidates after excluding WAI/STP; BRK uses
its service/stop path). The 32 RMB/SMB/BBR/BBS encodings have different meanings
on the 816 even with E=1. They display as `.BYTE` and `S`/`N` refuse them,
along with the 44 other encodings outside ASM's table. Full 816-only instruction
decoding is outside this version. Clear a breakpoint on an unsupported
instruction before using `C` to execute it. The hidden accumulator B byte is
preserved by the debugger; it has no display/edit field in this ABI.

Hardware interrupt vectors must reach STR8-N in the selected flash bank.
B1/B2/B3 supply matching vectors. B0 is not included; its empty or unrelated
vectors cannot provide automatic BRK entry merely because the program is in RAM.

## BRK functions and registrations

| ID | Contract |
| --- | --- |
| `$80` | Query: A=ABI 1, X=16 user slots, Y=4 system slots, C=1 |
| `$81` | Register user callback: A/X=request low/high pointer; C=1,A=0 success, C=0,A=1 invalid/duplicate/full |
| `$82` | Unregister user ID in A; same success/error convention |
| `$83` | Print saved registers and continue, preserving registers/flags |
| `$84` | Output Y bytes at A/X RAM pointer, preserving registers/flags; invalid range returns C=0,A=1 |
| `$A0-$BF` | Four dynamic system registrations, independent of user capacity |
| `$C0-$FE` | Sixteen dynamic user registrations |
| Other IDs | Stop for inspection |

The four-byte registration request is `ID, handler-low, handler-high, flags`.
Flags must currently be zero. Request and callback must be in permitted
application RAM. Callbacks receive A/X=`$7000`, Y=ID, return with RTS, and edit
the saved context to return application results:

| Context offset | Value |
| --- | --- |
| 0-1 | Resume PC, little endian |
| 2-4 | A, X, Y |
| 5 | P |
| 6 | SP |

Callbacks must preserve bank selection and return with RTS. Nested BRK calls
return C=0,A=9 without replacing the outer context. The system registration
entry is the LE16 pointer at B1:`$A008`: bank 1 visible, IRQ masked, no active
debug session, A/X=request pointer, C/A success/error as above. It accepts only
`$A0-$BF`. The user BRK registration API cannot replace these or built-ins.
All dynamic registrations and breakpoints are cleared at HOLD/X/reset; drivers
must register again for a new program. This prevents stale pointers after loads.

## Memory and firmware integration

- Debugger component: B1:`$A000-$AFFF`; B1:`$9000-$9FFF` remains available.
- Application RAM limits and every ASM buffer remain unchanged: normally
  `$0200-$64FF`, or through `$66FF` when optional services release their area.
- Fifteen-byte BRK entry at `$7B81-$7B8F`; lifecycle bytes at `$7BFC-$7BFF`.
- Registry: `$7C30-$7C7F` (4 system plus 16 user entries, four bytes each).
- Eight breakpoint records and two internal records are in `$7040-$7067`.
- `$7000-$73FF` is shared monitor workspace: context, command scratch, stack
  snapshot, zero-page snapshot and RAM return trampolines. No application bytes
  are reserved for these. S/R/T validation refuses staging during an active
  debug session. Status loaders and flash-sector staging own this area only
  outside the session; calling private monitor loaders from an application is
  unsupported.
- Monitor header padding installs the entry automatically and routes HOLD
  through cleanup. Existing monitor payload lengths and fixed public ABI
  addresses remain unchanged. Same-size worker guards reject debugger-sector
  writes before flash command sequences, without disturbing the sector buffer.

The offline full-image tests cover both monitor choices on both processor
models and preserve the entire `$0200-$66FF` area with EDU OFF. The 816 run
checks E=1 and the direct-page register, DBR and PBR at zero during execution,
exercises BRK/RTI frames and stack
wrapping, verifies hidden B preservation, compares 177 common instructions
through `S` with direct execution on the 816 model, and checks all 256 decoder
bytes at two addresses. Application RAM, saved zero page, registers/status and
allocated stack results are compared. Entry uses nine free stack bytes for
the three-byte hardware frame, four saved register/bank bytes, and SELECT's
two-byte JSR return. Applications must leave that stack headroom; bytes below
SP are scratch rather than preserved application stack contents.

The existing rc1 reset CPU detector briefly exchanges E/C before returning to
E=1. The runner permits only its exact five-instruction native sequence, once
per full boot; native application/debugger execution is rejected. This does
not add native-mode debugging support. The independent CPU model is
[tmr4/py65816](https://github.com/tmr4/py65816/tree/530658b4fd848c69bfb2065f8e9bb5e70ef5d2a9),
with architectural checks based on the
[WDC W65C816S data sheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf).
The model and FT245/bank fixtures do not qualify device timing, electrical
interrupts, or flash installation. The offline suites do not access a board.

Prior local result (before the MAINT correction): `BUILD/rc1-debugger-v1e`, 3967 bytes of code plus a two-byte
CRC, leaving 127 bytes in B1:`$A000-$AFFF`. Application RAM remains intact.
All 21 65C02 groups and all 24 816 emulation groups pass, including both full
monitor boots and 512 decoder cases per CPU. A second fresh build produces
identical firmware and debugger bytes. Frozen rc1's 97 source hashes also pass.

## Historical experimental board package

[Board-test instructions](BOARD_TEST.md) cover exact-source installation,
fresh-capture rollback, original application RAM restoration, both monitors,
and the BRK/C/S/N/eight-breakpoint smoke test. [BRK ABI proposals](BRK_ABI.md)
describe possible future common services; firmware remains at functions 80-84.

The parent `v1f` local package is `BUILD/rc1-debugger-boardtest-r2`. Preparation reads only
local files; serial access exists only in separately invoked `board_link.py`
operations. No board-specific plan is authorized by a historical capture.
Install and rollback require repeated fresh captures and explicit board/USB IDs.
The rollback planner advances wear records and restores the nine original
firmware sectors while preserving current settings and other flash data.

The corrected suites include MAINT marker acceptance/refusal and the exact
packaged smoke (22 groups on 65C02, 25 on 816 E=1). Four programs/scenarios
run through both monitor choices on
each CPU, including all eight breakpoints hit twice, ninth-slot refusal,
individual/all clear, X cleanup, shared D/M/U and the BRK query service.

## Historical 2604 hardware checkpoint

On 2026-10-19 UTC, the owner-authorized trial installed package
`BUILD/rc1-debugger-boardtest-r1` on 2604 (65C02, USB A10MQGVHA).
Both MON A and MON B passed BRK entry, C/S/N, shared D/M/U, all eight
persistent breakpoints twice per slot, ninth-slot refusal, individual/all clear,
X/HOLD cleanup and BRK 80 query. All nine installation transfers were
device-verified, followed by a physical reset confirmed by the owner.
Monitor changes used the existing P/J3 software reboot path.

The run directory is
`output/qualification/rc1-debugger-2604-boardtest-2026-10-19-024408Z`.
It contains fresh repeated pre/post flash and application RAM captures,
installation and per-slot smoke receipts, the combined `report.json`, and an
offline rollback plan. Original application RAM was restored byte for byte,
the original MON B preference was restored, and RTC controls/trim were retained.
Rollback was prepared but not executed; capture again if the board changes.

During that trial, both boards received one-shot drift collection and 2609
firmware was not written. This checkpoint covers the 2604 installation and debugger smoke paths;
816 hardware, native debugging and interrupted-write recovery are outside it.

## Historical 2609 emulation-mode hardware checkpoint

The same package subsequently passed the owner-authorized 2609 trial
(65C816, USB A10MPQXCA). All nine installation transfers were device-verified,
the owner confirmed physical RESET, and all four flash banks matched the
installation targets before monitor preference changes. MON A and MON B each
passed the same four smoke scenarios: BRK, shared D/M/U, C/S/N, all eight
persistent breakpoints twice, ninth-slot refusal, clearing, X/HOLD cleanup
and BRK 80 query. This gives 32 verified breakpoint hits on 2609.

Six observations confirmed E=1, DBR/PBR/direct page zero, IRQ disabled and
decimal clear, including checks before and after each monitor's smoke run.
The RAM observer uses SEC/XCE to record prior E while forcing E=1; it cannot
enter native mode. The existing reset CPU detector is unchanged. Native
applications and debugging were not tested.

Evidence is in
`output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z`:
fresh repeated pre/post captures, per-slot receipts and the combined
`report.json`. All 25,344 original application RAM bytes and MON A preference
were restored. The final audit verified the seven firmware sectors, preserved
other flash data and settings, and accounted for exactly nine erases. RTC
controls/trim were preserved. Rollback was prepared and verified offline but
not executed; capture again if the board changes. 2604 was not accessed during
this trial. Periodic sampling and soaks were stopped at that checkpoint;
the later `v1g` continuation has separate authorization and evidence. Interrupted-write
recovery is outside this checkpoint.

## Historical subsequent eight-hour qualification

The earlier `v1e` generation-50 firmware passed 431 rc1/ASM/DBG1 soak cycles and
6,896 persistent-breakpoint hits per board over 8h 00m 24s, without failures.
2604 used MON B; 2609 used MON A in E=1. Earlier trials covered both slots.
Full original application RAM restoration, unchanged flash/settings, and final
NIST drift collection passed. Native applications/debugging remain excluded.
These results do not qualify the later `v1f` or `v1g` images. Install and
rollback still require fresh captures and newly derived plans.

