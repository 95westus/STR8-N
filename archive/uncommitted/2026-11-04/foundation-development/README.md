# STR8N-F v0.3.0 — Foundation / BASE1 / PR05

**A 4 KB foundation for your own environments.**
Up to four selectable banked environments, running one at a time on a shared
CPU, approximately 32 KB physical RAM and peripherals.

Foundation is the stable 4096-byte B3:F boot/recovery component. BASE1 identifies
the boot/layout contract; PR05 identifies the fixed private compatibility
profile used by the qualified RAM tools. C/D contain boot policy and tracked
wear. The optional MON/tool layer has its own version and generation.

## Current unified candidate4

MON A/B **0.1.0-dev g00000010**, WB2 gE, PROGRAM g3, SRAM/WORK g4,
CLOCK and **ASM/DBG g2**, with full **MAINT.bin / FLASH.bin loaded at $0200
from REC>**. MAINT and FLASH are no longer resident applications. Traditional
startup/status, VERSION/TIME/trim, Dump/Modify, APPS, storage/BATCH/loaders and
the developer bodies are shared across the supported CPU paths.

The compact profile matches the qualified 2512/2604/2609 setup: 92 KiB in
allocated sectors, including F and C/D, with 36 KiB in fully erased sectors.
B0:A–D holds ASM/DBG; the remaining banked space still needs owner-image review.
Saved board settings, RTC calibration/history and SRAM geometry remain per board.

Read the [operator manual](docs/NATIVE_UTILITIES_MANUAL.md),
[ASM/DBG guide](docs/DEVELOPER_MANUAL.md),
[terminal instructions](docs/SERIAL_CONSOLE.md) and
[current qualification/remaining gates](docs/UNIFIED_CANDIDATE_STATUS.md).
The new REC g1 MAINT includes its full editor/copy/BOOT core but not the later
EDU SAVE/named-X front doors. The assembler targets65C02; DBG's816 scope is
common 8-bit emulation. Native816 is not included.

The current components have dated board qualification. This freshly packaged
candidate needs its own extracted-kit live acceptance; older archive passes
are not transferred to it. Packaging performs no firmware build or board access.
The complete published Foundation operator subkit is kept byte-for-byte exact;
the current Python terminal is separate, launched with `python terminal.py`.
No vendor WDC firmware, private board captures or saved settings are packaged.

From the C:\SRC\STR8-N workspace, build a fresh local ZIP with:

```text
python release/str8nf-v0.2.0/tools/package_compact_candidate.py --out BUILD/unified-g10-candidate4-20261102-r1
```

No publication/tag/push is performed. A fresh BUILD directory is required.

## Published Foundation remains unchanged

For WDC **W65C02SXB** and **W65C816SXB**, using65C02 or65C816 emulation.
Matching W65C02EDU/W65C816EDU add-ons are optional; BASE1 boot/recovery needs
neither EDU nor SPI SRAM. Compatible user-supplied environments share the
physical CPU/RAM and execute one at a time.

[Published v0.3.0](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0):
[4KB F.bin](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/F.bin),
[operator kit](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0.zip),
[source ZIP](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/STR8N-F-BASE1-0.3.0-source.zip)
and [checksums](https://github.com/95westus/STR8N-F/releases/download/v0.3.0/SHA256SUMS.txt).
The [Foundation user manual](docs/USER_MANUAL.md) covers the published migration,
provisioning, opaque installation/readback and saved-default workflow.

F stays **0.3.0 g00000001 BASE1/PR05**, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Raw L accepts $0200–$64FF; preservation tools escrow application RAM through
$66FF and owner ZP $00–$DF. Interactive tool loading itself does not restore it.

Historical branches, Candidate3/developer preview archives, the original2604
rc1 g0034 local archive and their dated acceptance documents remain intact.
A WDC backup can be kept privately on the host; a complete WDC B0 fallback
conflicts with the full B0:A–D developer layout. Factory restoration is a
separate operation that replaces Foundation, not a normal MON upgrade.
