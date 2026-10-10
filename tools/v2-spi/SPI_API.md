# Resident SPI and SRAM interface

Current contract: frozen beta23 generation 32, qualified on 2512/2205/2604/2609.
All four use EDU ON/TRIM 0 in the current campaign. The public addresses and
request layout below remain applicable; references to beta15, candidate stages
and earlier board modes describe historical checkpoints. Start with the
[beta23 technical guide](../../docs/STR8N_V2_BETA23_TECHNICAL_GUIDE.md).

Beta15 provides the foreground W65C02S service, also usable in 816 emulation
with E=1 and D=DBR=PBR=0. It is installed on all three qualified boards;
the saved EDU mode is OFF on 2512 and ON on 2205/2609. The original placement
is recorded in [Phase 3](../../docs/STR8N_V2_SPI_PHASE3_2026-10-08.md).

Discover SV at $7D04: `SV`,1,flags,gateway LE16,last user-RAM address LE16.
Bits 0/1 retain clock/I2C; bits 2/3 describe validated SPI/SRAM software.
Require the appropriate bit, gateway $6500 and matching service signature:

| Service | Signature | JSR entry |
| --- | --- | --- |
| SPI | `SP`,1,1 at $6646 | $664A |
| SRAM | `SM`,1,1 at $66A2 | $66A6 |

These capabilities do not certify attached hardware. Check again after RESET
or monitor reentry. Missing/corrupt sector 9 removes SPI/SRAM capabilities while
validated clock/I2C remain available. Missing/corrupt sector 8 invalidates the
common gateway dependency. No SPI scan, chip mode change, PROBE or formatting
occurs at boot. With beta15's EDU mode ON, installed software reserves
$6500-$66FF and leaves user RAM through $64FF even without EDU; device failure
does not free that reservation. Explicit EDU OFF at RESET disables the services
and permits RAM through $66FF. Check descriptor capabilities before touching
a service signature or request block. See
[EDU mode](../../docs/STR8N_V2_EDU_MODE_2026-10-08.md).

## Request and return

Requests/results share $6650-$665F with I2C. Do not prepare one service request
while invoking another. Copy results before another service or HOLD; the monitor
can read RTC and replace diagnostics. Nonempty buffers must fit completely in
$0200-$64FF. Zero counts ignore pointers. The common gateway and driver/journal
locks own the whole operation; internal helpers do not reacquire a public lock.

A returns status and Carry is set for success. Stack, full caller PCR, I and
decimal state are preserved; X/Y/N/Z/V are unspecified. IRQ/NMI/native callers
are unsupported. Unsupported cross-bank flash NMI handlers are rejected before
mapping. RAM NMI reentry during an operation returns busy without changing the
active request/results or pins. This is cooperative ownership, not isolation
from programs that directly write VIA or private RAM.

| Offset | SPI meaning | SRAM meaning |
| --- | --- | --- |
| 0 | Profile: 1 mikroBUS; raw 0 SRAM denied | 0 PROBE, 1 READ, 2 WRITE |
| 1 | Bit 0 duplex; other bits zero | Flags zero |
| 2-3 | Transmit pointer LE16 | Address low/middle bytes |
| 4 | Transmit count 0-64 | Address high byte, only 0 or 1 |
| 5-6 | Receive pointer LE16 | CPU buffer LE16 |
| 7 | Receive count 0-64 | Payload count 1-64; zero PROBE |
| 8 | Returned status | Returned status |
| 9 | Transmit bytes clocked | Payload bytes completed |
| 10 | Receive bytes stored | Diagnostic transfer count |
| 11 | 0 validation/refusal, 3 successful cleanup | Capacity low byte on successful PROBE |
| 12 | Receive filler byte | Capacity middle byte on successful PROBE |
| 13 | Mode, currently zero only | Capacity high byte on successful PROBE |
| 14 | Reserved zero | Health on successful PROBE: $81 |
| 15 | Reserved zero | Reserved zero |

SPI must have at least one nonzero count. Normal operation transmits then
receives under one continuous select. Duplex requires equal nonzero counts
and permits identical or disjoint buffers; partial overlap is rejected. No
automatic retries occur. Success means bytes were clocked/stored, not an ACK
from a SPI device. An absent mikroBUS device can return arbitrary input while
transport still completes. External mikroBUS hardware is not yet qualified.

SRAM checks address+count without wrap beyond $020000, and limits each request
to 64 payload bytes. The private adapter sends the header separately so a full
64-byte WRITE fits a single bounded 68-byte frame. It verifies sequential mode
for the operation, then restores/verifies the previous byte/page/sequential mode.
WRITE completion alone is not data readback proof; a saved-record manager must
verify before publishing. PROBE toggles/restores/verifies the reserved $1FFFF
byte. Its nominal capacity is 128 KiB; successful probe does not establish
battery condition or retained-data validity.

Public raw SRAM SPI is always denied. The Phase 4 candidate also denies public
SRAM WRITE from cold initialization, including after RESET, to protect retained
saved programs. READ and PROBE remain available. The standalone SRAM manager
uses a private foreground write path; ordinary clients must not manipulate
private state. This is cooperative ownership, not isolation from direct RAM
writes. [WORK](WORKSPACE_API.md) now supplies checked workspace allocation and
verified writes. The already-reserved byte `$66AF` is its RESET/session latch;
HOLD preserves it, and the gateway template initializes it to zero on RESET.

## Failure and lifecycle

| Status | Meaning |
| --- | --- |
| 0 | Operation completed |
| 1 | Active select, pending CB flag, Port B handshake/pulse mode or input latching |
| 6 | Raw managed SRAM or managed WRITE denied |
| 7 | SRAM mode/probe/restoration unverified |
| 8 | Another operation active; request/results remain untouched |
| 9 | Invalid profile, mode, flags, lengths, overlap, address or CPU buffer |
| $80 | Software/main component absent or incompatible |
| $81 | Backing code integrity failure |
| $82 | Unsupported cross-bank NMI handler |

The engine preserves unrelated driven VIA bits and DDR, deasserting select
before restoration. It does not acknowledge pending CB flags or change
handshake/latching settings automatically. New asynchronous CB activity during
the exclusively owned transfer is outside this foreground contract; interrupt-
signaling SPI devices need later work. Inspect configuration/ownership when
status 1 occurs. Do not discard enabled interrupt evidence to force a transfer.

The gateway verifies the complete sector 8 on first activation and the complete
immutable sector 9 prefix before SPI use. Cached validity lasts until HOLD/RESET;
HOLD preserves initialized/retained state but invalidates executable caches.
Validation errors cause no SPI clocks. A mid-operation readback failure can
leave effects: check results and retain the original bytes needed for recovery.

## Runnable example

Build with `python tools/build_v2_spi_resident_example.py`. Load
`BUILD/v2-spi-resident/example/example.s19` and use `G 2000` to READ 16 bytes
at $10000 into CPU $2300. Copied results are at $2410-$241F. The default READ
does not prove the bytes contain a valid stored object or allocated workspace.

For a caller-prepared operation, put the complete request at $2400 and use
`G 2003`. READ and PROBE are public; a WRITE request returns denied in the
Phase 4 candidate. Saved-program writes use [the SRAM manager](SRAM_STORE.md),
and workspace writes use WORK handles. With the candidate absent on
current beta13 boards, the example
returns software-unavailable rather than calling a stale entry.
Symbols are provided in [spi-api.inc](spi-api.inc).
