# Beta33 intended freeze candidate: standalone on-board ASM

The owner requested standalone ASM from the earlier branch on the beta32
baseline, making beta33 the intended 2.0 freeze candidate. This is ASM 0.4,
not ASM-F2, HIMON or the proposed v2.1 runtime/linker. Work is isolated on
`codex/v2-beta33-asm`, based at the completed beta32/support checkpoint
`e97d785`; v2.1 source and tests are excluded from the candidate.

ASM source, documentation and tests were recovered selectively from saved
checkpoint `5313633`, without applying the rest of that stash or changing
it. The parser, editor and instruction encoder are retained; ASM 0.4 relocates
its private buffers to provide a contiguous user-code window. The image
header now uses its linked entry symbol, allowing placement at E000 instead
of the earlier 9000. A beta32-owned public include replaces the old build
path. The named-app host ABI, RAM console and monitor HOLD remain unchanged.

The offline reference uses B3 monitor B generation 45 (`0000002D`), beta28 A
as the retained fallback, and ASM in B1:E-F. This placement fits the erased
E/F sectors found in 2205's verified beta32 backup, preserving its older
MAINT and CLOCK records. It does not authorize treating another board's
sectors as erased; a live installation must bind to fresh backup preimages.

## Usage and memory

Launch with `ASM`; `APPS` lists `ASM installed B1:E000 LEN 1864`.
At `ASM>`, type numbered source or use PASTE, then ASM, DUMP and QUIT.
`G 0200` executes the generated RAM program. The
[worked examples](../examples/beta33/README.md) exercise public PUTC/HEX/HOLD,
a RAM variable and monitor Store/Table/Restore of the generated program.

| Item | Usage |
|---|---|
| ASM flash image | 6,244 bytes, B1:E000-F863, entry E010 |
| ASM flash allocation | Two 4 KiB sectors, E and F; 1,948 bytes outside the image, including the vector tail |
| Exception vectors | In the same F sector, outside ASM's image; no separate third sector |
| Named-app descriptor | 32 bytes in an existing B3:E table slot; existing 2 KiB extension seal renewed |
| Native utility bundle | 22,062 / 22,528 bytes; 466 bytes free; +50 bytes over beta32 |
| Monitor | 3,967 / 3,968 bytes; banner/generation updated, no code growth |
| ASM source | $3300-$4EFF, 7,168 bytes of packed source |
| Generated output | $0200-$32FF, up to 12,544 bytes |
| Symbols | $4F00-$62FF, up to 256 records |
| State and line buffers | $6300-$64FF, 512 bytes |
| Exclusive active workspace | $0200-$64FF, 25,344 bytes, plus ZP $00-$3F and stack |
| Permanent RAM reservation increase | Zero; application/services boundary unchanged |

The named-app launcher checks descriptor/header CRC, workspace bounds,
exception vectors and complete image CRC before changing banks. ASM remains
in flash; only source, output, symbols, variables and buffers occupy its RAM
workspace. It emits W65C02 instructions on a 65C02 host or a compatible 816
emulation host. Native 816 assembly/execution is not added by this candidate.

The added 50 bytes tighten BATCH's existing A-command allowlist to the exact
APPS word. Previously ASM could pass that character-based allowlist even
though its interactive reader cannot consume queued commands. ASM in a BATCH
now stops before launch; APPS and the existing registered utility providers
retain their behavior. No new BATCH provider or public ABI is introduced.

The default origin and physical output both start at $0200. ASM -> QUIT ->
G 0200 -> S/T/R requires no MAINT copy. Other logical origins remain supported
through staged output/S19 loading. The layout boundary test fills all 12,544
code bytes, then rejects a one-byte overflow without touching source or services.

## Qualification and release state

The build and its original receipts are offline qualification. Complete instruction, editor, expression, capacity,
error and generated-program tests run through the real linked machine code.
Integration covers source -> RAM -> public ABI execution -> flash S/T/R,
corrupt descriptor/header/image/vector refusal, EDU ON, native utilities and
BATCH. An independent rebuild compares the sealed artifacts and reference
bank images. Receipts are under `BUILD/v2-beta33-candidate`.

Fixed B3:F, resident RTC/SPI services, CLOCK 1.9, the B3:E800-EFFF service
kernel, and B2 assets after the native bundle retain beta32 bytes. Building
does not access a serial port, flash a board, or create a live installer.
The separately prepared, backup-bound installation on 2512 subsequently
passed full flash/retained-data verification, the contiguous-window test,
on-board assembly/execution/S/T/R, native utility/BATCH checks and both
monitor boots. Original application RAM was restored and verified; COM4 is
released. See the [2512 hardware record](STR8N_V2_BETA33_2512_2026-10-16.md).
The sealed model receipts remain unchanged; hardware proof is separate.

The owner accepted the combined completed soak evidence and requested a
complete stop. No soak worker remained running; the STOP marker and verified
RAM restoration remain intact. The hourly reminder was disabled. Historical
transport failure and actual elapsed durations remain documented; acceptance
does not turn the interrupted enhanced run into a completed 24-hour run.

Public migration-path qualification and the other stable-release gates remain
separate from this ASM addition and the accepted soak evidence. Beta33 is an
intended freeze candidate, not a declaration of stable 2.0.
