# 2609 developer tools: 816 emulation RAM scope

Owner-authorized November 2, 2026. Use only2609/COM8 when RTC collection
permits the shared lease and a420-second window. Leave2512/2205/2604 alone.
No flashing, journal/SPI-data/WORKSPACE/RTC-setting writes, resets or power
cuts are included. F stays golden; all four flash banks and boot/settings/
wear history must remain exact. No firmware rebuild or CPU simulation.

Reuse candidate2's exact ASM-RAM.bin and DBG-RAM.bin from a fresh verified
extraction. Use its console transfer backend. The existing2609 B0 WDC image
is retained; this scope does not install AP/02 images or launch nonexistent
installed ASM/DBG aliases.

Capture fresh owner RAM0200-66FF, ZP00-DF, full6B00-77FF cache and original
7E02-03/7E67-69 hooks. Restore/read back those regions and hooks on exit;
finish REC>, release COM8 and leave RTC eligible. Read every flash bank
before and after; the current shared marker supplies the admission hashes.

The required runtime context is E=1, eight-bit registers, D/DBR/PBR=0 and
IRQ masked. A bounded RAM probe observes E through SEC/XCE (retaining E=1),
and uses PHB/PHD/PHK with bank-zero long stores to record the bank/direct-page
context. It normalizes the required zero context before HOLD; refuse a
nonconforming observation. Repeat after the tools. Ordinary debugger stepping
never executes mode changes, bank changes, long addressing or block moves.

CPU compatibility review uses the [WDC W65C816S datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf),
especially emulation/vector and opcode-compatibility sections, alongside the
paired source decoder/stepper. The assembler remains a65C02 cross-assembler;
executing its common subset on an816 is distinct from supporting816 assembly.
RMB/BBR source emission is checked without executing those bytes on2609.

Required RAM groups: exact packaged HELLO assembly/export/run; labels/EQU,
diagnostics and common stack/BRA/STZ execution; real emulation BRK/register
framing, S/N/JSR/RTS; all32 reassigned x7/xF opcode refusals and17 additional
unsupported816 opcode refusals; logical branches/indirect/RTI and atomic JSR
guards; all eight real breakpoint hits; public-call N and HOLD; real callback
and nested-BRK behavior; X/ZP/cancellation/hook cleanup; before/after CPU
context and complete flash preservation. Unknown instructions must be shown
as .BYTE and refused for S/N without execution. Free-running C is not a
sandbox; use only the explicit safe fixtures.

Source persistence writes, an816 assembler, native16-bit debugging, hardware
IRQ debugging, AP/02 flash installation, physical GUI keys and publication
are outside this RAM qualification.

Driver: `tools/trial_2609_devtools_g2_emulation_ram.py` in the workspace root.
