# Historical ASM/DBG BASE1: first 2512 RAM increment

This dated record retains the original BUILD paths, trial scope and candidate
identities. Use [STR8-N DEV ASM/DBG](DEVELOPER_MANUAL.md) for current operation,
[component/source/releases](COMPONENT_GUIDE.md) for current files and
[formats](FILE_FORMATS.md) for RAM BIN versus S19 export. Named-kit acceptance
limits are in [qualification scope](QUALIFICATION_SCOPE.md); private detailed
trial records referenced below are not distributed in this source edition.

November 2, 2026. The owner requested ASM/DBG on2512 before further fleet
rollout. Work is active. This is a separate developer increment above frozen
Foundation0.3.0 g1 BASE1/PR05; it does not modify Candidate3 or published files.
The preserved rc1 sources/reference boards remain intact. The subsequent
initial2512 RAM workflow passed (private record `ASM_DBG_2512_RAM_ACCEPTANCE.md`). Flash
installation and the broader developer feature gates remain open.

## Concrete candidates

| Module | Current build | Memory and status |
| --- | --- | --- |
| Resident ASM/editor | `BUILD/asm-base1-g1-r6/ASM-BASE1-RAM.bin` | 24,829-byte RAM packet; core4000-5CF5, paired source helper5D00-62FC |
| DBG1 port | `BUILD/dbg-base1-g1-r5/DBG-BASE1-RAM.bin` | 25,096-byte RAM packet; unchanged r4 code4000-4F48, paired opcode/length tables5F00-6407 |

The packets are trialed independently; their code overlaps deliberately. ASM
retains the existing numbered editing, NEW/LIST/PASTE, labels/local labels,
EQU, directives, assembly, diagnostics, LST/SYMS, DUMP/S19 and QUIT. Its output
is0200-1FFF, source2000-37FF, symbols3800-3FFF and state6500-66FF. The PROGRAM
adapter implements AS/1 source save/load using the admitted SP/g3 provider;
positive persistence subsequently passed its approved320-byte fixture (private
record `ASM_AS1_PROGRAM_ACCEPTANCE.md`). It checks
load0200, restore-only entry and capsule bounds before loading source. Flash
source persistence explicitly returns unavailable in RAM1 because loading
the current flash workbench would overwrite the resident RAM assembler.

DBG retains registers/editing, disassembly, checked RAM D/M, eight user
breakpoints, step, step-over, continue, BRK services and X. Initial application
RAM is0200-3FFF. It uses a paired BASE1 wrapper for7E02; its five-byte public
BRK/HOLD ownership replaces the old rc1 stack/bank wrapper, monitor-D/M and
7DF9 hooks. Original hooks and patched instructions are restored by X or the
application's HOLD before entering MON. It is a single-session RAM launch,
not a debugger left armed while arbitrary monitor tools reuse its scratch.
First target is2512/65C02. 816 emulation/native acceptance is not claimed.

## Initial live scope: RAM only

Only2512/COM4, when idle and RTC collection permits the shared lease. No flash,
journal, PROGRAM/WORKSPACE, EEPROM, RTC time/trim or power-fail ACK writes.
No reset or power cut. No other-board access, source-only system rebuild,
publication, commit or push.

Capture fresh owner RAM0200-66FF, ZP00-DF, provider-cache7000-74FF and the
five original bytes7E02-7E03/7E67-7E69. Require the original BRK default7E57
and HOLD JMP7E93, current MON B g10/65C02, and the exact admitted F/provider.
The debugger also checks the complete original HOLD target before activation;
it refuses a different hook owner.
The candidate may borrow those RAM ranges and hooks. Restore and read back
the original owner/cache/hooks after success, cancellation or an error. If
the debugger has not stopped at a known prompt, retain the restoration guard
and obtain controlled recovery rather than loading over running code.

Exercise resident editing/assembly and meaningful diagnostics; verify emitted
bytes independently and execute a returning marker program. Exercise only
cancelled source load and explicit unlinked-flash refusal in this first scope.
Then use a bounded RAM BRK fixture for registers/U, S/N, breakpoint hit, D/M,
C and program-HOLD cleanup, followed by X cleanup. No persistence fixture is
implicitly authorized by those console tests. Recheck B3/F/settings/history,
restore owner/cache/hooks and finish REC> with COM4 released and RTC eligible.

Driver: `tools/trial_2512_asm_dbg_base1.py` in the workspace root. The r3
runtime receipt passed; the acceptance document records the two preceding
interrupted trials and exact recovery. Build preparation corrected host symbol/branch handling, paired
source return-stack depth and the raw-L packet bound; successful assembler
bytes were reused for source-helper corrections. No routine CPU simulation,
F rebuild or MON/workbench rebuild was run.

## Before installation or shipping

The initial RAM workflow and positive AS/1 PROGRAM persistence/fault/
cancellation cases passed. The later 2512 flash preview (private record
`ASM_DBG_FLASH_PREVIEW.md`)
adds normal MON/APPS/R launch paths and a separately reviewed installation.
The [SF/1 FLASH-source increment](ASM_FLASH_SOURCE_INCREMENT.md) subsequently
passed and is installed on2512. The reduced RAM layout is also used
by this RAM-staged preview; it is not the later full-RAM XIP memory budget.
Qualify the paired816-sensitive path later without replacing the reference
boards. Package and test a later extracted developer kit after those gates.

Historic technical plan: private `MON_ASM_DBG_RELEASE_GATE.md`. Current public
scope is summarized in [qualification scope](QUALIFICATION_SCOPE.md).
