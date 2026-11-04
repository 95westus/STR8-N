# NFM1 RAM migration engine contract

This source is a new, unqualified RAM migration engine. It does not call WDC
firmware or N/F services and contains no vendor firmware. Flash/FT245 handshake,
polling and FNV arithmetic follow the project's earlier RAM-worker patterns.
No device has been accessed or migrated with this engine.

The host must make durable original-bank and affected-RAM backups, choose an
explicit admitted transaction, reserve its erases durably, load and read back
the complete RAM image, and only then execute it. The unrendered template has
no valid plan/self-hash and refuses before any flash erase/program.

## RAM and CPU entry

- Upload exactly 8192 bytes at 2000-3FFF. Never upload the WDC 816 stack at 0700.
- Entry 2000: 65C02, or 816 emulation with D/DBR/PBR zero.
- Entry 2010: 816 native or emulation, executing in bank zero. Its shim enters
  emulation, sets D/DBR to zero and initializes the emulation stack.
- Staging: 4000-4FFF. Scratch: 6000-601F. ZP: E0-E9. Stack: 0100-01FF.
- Code must end before 3000. All code, messages and flash polling are in RAM.
- Console is FT245 USB only; supported flash ID is manufacturer BF, device B5.

For an F-recovery start, the host first renders the same 8192-byte template,
then calls `build.recovery_loader(rendered_template)` and sends the resulting
BIN through raw L at 0200. It contains 32 descending-page copy loops followed
by the template, relocates the template to 2000-3FFF, and jumps to 2000. Copying
backwards is necessary because the source blob overlaps its destination. The
wrapper is 8611 bytes and fits within raw L's 0200-64FF window. Its generated
instruction/address structure is checked without assembling the engine again
or running a CPU model. The generated reference ASM is retained with the build.
The public unrendered recovery template still refuses; patch and seal the
engine before wrapping it, not the outer wrapper alone.

## Per-run plan

The host patches the 256-byte zero-filled plan at 3000, then puts the little
endian FNV-1a32 of RAM 2000-3FFB at 3FFC-3FFF. The hash covers code, strings,
padding and the rendered plan, excluding only its four-byte hash field.

| Plan offset | Bytes | Meaning |
| --- | ---: | --- |
| 00 | 4 | ASCII NFM1 |
| 04 | 1 | Format 01 |
| 05 | 1 | Operation count, 1-3 |
| 06 | 2 | Reserved zero |
| 08 | 16 | Initial whole-bank FNV32 values for B0, B1, B2, B3, little endian |
| 18 | 8 | Reserved zero |
| 20 | 16 each | Operation rows |

Each row contains sector high byte at +0, commit flag at +1, zero bytes at
+2/+3, whole-B3 preimage FNV at +4, incoming uncommitted payload FNV at +8,
and whole-B3 final postimage FNV at +12. Only these orders are admitted:

- Count 1: F, commit flag 0.
- Count 2: D then C, each commit flag 1. This supports an already identical F.
- Count 3: F, D, C; F flag 0 and journals flag 1.

Every declared operation performs one actual erase, including a blank sector.
The host must count/reserve that erase. The engine cannot write B0/B1/B2 or
any B3 sector except F, D and C. It neither copies WDC to B0 nor decides whether
an occupied C/D sector is safe to provision. Existing SNBT history requires a
separate admitted history-preserving transaction; it must not be reset by this
factory provisioner.

For a commit row, incoming payload byte FF must be FF. The engine verifies the
entire uncommitted 4096-byte sector, programs sector+00FF to 00 last, compares
the entire final sector again, then checks the whole-B3 final postimage FNV.
The planner supplies the SNBT page/header/wear CRCs and final committed hash.
The engine validates exact expected bytes, not the semantic content of a
user-modified journal. There is no embedded F payload; the planner must bind
the supplied F transfer to the released 4096-byte file.

## Console transfer and completion

The engine prints its identity, preservation scope, RAM/plan result, complete
source-bank check, chip check and confirmation prompt. Reply exactly `Y` CR.
An already queued LF is consumed. Ctrl-C at this prompt cancels without a
flash erase/program. After execution starts, the engine never calls WDC again.

For each operation, wait for this exact line before sending its binary bytes:

```text
SEND 4096 BYTES FOR B3:F
```

The destination character is F, D or C, and the line ends CR LF. Send exactly
4096 bytes, paced by the host (the existing transport uses 64-byte chunks with
10ms gaps). No added line endings. Incoming bytes are literal payload data.
The engine checks the transfer FNV and full current B3 preimage before erasing.
It reports erase, blank verification, programming, sector comparison,
journal commit and complete-bank verification as separate phases.

On completion it verifies B0/B1/B2 are unchanged and B3 matches the final row,
then emits:

```text
MIGRATION VERIFIED; PRESS PHYSICAL RESET
```

It halts in RAM instead of automatically jumping through possibly damaged ROM.
Only a later physical reset/REC check establishes boot acceptance. Failure
prints its phase/cause and halts with no automatic retry or reset. TX failure
halts without pretending a message was delivered. Keep the log and escrow;
the host must inspect actual flash before resuming. Owner RAM restoration is
a distinct host/recovery step and is not performed by this engine.

## Fresh public capture: separate read-only NFA1 helper

`nf-archive.asm` supplies a separate read-only RAM program, using the same
source-closed FNV and FT245 functions. Current built artifacts are under
`build/archive-r1-repair1/`; the migration engine is under `build/r1/`.
Build it only when source changes require it, using a fresh output directory,
for example `python build_archive.py --out build/changed-archive`. It has no flash command,
chip-ID command, write through a flash pointer, or SPI/RTC/EEPROM/EDU access.
Its only I/O writes are FT245 controls/data/directions and the bank PCR.

Before uploading it, the host must escrow owner RAM/ZP through the still
running WDC debugger. Upload/read back `archive.bin` at 2000-3FFF and execute
2000 for 65C02 or 2010 for 816. The image is sealed with its own FNV at 3FFC.
An optional `archive-recovery.bin` wrapper supports raw L entry 0200.

Wait for `ARCHIVER READY; G then Enter> ` and send exactly G CR. The helper
streams these eight headers in order, each terminated CR LF:

```text
ARCHIVE B0 PASS 1
ARCHIVE B1 PASS 1
ARCHIVE B2 PASS 1
ARCHIVE B3 PASS 1
ARCHIVE B0 PASS 2
ARCHIVE B1 PASS 2
ARCHIVE B2 PASS 2
ARCHIVE B3 PASS 2
```

Each header is immediately followed by exactly 32768 raw bytes and then four
little-endian FNV-1a32 bytes. The helper computes that trailer as it transmits
each flash byte. The host must compare both complete bank passes byte for
byte, verify every trailer, and keep the resulting vendor/owner bytes private.
The helper restores B3 after every bank, and finally emits
`ARCHIVE COMPLETE; PRESS PHYSICAL RESET` CR LF and halts in RAM.

The operator's physical reset re-enters vendor firmware when starting from
WDC. Reconnect/read back its identity and compare current B3 with the archive
before rendering/loading the admitted migration image. This requires a
physical reset because the helper deliberately does not fake a return into
the vendor's native/emulation context. Vendor startup behavior is a separate
qualification: the helper itself issues no SPI writes, but cannot promise
that vendor firmware will not initialize peripherals on reset. The archiver,
migrator and their reset paths have not been device- or CPU-qualified here.
