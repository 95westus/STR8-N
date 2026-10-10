# SPI Phase 1 interface and placement proposal

Recorded 2026-10-07 after the verified beta13/CLOCK 1.5 update on 2512, 2205
and 2609. Phase 1 establishes measured headroom, a proposed ABI and ownership
rules. SPI implementation and RAM-prototype hardware tests belong to Phase 2.
The size experiments below do not replace the installed firmware.

Subsequent [Phase 2 qualification](STR8N_V2_SPI_PHASE2_2026-10-08.md) revises
the size proposal: 627-byte main logic plus 217-byte shared helpers targeted
to recovered sector 8 space. The prototype is qualified in RAM; full resident
integration and gateway fit remain Phase 3 work.

## Measured placement

The installed beta13 monitor occupies 3,967 of 3,968 bytes. Its E launcher
occupies 1,754 of 1,760. Immediate monitor command additions cannot fit without
reworking those allocations. Fixed recovery F remains unchanged.

| Region | Installed code | Available space under current layout |
| --- | --- | --- |
| B3 sector 8 provider, including seal | 2,267 bytes | 37 bytes before fixed banner at $8900 |
| Banner and formatting at $8900 | 1,156 bytes | 108 bytes before gateway template at $8DF0 |
| Gateway template at $8DF0 | 512 bytes | 14 bytes before sector seal at $8FFE |
| B3 sector 9 immutable code | 2,810 bytes | 260 bytes before prefix seal at $9BFE |
| B3 $9C00-$9FFF | 1,024 bytes | Owned by EUI binding records |
| Board RAM gateway code | 326 bytes | 10 bytes before the request at $6650 |

An isolated WDC assembly experiment reused the existing branch-relaxation
method: replace an expanded conditional branch with a short branch when the
assembled displacement fits. It produced these measured sizes:

| Module | Original code | Compacted code | Saving |
| --- | --- | --- | --- |
| Provider excluding seal | 2,265 | 2,199 | 66 bytes |
| Banner and formatting | 1,156 | 1,027 | 129 bytes |
| Journal and EUI administration | 2,810 | 2,414 | 396 bytes |
| CLOCK 1.5 | 6,443 | 5,969 | 474 bytes |

These independently linked sizing objects are not a matched executable
candidate. Cross-module addresses and seals must be regenerated, then the
functional regressions repeated before using any compacted code. Current
beta13 artifact hashes remain unchanged. Reproduce the report with
`python tools/measure_v2_spi_phase1.py`; local results are under
`BUILD/v2-spi-phase1/report.json`.

**Preferred placement:** compact the existing B3 sector 9 code prefix and put
SPI transport, SRAM adapters, validation and dispatch glue in its recovered
space. Set a combined new-code budget of **640 bytes**, inside the measured
656-byte gap. Preserve the prefix seal and the entire EUI tail. Small provider
bridges may use recovered sector 8 space. No additional sector is allocated.
Full driver fit remains to be proved by the Phase 2 assembly; exceeding this
budget requires revisiting placement before integration.

## RAM allocation target

Retain the current $6500-$66FF software reservation and user-RAM top $64FF.
Installed software owns it even when EDU is absent. Keep the existing RG and
I2 descriptors, public entries and request/result locations compatible.

The current layout has 10 bytes after gateway code, 4 after the I2C request,
14 after provider-private state and 8 after the RAM I/O thunks. The proposal
uses those documented gaps and overlays mutually exclusive request/scratch
state rather than adding a second allocation.

| Proposed location | Purpose |
| --- | --- |
| $6646-$664C | SPI descriptor `SP`,1,1 and one JMP entry |
| $6650-$665F | Shared 16-byte request/result area for I2C, SPI or SRAM |
| $6669 | Existing common driver lock |
| $666A-$66A1 | Existing volatile provider scratch, reused under the lock |
| $66A2-$66AD | SRAM descriptor `SM`,1,1, one JMP entry and five-byte stub |
| $66B8-$66BC | Five-byte SPI gateway stub |

Addresses are a layout target, not callable installed entries. The generated
gateway must prove that code and tables remain within these gaps. RTC output,
requests and retained outage capture at $66C0-$66FF remain owned by RTC.
The monitor's $6B00-$6BFF scratch may be used only by a complete foreground
storage/driver operation, excluding flash staging and other monitor operations.

The SPI target adds no zero-page cells: use the existing RAM I/O thunks and
locked absolute-address scratch. Existing journal paths still lease their
documented monitor zero-page cells; preserve that lease if the dispatch passes
through them. Set a 16-byte additional foreground stack budget including the
public JSR and nested gateway/adapter/byte calls, excluding asynchronous NMI
handler use. This is a design ceiling, not a measured new-driver stack result.
Phase 2 must record actual deepest stack use and verify caller SP restoration.

## Discovery and calling contract

Retain SV format 1 and the gateway pointer at $7D04. Existing bits 0/1 continue
to identify RTC/I2C software. Proposed bits 2/3 identify validated SPI/SRAM
software, with descriptors at gateway-relative offsets $0146/$01A2. They do
not claim attached hardware or healthy SRAM. Publish capabilities only after
verifying all backing immutable code. A failed SPI component must leave
validated RTC/I2C services available where their dependencies remain intact.

Public code discovers the appropriate signature before calling its single
JSR entry. SPI takes its transaction from the shared request. SRAM takes a
PROBE, READ or WRITE operation from that request. The gateway selects B3,
validates code, dispatches and restores the caller's complete PCR. Use the
existing foreground W65C02S / 816-emulation contract: E=1 on 816,
D=DBR=PBR=0; preserve stack and documented I/decimal/bank state. A returns
status, Carry is set on success; X/Y/N/Z/V are unspecified. IRQ/NMI/native
callers and concurrent users remain unsupported.

Own the complete operation. Common gateway and driver locks cover SPI, SRAM,
I2C and RTC adapters; internal transfers never reacquire a public lock. Busy
refusal leaves the active request, counts, pins and selected device untouched.
Requests/results are shared: copy needed results before another service call,
and do not prepare one request while invoking a different service. Existing
clients must keep transmit buffers stable until return, as before.

## Proposed SPI request

| Offset | Field |
| --- | --- |
| 0 | Device profile: 0 SRAM, 1 mikroBUS SPI |
| 1 | Flags: bit 0 full duplex; other bits zero |
| 2-3 | Transmit RAM pointer, LE16 |
| 4 | Transmit count, 0-64 |
| 5-6 | Receive RAM pointer, LE16 |
| 7 | Receive count, 0-64 |
| 8 | Returned status |
| 9 | Transmit bytes clocked |
| 10 | Receive bytes stored |
| 11 | Completion/error phase |
| 12 | Filler byte during receive-only clocks |
| 13 | Mode: initial implementation accepts mode 0 only |
| 14-15 | Reserved, zero |

At least one count is nonzero. A nonempty buffer must be entirely within the
validated application-RAM range; validate sum/end arithmetic before touching
pins. In sequential mode, transmit then receive under one continuous select,
with at most 128 byte times. With duplex enabled, require equal nonzero counts
and exchange those bytes simultaneously. Duplex permits exactly in-place
buffers; reject other transmit/receive overlaps. Sequential overlap is allowed
because transmission completes before receive stores.

Use named profiles instead of caller-supplied arbitrary VIA addresses/masks.
SRAM uses PB2 and mikroBUS PB3; clock PB0, MOSI PB1 and MISO PB5. Keep both
selects inactive while changing direction/idle state. Refuse a preexisting
actively driven select before claiming the bus. Preserve unrelated VIA bits,
registers and state; release select before restoration. Do not use VIA2's PCR
for SPI pins: that register controls flash bank selection.
[WDC EDU wiring, section 3.1](https://www.wdc65xx.com/wdc/documentation/W65C02EDU.pdf).

Once managed SRAM storage is enabled, public raw profile 0 is denied; the SRAM
adapter uses a private authorized path. Profile 1 remains available to ordinary
programs. Unsupported modes/profiles fail explicitly. No scan or peripheral
commands are sent automatically during boot. The Phase 2 prototype will measure
transfer timing on supported board clocks; no configurable frequency contract
is claimed by this version.

Status 0 means the requested clocks/stores completed. SPI provides no ACK, so
this does not prove a peripheral received a command. Proposed shared statuses:
1 preexisting active select, 6 managed-device denial, 7 readback/probe failure,
8 operation already active, 9 invalid arguments/unsupported mode, $80 absent
software, $81 integrity failure and $82 unsupported cross-bank NMI handler.
Do not reuse I2C NACK as a fabricated SPI device-presence result. Report phases
0 validation, 1 transmit, 2 receive/duplex and 3 cleanup. On a partial transfer,
return completed counts; no automatic retry or rollback.

## Proposed SRAM request and behavior

| Offset | Field |
| --- | --- |
| 0 | Operation: 0 PROBE, 1 READ, 2 WRITE |
| 1 | Flags, initially zero |
| 2-4 | SRAM address, LE24 |
| 5-6 | CPU RAM buffer pointer, LE16 |
| 7 | Payload count, 1-64 for READ/WRITE |
| 8 | Returned status |
| 9 | Payload bytes completed |
| 10 | Error/completion phase |
| 11-13 | Capacity, LE24 on successful PROBE: $020000 |
| 14 | Usability/retention status; battery condition remains unknown |
| 15 | Reserved, zero |

READ/WRITE require address <=$01FFFF and address+count <=$020000, using carry
checks across all three bytes. Zero is not a special spelling of 64 KiB.
Validate CPU buffers before transfers. Emit the three address bytes in the
chip's wire order. Maintain/verify sequential mode during explicit SRAM use;
changing its mode register does not format or erase the array. End-of-array
wrap is forbidden even though the chip supports it.
[23LCV1024 datasheet, section 2](https://ww1.microchip.com/downloads/en/DeviceDoc/23LCV1024-1Mbit-SPI-Serial-SRAM-with-Battery-Backup-and-SDI-Interface-20005156B.pdf).

Reserve the last 32 bytes, $1FFE0-$1FFFF, for a bounded usability probe. Preserve
and restore their contents during qualification; a failed restoration makes
storage untrusted. PROBE is explicit and distinct from descriptor discovery.
Full-address alias tests on $0FFFF/$10000 and the array end belong to Phase 2.
Do not accept an absent device merely because a read returns all $00 or $FF.

The private adapter stages command/address bytes in monitor scratch. A READ
can send a four-byte header then receive up to 64 payload bytes. A WRITE uses
up to 60 payload bytes per 64-byte transport packet; a 64-byte SRAM request
therefore uses two bounded frames under the same operation lock. Count only
payload bytes in SRAM results. Write completion alone is not readback proof;
saved-program publication always requires verification.

Before managed storage is enabled, explicit prototype block writes are bounded
by physical and CPU-buffer checks. After enablement, ordinary public writes
must not bypass the program catalog, probe reservation or workspace claims.
The storage/workspace manager validates ownership and invokes a private write
path; unprivileged raw block writes are denied. That policy must be established
before publishing managed storage. It is cooperative software ownership, not
hardware isolation against programs that access VIA directly.

## Program storage and workspace direction

The initial physical split targets $00000-$0FFFF for program storage, including
its headers/directory, and $10000-$1FFDF for workspace. The final 32 bytes belong
to the probe. Report usable payload capacity after metadata; these ranges are
gross allocations. Phase 4 defines the persistent record format; Phase 5 adds
adjustable allocation units, claims and resize checks. No record relocation or
automatic compaction is required initially.

Flash continues to serve named `R` programs on every board. To avoid spending
the monitor's single remaining byte, the initial SRAM user interface will be a
small saved utility, launched through the existing `R SRAM` workflow. Its own
save/restore/table commands select SPI storage explicitly. Program restores
follow current load/entry behavior and the published CPU-RAM limit. A later
compact monitor provider syntax can be considered after its assembled fit is
measured. Do not silently prefer SRAM over a same-named flash record.

Workspace claims use offsets/handles, owner and generation checks. RESET
invalidates temporary claims; normal HOLD preserves live ownership. Saved
programs are independently validated before reuse after reset or power loss.
SRAM retention depends on a working backup supply; invalid retained state
does not authorize automatic formatting or stop flash recovery.

## Future crypto transport requirement

ATECC608A is an I2C device; SPI has no crypto-specific responsibilities.
The existing 64-byte I2C interface is insufficient for all command packets:
Microchip's P-256 external VERIFY packet is 135 bytes. Keep the present ABI
unchanged and reserve a versioned/private long-packet path, initially bounded
to 255 bytes with caller-owned buffers. Include explicit wake handling and
bounded waits/polling in a later crypto adapter; do not add automatic wake,
address-zero traffic or crypto commands to ordinary I2C calls.
[Microchip CryptoAuthLib command definitions](https://github.com/MicrochipTech/cryptoauthlib/blob/main/lib/calib/calib_command.h).

This records the transport requirement without implementing crypto. The future
adapter must qualify whole-packet framing, CRC, delays and device state before
claiming crypto support. It can reuse the shared transport without a new SPI
interface or a permanent large board-RAM buffer.

## Phase 1 completion and Phase 2 gate

Phase 1 has a reproducible inventory and sizing report, a preferred existing-
sector target, proposed compatible RAM allocation, bounded transaction/block
formats, device policy, error/partial-progress contract and explicit initial
storage selection. No SPI code was installed or SPI/crypto pins accessed.

Phase 2 must assemble the real engine/adapters within the 640-byte budget,
prove the proposed RAM gaps and shared-state rules, regenerate dependent
addresses/seals, and execute host models before running a RAM-only prototype.
Required checks include all caller banks, busy/unsupported refusal, VIA/select
restoration, in-place duplex, maximum/boundary buffers, managed SRAM policy,
full 17-bit addressing and readback/probe failures. Qualify 2512's no-EDU path
and EDU access on 2205/2609. General mikroBUS hardware remains unqualified until
a representative device is attached and tested.

See [the phased plan](STR8N_V2_SPI_SRAM_PHASED_PLAN_2026-10-07.md) and
[beta13 installation](STR8N_V2_TRIM_HARDWARE_2026-10-07.md).
