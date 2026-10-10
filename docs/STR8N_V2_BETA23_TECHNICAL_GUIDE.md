# STR8-N beta23 technical guide

Revision: 2026-10-10. Target: **2.0b23, generation 32**, with CLOCK 1.6,
MAINT 1.8, EDU 1.2, SRAM 1.2 and WORK 1.2. This guide describes the frozen
qualified development image. The published release remains beta4.

Functional, preservation and controlled recovery checks passed on 2512, 2205,
2604 and 2609. Extended soak/retention validation is limited to **2604 and 2609**
and continues with bounded exercises and battery-backed power-off intervals.
Its 48–72-hour powered-on acceptance gate remains open. Extended validation
on those two does not imply extended soak on 2512/2205. See the
[current drift/soak status](STR8N_V2_BETA23_DRIFT_SOAK_2026-10-10.md).
Final RC packaging is pending.

All addresses below are hexadecimal CPU bank-$00 addresses unless identified
as an external SPI address. `LE16`, `LE24` and `LE32` mean little-endian integers.
The external SRAM is not part of the CPU address space.

## Contents

- [Boot, recovery and memory ownership](#boot-recovery-and-memory-ownership)
- [Essential monitor ABI](#essential-monitor-abi)
- [Interrupt contract](#interrupt-contract)
- [Optional-service discovery](#optional-service-discovery)
- [Time ABI](#time-abi)
- [Shared I2C ABI](#shared-i2c-abi)
- [Resident SPI and SRAM ABI](#resident-spi-and-sram-abi)
- [WORK allocation ABI](#work-allocation-abi)
- [Named SRAM storage and flash records](#named-sram-storage-and-flash-records)
- [Runnable 65C02 examples](#runnable-65c02-examples)
- [Integration checklist and evidence](#integration-checklist-and-evidence)

## Boot, recovery and memory ownership

Cold reset initializes RAM console/vector services, checks monitor slots A/B,
and loads the saved configuration. A and B are validated monitor images in
B3 sectors A and B. The fixed F core supplies recovery independently of either
slot. Choose A/B during startup or Enter for the saved default. `S` enters
`FIXED F RECOVERY` at `REC>`; `W` reports wear, and `A`/`B` validates and launches
that slot. Recovery updates are separate write operations, not part of W/A/B.

`J3` is the monitor's cold restart. Application `RESET` transfers through the
reset ABI. `HOLD` returns to the resident monitor, normalizes the visible bank
and gives a quiet prompt; it does not perform cold initialization. `M1` loads
the maintenance utility, so it can overwrite its application-RAM footprint.
After a successful firmware upload the installer is halted and requires the
physical main-board RESET. On 2609, S2/RESB is RESET and S1/NMIB is NMI.

EDU is a saved **per-board, reset-latched** setting. `R EDU`, `OFF`/`ON`, single
`Y`, `Q`, then `J3` activates a change. Save prints `Saved; RESET required.`;
while active and saved modes differ, status prints `RESET required: OFF` or
`ON`. Ordinary return does not activate the saved mode. Cancellation and an
unchanged save do not create a new reset requirement.

| CPU range | Ownership |
|---|---|
| $0000–$00FF | Zero page; monitor/utility scratch includes the upper zero page; reserve per called interface |
| $0100–$01FF | CPU stack |
| $0200–$64FF | Application RAM with EDU ON |
| $6500–$66FF | Optional-service reservation with EDU ON; reclaimed application RAM with active OFF |
| $6700–$77FF | Monitor staging/journal workspace; temporary SRAM-manager lease |
| $7800–$7BFF | Monitor worker and related private staging/hooks |
| $7C00–$7DFF | Monitor lines, state, configuration and discovery |
| $7E00–$7EFF | RAM vectors and public RAM ABI |
| $7F00–$7FFF | Board I/O |
| $8000–$FFFF | Selected flash bank B0–B3 |

Use the validated discovery RAM limit, not the historical `$66FF` constant.
With active OFF, optional signatures/request blocks may contain application
bytes: do not inspect or write them before capability discovery. An EDU mounted
on an OFF board remains electrically connected; OFF simulates the standalone
firmware profile, not physical removal. Hardware failure does not release an
already active service reservation.

WORK owns $5000–$648A while loaded. MAINT 1.8 owns $2000–$44E3 while loaded.
The preserving named `R SRAM` loader leaves $0200–$64FF intact; ordinary S19
or numeric-address loading of its transport does not provide that guarantee.
Private staging is not extra public application RAM.

## Essential monitor ABI

For returning calls, use `JSR`; for RESET/HOLD, use `JMP` because they do not
return to the application. Check `52 41 01 0D` (`RA`, format 1, 13 entries)
at **$7E60–$7E63** before calling the RAM table. These entries work with any
flash bank visible. Direct ROM facade entries require the resident bank visible.

Monitor services require foreground execution, IRQ disabled and decimal clear.
On the 816 use **E=1, D=0, DBR=0, PBR=0**. Native interrupt-vector support does
not advertise native-mode monitor/service calls. Preserve any application
registers/flags needed after a console call rather than relying on unspecified
effects. The optional bus gateway has a separate preservation contract below.

| Operation | RAM entry | Resident ROM facade | Input/result |
|---|---|---|---|
| RESET | $7E64 | $F004 | Cold reset; does not return |
| HOLD | $7E67 | $F007 | Monitor return; does not return |
| CON_INIT | $7E6A | $F00A | Reinitialize console; changes console state |
| PUTC | $7E6D | $F00D | A = character; console cancellation can suppress output |
| GETC | $7E70 | $F010 | Blocking input; A = byte, including $03 for cancellation |
| RAW_POLL | $7E73 | $F013 | C=1/A=byte if available; C=0 if empty; bypasses queued GETC input |
| CHECK_CANCEL | $7E76 | $F016 | C=1 when cancellation is pending; polls bounded input |
| RX_RESET | $7E79 | $F019 | Reset receive/queue state |
| HEX_OUT | $7E7C | $F01F | Print A as two hexadecimal digits |
| NEWLINE | $7E7F | $F022 | Emit CR/LF |
| HEX_NIBBLE | $7E82 | $F025 | ASCII hex in A → value 0–15/C=1; invalid C=0 |
| CAPS_QUERY | $7E85 | $F028 | A=format 1, X=flags $17, Y=length 4, C=1 |
| BOARD_QUERY | $7E88 | $F02B | A=format 1, X=CPU, Y=board/console flags, C=1 |

CAPS bits: $01 65C02 calls; $02 816 emulation calls; $04 native vectors;
$08 native service calls (**not set**); $10 bank-independent RAM calls.
BOARD CPU codes are $02 (65C02) and $16 (65C816). Board flags defined by the
header are $01 FT245, $02 ACIA, $04 timed ACIA, $08 selected ACIA and $10
FT245 present. Current USB behavior is qualified; ACIA receive on 2512/2205
remains deferred. A defined flag is not a hardware-acceptance claim.

The ROM signature begins at $F000. ROM $F01C is a reserved line-policy slot;
line editing is not a bank-independent public application service. The RAM
configuration copy at $7D80 is not a persistent flash pocket. Use supported
configuration commands to save changes; do not patch private state or workers.

Source contract: [public symbols](../src/v2-beta4/str8n-v2-public.inc),
[RAM dispatch](../src/v2-beta4/str8n-v2-vectors.asm).

## Interrupt contract

Pointers below contain **16-bit bank-$00 handler addresses**. Preserve old
pointers and restore them when the application finishes. A handler owns source
acknowledgement, register preservation, stack/frame handling and `RTI`.

| Emulation pointer | Address | Native pointer | Address |
|---|---|---|---|
| NMI | $7E00 | COP | $7E10 |
| BRK | $7E02 | BRK | $7E12 |
| IRQ | $7E04 | ABORT | $7E14 |
| COP | $7E06 | NMI | $7E16 |
| ABORT | $7E08 | IRQ | $7E18 |

The emulation dispatcher distinguishes BRK from IRQ using the stacked B flag
and restores its temporary A/X before entering the selected handler. Native
entries use indirect JMP and leave widths, registers and the native hardware
frame to the handler. Native default RTI is not interrupt-source acknowledgement.

Publish a native NMI pointer while E=1: increment the NMI gate at **$00F4**,
write both pointer bytes, then clear the gate. SEI alone does not mask NMI.
Keep native handlers' width/direct-page/data-bank requirements explicit and
return to the qualified emulation profile before monitor calls. IRQ/NMI/native
callers must not invoke RTC/I2C/SPI/SRAM/WORK services. Cross-bank gateway calls
reject unsupported flash NMI handlers; install a suitable RAM handler instead.
Do not take a private flash worker or streaming-hook address as an ABI.

## Optional-service discovery

**$7D04–$7D0B** is the eight-byte `SV` descriptor:

| Offset | Meaning |
|---|---|
| 0–1 | `SV` ($53,$56) |
| 2 | Format 1 |
| 3 | Capabilities: $01 RTC, $02 I2C, $04 SPI, $08 SRAM |
| 4–5 | Gateway base LE16; $6500 for this version |
| 6–7 | Inclusive application-RAM ceiling LE16 |

Typical ON bytes: `53 56 01 0F 00 65 FF 64`. OFF bytes:
`53 56 01 00 00 00 FF 66`. Capabilities certify validated software, not attached
devices, valid time, valid storage or battery health. Partial availability is
possible; require only the capability being used, then its versioned signature.
Rediscover after RESET or monitor reentry. Check returned A/Carry even after
successful discovery: backing-code validation or device operations may fail.

| Service | Signature | Public entries |
|---|---|---|
| RTC | `RG`,1,4 at $6500 | $6504/$6507/$650A/$650D |
| I2C | `I2`,1,1 at $6510 | $6514 |
| SPI | `SP`,1,1 at $6646 | $664A |
| SRAM | `SM`,1,1 at $66A2 | $66A6 |

Resident RTC/I2C/SPI/SRAM calls return **A=status, C=1 for success**. They preserve
stack, caller PCR/bank selection, I and decimal state; X/Y/N/Z/V are unspecified.
They are foreground, cooperatively owned operations. Reentry returns busy
without overwriting the active operation's request/results. Direct VIA/private
RAM writes by another program are outside this ownership contract.

## Time ABI

Include [kernel-rtc-api.inc](../tools/v2-rtc/kernel-rtc-api.inc). The old standalone
RAM prototype at $3000/$3F00 is not the installed beta23 interface.

| Entry | Purpose |
|---|---|
| $6504 RTC_READ | Read a stable, validated decoded UTC calendar |
| $6507 RTC_STATUS | Read raw/status information, including stopped/invalid clock state |
| $650A RTC_SET | Explicit validated calendar request; preserves outage evidence first |
| $650D RTC_ACK_POWER | Capture outage evidence, then explicitly acknowledge hardware latch |

| Address | Bytes | Result/request |
|---|---:|---|
| $66C0 | 1 | Result status |
| $66C1 | 1 | Flags |
| $66C2–$66C9 | 8 | Decoded calendar |
| $66CB–$66D3 | 9 | Raw RTC registers $00–$08 |
| $66D4–$66DB | 8 | Latest outage registers $18–$1F |
| $66DC | 1 | Captured-outage evidence available |
| $66E0–$66E7 | 8 | SET calendar request |
| $66E9–$66EA | 2 | Consumed intent key: SET `ST` ($53,$54); ACK `PA` ($50,$41) |
| $66F0–$66F7 | 8 | Captured outage retained in RAM across service calls |

Decoded/request bytes: year LE16, month, day, weekday, hour, minute, second.
These are binary, not BCD or ASCII. Years are 2000–2099; weekday is 1=Monday
through 7=Sunday. RTC convention is UTC. Local display never changes RTC UTC.
Copy a successful calendar/result to application-owned RAM before another
service or monitor operation. Captured RAM evidence is lost on RESET/replacement;
it is distinct from durable EEPROM history.

Flag masks: $01 oscillator-start bit, $02 running, $04 valid calendar,
$08 power-fail latched, $10 backup enabled, $20 continuity/battery condition
unknown. Backup enabled and a valid calendar do not certify remaining battery
life. Outage registers have minute precision and no year; do not infer a
precise outage duration/year from them alone.

| Status | Meaning |
|---|---|
| $00 | Success |
| $01 | Bus busy |
| $02 | NACK |
| $03 | Timeout |
| $04 | Stopped/invalid calendar for READ |
| $05 | Enabled alarm blocks SET |
| $06 | Intent/policy denied |
| $07 | Unstable/unverified operation |
| $08 | In use |
| $80/$81/$82 | Software unavailable / integrity failure / unsupported NMI handler |

`RTC_ACK_POWER` is not the durable journal's save-and-ack transaction. Ordinary
application time readers should use READ/STATUS only. CLOCK/boot's managed
history path verifies a committed event before automatic acknowledgement.
History uses four 32-byte ordinary EEPROM slots at $00–$7F, leaving factory
identity/status outside the allocation. A full ring replaces the oldest slot.
Foreign layout is refused, not automatically formatted. Current 2604 history
reports $90 and retains its latch; its clock/SRAM retention passed.

EUI/binding, history administration, trim and fixed-offset internals use
version-paired code and scratch; their private ROM addresses are not public
RTC jump-table entries. Use CLOCK's documented console operations. OFFSET,
SET and TRIM apply immediately after verification and require exact `YES` in
CLOCK; none requests reset. Normal trim is signed −127…+127, canonical zero;
coarse/alarm/output ownership and transfer verification are guarded. OFFSET is
−12:00…+14:00 in minute steps, fixed without automatic DST. TZ records share
the finite append-only identity tail at B3:$9C00–$9FFF; full space refuses
without automatic erase. Keep UTC/trim unchanged during a drift campaign.

A complete read-only assembly example with discovery and copied UTC is
[time-example.asm](../tools/v2-rtc/time-example.asm). Build/load instructions
and drift policy are linked from [RTC direction](STR8N_V2_RTC_DIRECTION.md).

## Shared I2C ABI

Call $6514 after SV bit $02 and `I2`,1,1 discovery. Request/result occupies
**$6650–$665F**, shared with SPI/SRAM; finish and copy results before preparing
another request. Buffers must fit entirely in $0200–$64FF; zero counts ignore
their pointers. At least one direction must be nonempty.

| Offset | Meaning |
|---|---|
| 0 | Unshifted 7-bit address $08–$77 |
| 1 | Bit 0 repeated START; other bits zero |
| 2–3 / 4 | Write buffer LE16 / count 0–64 |
| 5–6 / 7 | Read buffer LE16 / count 0–64 |
| 8 | Status |
| 9 / 10 | Acknowledged write payload / stored read bytes |
| 11 | Phase: 0 setup, 1 write address, 2 write data, 3 read address, 4 read data, 5 STOP |

Combined flag 1 uses repeated START; flag 0 uses STOP/new START. Overlapping
buffers are permitted because transmit completes before receive storage.
The managed $6F RTC permits only a one-byte register pointer, repeated START
and reads within $00–$1F. Public EEPROM $57 transactions are denied. Other
devices can use normal transfers; physical external peripherals remain outside
the current qualification matrix.

Statuses: $00 completed; $01 bus not idle; $02 NACK; $03 clock/STOP timeout;
$06 policy denied; $08 busy; $09 invalid request; $80/$81/$82 as above.
Partial counts describe effects, not rollback or device-internal completion.
There are no automatic retries, scans or bus-clear pulses. Clock-stretch waits
are bounded at 255 line polls, not a fixed millisecond timeout. See
[full I2C contract](../tools/v2-rtc/I2C_API.md).

## Resident SPI and SRAM ABI

Call $664A for SPI or $66A6 for SRAM after the corresponding SV/signature checks.
Both share the $6650–$665F block. Counts are bounded to 64 payload bytes; CPU
buffers must be wholly within $0200–$64FF.

| Offset | SPI | SRAM |
|---|---|---|
| 0 | Profile 1 mikroBUS; managed profile 0 denied | Op 0 PROBE, 1 READ, 2 WRITE |
| 1 | Bit 0 duplex; otherwise zero | Flags zero |
| 2–4 | TX pointer LE16, TX count | External address LE24; high byte 0 or 1 |
| 5–7 | RX pointer LE16, RX count | CPU buffer LE16, payload count |
| 8 | Status | Status |
| 9 | TX bytes clocked | Payload bytes completed |
| 10 | RX bytes stored | Diagnostic transfer count |
| 11 | Phase: 0 refusal, 3 completed cleanup | Capacity LE24 starts here after successful PROBE |
| 12 | RX filler | Capacity middle byte after PROBE |
| 13 | Mode zero | Capacity high byte after PROBE |
| 14 | Reserved zero | PROBE health $81: usable, retention/battery unknown |
| 15 | Reserved zero | Reserved zero |

SPI transmits then receives under continuous select. Duplex requires equal,
nonzero counts and identical or disjoint buffers; partial overlap is refused.
Successful SPI transport does not establish device presence or acknowledgement.
SRAM address+count must not wrap or exceed $020000. READ/WRITE counts are 1–64;
PROBE uses zero count and reports 128 KiB nominal capacity. PROBE temporarily
changes and restores/verifies reserved byte $1FFFF: it is not a read-only
retention inventory. The driver temporarily selects sequential mode and
restores/verifies the previous SRAM mode.

Public raw managed-SRAM SPI and public SRAM WRITE are denied from cold boot.
Use WORK for checked workspace writes and the named manager for saved images.
Do not enable private write flags. A completed write would not itself prove
readback; managed publication verifies data before committing metadata.

| Status | Meaning |
|---|---|
| $00 | Completed |
| $01 | Active select, pending CB flag or incompatible handshake/latching state |
| $06 | Managed raw SPI/WRITE denied |
| $07 | Mode/probe/restoration unverified |
| $08 | In use; active request/results untouched |
| $09 | Invalid profile/mode/flags/counts/buffers/overlap/address |
| $80/$81/$82 | Unavailable / integrity failure / unsupported NMI handler |

Unrelated driven VIA bits, DDR and caller PCR are preserved; selects are
deasserted before restoration. The service does not discard pending CB evidence
or alter handshake ownership to force a transfer. Interrupt-signaling external
SPI devices, native callers and concurrent bus owners require later work.
See [SPI contract](../tools/v2-spi/SPI_API.md) and
[symbols](../tools/v2-spi/spi-api.inc).

### Read-only SRAM request example

After SV bit $08, gateway/RAM-limit and `SM`,1,1 checks, the following complete
16-byte block at $6650 requests 16 bytes from external $10000 into CPU $2300:

```text
01 00 00 00 01 00 23 10 00 00 00 00 00 00 00 00
```

Execute `JSR $66A6`, require C=1 and A=$00, and verify completed payload count
at $6659 is $10. Data is at $2300–$230F. On failure, inspect the returned A and
copied diagnostics; do not interpret the buffer as a valid object. This READ
does not mount, format, claim or PROBE storage. Save result bytes in ordinary
application RAM before another shared request. A request block alone is not an
S19 application and must not be executed with G.

## WORK allocation ABI

Load WORK 1.2 before the application, for example `R 2 WORK L`, then select B3.
It occupies **$5000–$648A**. Check `WK`,1,2 at $5006–$5009, then `JSR $5003`
with **A=request address low, X=high**. The 32-byte request/result must be in
$0200–$64FF outside the library. Reserve its range; relocation is not automatic.

Return A=status and C=1 only for success. X/Y, zero page $D0–$D5 and library
scratch are clobbered. IRQ is disabled and decimal clear on return; stack and
bank selection are preserved. These are different flag rules from the resident
gateway. Keep the library, request and buffers stable throughout the call.

| Offset | Bytes | Meaning |
|---|---:|---|
| 0 | 1 | 0 query, 1 claim, 2 release, 3 read, 4 verified write, 5 resize, 6 format, 7 upgrade, 8 repair |
| 1 | 1 | Flags zero |
| 2 | 2 | Nonzero owner LE16 for claim/handle operations |
| 4 | 8 | Handle: slot, zero, epoch LE32, ticket LE16 |
| 12 | 3 | Relative READ/WRITE offset; QUERY returns workspace boundary |
| 15 | 1 | READ/WRITE count 1–64 |
| 16 | 2 | CPU buffer LE16 |
| 18 | 3 | CLAIM length; QUERY returns workspace capacity |
| 21 | 1 | RESIZE units 1–4 of 16 KiB; QUERY returns current units |
| 22–23 | 2 | QUERY legacy/secondary flags; transfer completion/diagnostics for READ/WRITE |
| 24 | 8 | Administrative key `RESIZE!!`, `FORMAT!!`, `UPGRADE!`, `REPAIR!!` |

CLAIM returns the complete handle and zero relative offset. Keep owner and all
eight handle bytes. Placement is 256-byte aligned, length exact; four live slots
and contiguous-space requirements can limit allocation. Allocation does not
clear existing bytes. Reads/writes enforce owner, epoch, ticket, claim bounds,
CPU buffer ownership and library/request overlap rules. WRITE stages up to 64
bytes and verifies readback. Errors may leave partial effects; inspect status
and diagnostics rather than interpreting a nonzero count as success.

| Program allocation | Saved payload capacity | Workspace capacity |
|---:|---:|---:|
| 16 KiB | 14,336 bytes | 114,656 bytes |
| 32 KiB | 30,720 bytes | 98,272 bytes |
| 48 KiB | 47,104 bytes | 81,888 bytes |
| 64 KiB | 63,488 bytes | 65,504 bytes |

The first 2,048 bytes are management. Resize moves no data and refuses live
claims or saved extents that conflict with the proposed boundary. Old saved
versions occupy extents until explicit reclaim. Query alone does not initialize
a session. HOLD/library reload preserve live handles; cold RESET clears private
session latch $66AF, and the next handle operation establishes a new epoch,
making old handles stale. Discard handles after RESET or FORMAT. Counters refuse
exhaustion rather than wrap.

Additional statuses: $49 administration/upgrade required; $4A resize/workspace
conflict; $4B stale or wrong-owner handle. $40–$48 retain storage meanings below;
resident transfer failures retain their underlying status. Console commands are
`?`, `P 16/32/48/64`, `U`, `V`, `F`, `Q`; console confirmation differs from the
eight-byte API keys. See [WORK contract and retained layouts](../tools/v2-spi/WORKSPACE_API.md).

### Minimal WORK call sequence

Place a 32-byte, initially zeroed block at a caller-owned address such as $2400.
For a 64-byte CLAIM, set byte 0=$01, owner at 2–3=`01 00`, and length at 18–20
to `40 00 00`. Call with `LDA #$00`, `LDX #$24`, `JSR $5003`; check A/Carry and
copy the returned handle at 4–11 into application state.

For WRITE, retain that owner/handle, set operation $04, relative offset 12–14
to zero, count 15=$40 and buffer 16–17=`00 25` for $2500–$253F. Initialize those
payload bytes before calling. For READ use operation $03 with the same bounds.
For RELEASE use operation $02 and the same owner/handle. A failed call requires
inspection; an unconfirmed claim/write can have effects. Do not zero the handle
before checking whether it must be released. This sequence does not FORMAT or
RESIZE and requires a valid allocation with suitable free claim space.

## Named SRAM storage and flash records

At `B3>`, `R SRAM` enters the preserving manager; its console explicitly selects
SPI SRAM. `S name start end entry`, `R name`, `G name`, `T`, `D name`, `C` and
`Q` provide save, restore, run, table, tombstone delete, reclaim and return.
Names are 1–16 uppercase letters/digits/underscore/hyphen. Entry 0000 is
restore-only; a run entry must lie within the saved image. SPI SRAM is storage,
not executable CPU memory: G validates and copies before jumping to CPU RAM.

There are eight 64-byte directory slots counting versions and tombstones.
Replacement needs a free slot and fresh contiguous 256-byte pages; old versions
remain until reclaim. Payload and metadata are verified before final $A5 commit.
Latest valid sequence wins. Reclaim does not move live payloads. Restore verifies
the whole payload before copying and again during copy; partial-copy failure
never executes the entry, but may already have changed destination RAM.

| External range | Current management/storage ownership |
|---|---|
| $00000–$0003F | Primary SS v2 layout |
| $00040–$0023F | Eight SP v1 directory records |
| $00240–$0027F | Secondary layout |
| $00280–$002FF | Two WS session packets |
| $00300–$0037F | Four WC claim packets |
| $00380–$007FF | Reserved management |
| $00800–(program boundary−1) | Saved payload pages |
| program boundary–$1FFDF | WORK workspace |
| $1FFE0–$1FFFF | Resident probe reservation |

An invalid primary is refused by SRAM; WORK can identify a verified secondary
and explicitly repair it. It does not automatically format unknown retained data.
The manager's development request entry **$6C03 is private/version-paired**,
not a resident public ABI. Streaming hooks and scratch addresses are likewise
private. Applications should use the supported console/loader or WORK contract;
advanced paired-tool maintenance requires the exact matching manager build.

Storage results: $00 completed; $40 unformatted/interrupted layout; $41 invalid
or ambiguous committed metadata; $42 absent/deleted name; $43 directory/extent
full; $44 invalid command/range/entry/name/confirmation; $45 pre-copy CRC/readback
failure; $46 incomplete/unverified copy (no execution); $47 no run entry;
$48 sequence exhausted; $49 WORK administration required. Do not blindly format
on $40: inspect/archive retained data and possible secondary recovery first.

Monitor `R/S/T` select flash by default. `S 2 AUTO ...` finds an erased extent
without erasing occupied data; it may leave the prompt at B2. MAINT 1.8 `X`
copies verified named programs between flash and SRAM while retaining the source.
Flash SR v1 runs at its load address, so SRAM-to-flash rejects an independent
entry that cannot be represented. Flash B3 system space and sealed B2 assets
are protected. See [storage commands/placement](STR8N_V2_STORAGE_TOOLS_2026-10-08.md)
and [directory format](../tools/v2-spi/SRAM_STORE.md) for exact record layouts.

## Runnable 65C02 examples

The [example tutorial](../examples/beta23/README.md) provides complete annotated
sources, build/test commands, S19 loading instructions and expected output:

| Program | Source | Demonstrates |
|---|---|---|
| Read UTC | [read-time.asm](../examples/beta23/read-time.asm) | Discovery, RTC_READ, copied binary calendar and decimal display |
| Read SRAM | [read-spisram.asm](../examples/beta23/read-spisram.asm) | LE24 external address, 16-byte request, bounded read and copied diagnostics |
| WORK area | [work-area.asm](../examples/beta23/work-area.asm) | QUERY/CLAIM, owner/handle, backup, verified WRITE/READ, original-data restoration and RELEASE |

Build with `python tools/build_v2_beta23_examples.py`; all entries are $2000.
The WORK example requires the paired library loaded at $5000, a valid v2 layout
and available claim space. It changes session/claim metadata, restores the
claimed payload on successful cleanup, and reports/retains an uncertain handle
when cleanup fails. It does not format or resize. The tutorial lists all scratch
addresses so application authors can reserve them. New examples are assembled
and model-checked against frozen beta23; physical execution is a separate check.

## Integration checklist and evidence

1. Select the 65C02/816-emulation profile and reserve all called code/scratch.
2. Validate RA, SV capability/gateway/RAM ceiling, then the required signature.
3. Initialize all request fields; use caller-owned buffers and bounded counts.
4. Call only from foreground, check A and Carry, then copy results promptly.
5. Preserve application state according to the specific API, not a universal convention.
6. Rediscover after lifecycle transitions; discard WORK handles after cold reset.
7. Verify readback/publication and account for partial effects on failures.

Authoritative references are the frozen generation-32 build and its bound
receipts, followed by the public symbol files and exact paired utility metadata.
Historical phase documents describe their dated builds, not current placement.
The owner-local freeze is under
`output/qualification/beta23-phase1-2026-10-09/frozen` and the final four-board
receipt under `output/qualification/beta23-final-matrix-2026-10-09-2003`.
These include board data and remain excluded from release packages.

See [four-board evidence](STR8N_V2_BETA23_FOUR_BOARD_STORAGE_2026-10-09.md),
[operator guide](STR8N_V2_BETA23_OPERATOR_2026-10-09.md),
[RC gates](STR8N_V2_RELEASE_CANDIDATE_PLAN_2026-10-09.md) and
[EDU lifecycle](STR8N_V2_EDU_MODE_2026-10-08.md).
Qualified coverage includes physical NMI, 2609 native BRK/NMI vector entry/return,
all caller banks, data preservation, controlled retained-state recovery and
actual main-power retention. Models cover additional write cuts/faults. Native
service calls, general external peripherals, RTC alarms/MFP, crypto and automatic
drift-derived trim application remain outside the RC matrix.
