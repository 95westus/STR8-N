# ASM source FLASH increment

Installed and accepted on2512/65C02, November2,2026. RAM-first guards,
real source SAVE/LOAD, installed execution, corruption refusal and final
preservation passed. F, MON A/B, E and published downloads are unchanged.
The816 developer path and extracted developer kit remain separate.

## Intended operator workflow

Inside `R ASM`:

```text
SAVE FLASH DEMO01
Append source B0:9000 sectors 01; type YES> YES
NEW
LOAD FLASH DEMO01
LIST
ASM
```

The displayed address depends on the current allocation scan. Only whole
erased sectors within B0:8000–DFFF can be proposed, and the exact starting
address and sector count must be approved before programming. Erased space
alone is not allocation permission. Any response other than exact `YES`
cancels. A save never erases, replaces an existing name, or touches a different
bank. Use a new name for another revision. Source saving stages a capsule
over the output buffer; assemble again before running output.

`LOAD FLASH name` validates the storage header and complete source capsule
before copying into the live editor. Dirty loads retain the existing explicit
discard confirmation. `SAVE/LOAD SRAM name` continues to use formatted PROGRAM
storage; WORKSPACE is never allocated by these commands.

The current2512 layout has one free source sector, B0:9. It holds one source
record containing up to4056 packed-source bytes. Another record or a larger
two-sector source needs a separately admitted extent; there is no implicit
reclaim. Use PROGRAM storage for additional revisions. SF/1 source records
are loaded inside ASM, not launched as applications or runnable programs.

## Format and pairing

SF/1 is a32-byte metadata header carrying an AS/1 source capsule. Metadata CRC
is calculated with the commit byte FF. Header and payload bytes are programmed
only over an FF preimage and individually verified. The final FF-to-3F commit
publishes the record after all data is verified. The source capsule supplies
its own source-length and CRC checks. A record occupies one or two whole4KiB
sectors; source is bounded by the current6KiB editor capacity. There is no
automatic cleanup of torn/corrupt/duplicate records or implicit owner erase.

The private FS/1 provider occupies unused padding at B0:D800–DFFF within the
existing DBG AP/02 image. It loads into RAM7000–77FF. The source helper checks
its profile, full-block CRC and paired callback addresses before entering it.
Switching back to SRAM source operations reloads the admitted PROGRAM g3
provider at6B00–77FF. The selected flash allocation remains16KiB, and the full
selected preview profile remains104KiB. There is no new Foundation ABI.

| Result | Meaning |
| --- | --- |
| `$42` | Source name not found |
| `$50` | Duplicate/reserved source name |
| `$51` | No suitable contiguous erased extent |
| `$52` | Invalid SF/1 header or conflicting source records |
| `$53` | Programming/preimage/readback failure; no automatic retry |
| `$54` | Proposed allocation cancelled |
| `$80` / `$81` | PROGRAM / FLASH provider absent, invalid or mismatched |
| `Invalid source image.` | AS/1 source format, size or CRC rejected |

## RAM-first incident and recovery

The first read-only candidate lost the page count because the pinned bank
selector uses X. Its RAM copy ran beyond the intended overlay and hung before
the save prompt. No flash-programming command was issued; I/O preservation
was inspected rather than assumed. The owner pressed one physical RESET.

Recovery independently verified all four flash banks, golden F and all boot/
wear/settings bytes; restored owner RAM0200–66FF, ZP00–DF, public BRK/HOLD
hooks and the full6B00–77FF provider cache. A complete131072-byte SPI read
matched the preserved baseline exactly (zero differing bytes). Native TIME
reported the expected flags28, trim0C and control80. The CPU reset was recorded
without changing RTC time, trim, flags, data-collection baselines or schedule.

The corrected candidate saves and reloads the bound across SELECT. It also
checks current source-size bounds and explicit callback pairing. The corrected
RAM trial passed provider CRC refusal, AS/1/SF/1 size guards, exact-sector
NO cancellation, dirty-load refusal, FLASH/PROGRAM overlay switching and exact
flash/owner/cache preservation. The subsequent reviewed five-erase execution
passed real SAVE/LOAD in RAM and through installed R ASM, duplicate/full and
dirty-load guards, two real CRC/header corruption refusals and DBG step/HOLD.
The test record was removed by restoring B0:9 to all FF. Four app upgrades
and that cleanup used five wear appends; all25 old journal rows remain exact
on chip, with sequence1187 and30 valid rows. Owner RAM/ZP/full provider cache
were restored. COM4 is released and RTC host admission remains valid.

Workspace receipts:

Detailed qualification receipts are retained privately and omitted from this export.

Accepted build: `BUILD/asm-flash-source-g2-r4/manifest.json`. Earlier build/failed
trial artifacts remain historical. The ASM and DBG cores and the admitted
decompressor are reused; only the source helper/provider and ASM wrapper are
linked. No CPU simulation, F/MON rebuild or other-board developer trial is
part of this increment.
