# SPI SRAM Phase 3 resident candidate

Recorded 2026-10-08. Phase 3 integrates the qualified W65C02S RAM prototype into
a matched **beta14 generation 23** resident candidate. It passes linked-code
SPI/SRAM models, existing-service regressions and three exact-backup offline
update rehearsals. The boards remain beta13/CLOCK 1.5; installation is Phase 6.
No serial port or board was accessed in this phase.

## Placement and measured sizes

| Component | Candidate bytes | Allocation and remaining space |
| --- | --- | --- |
| Provider, bridges and pointer helpers, including its seal | 2,299 | $8000-$88FF; 5 bytes before banner |
| Banner, validation, SPI GPIO/mode/cleanup helpers | 1,262 | $8900-$8DEF; 2 bytes before gateway template |
| Journal, EUI administration and SPI/SRAM main code | 3,070 | $9000-$9BFD; seal at $9BFE-$9BFF |
| EUI binding records | 1,024 | $9C00-$9FFF; retained independently of code CRC |
| RAM gateway code and header constants | 319 | Below fixed SPI table at $6646 |
| Gateway/state allocation | 512 | $6500-$66FF unchanged |
| Monitor slots A and B | 3,967 each | 3,968-byte code limit |
| E launcher | 1,754 | 1,760-byte limit |
| Runnable SRAM example | 155 | CPU $2000-$209A |
| Deepest modeled foreground SPI stack | 15 | Includes caller return; 16-byte design ceiling |

The journal code prefix is fully occupied. Future growth requires further
measured optimization or a revised allocation; the EUI tail is not spare code
space. Phase 3 reuses the trusted E CRC routines, the bank gateway, buffer
validators, shared locks and RAM I/O thunks. Short eligible jumps/branches and
compact 65C02 operations reduce duplicate code. Fixed recovery F remains
byte-identical; no additional sector or board-RAM reservation is introduced.

Provider format is RC,3,7; banner is BT,5,3; immutable journal prefix is PJ,6,1.
The existing public RG,1,4 and I2,1,1 entries/addresses remain compatible. A new
matched component must not be mixed with older private formats or link addresses.

## Discovery and activation

SV format 1 at $7D04 retains gateway $6500 and user-RAM top $64FF. Bits 0/1
remain clock/I2C; bits 2/3 identify validated SPI/SRAM software. A complete
candidate publishes $0F. The separate interfaces are:

| Interface | Signature | JSR entry |
| --- | --- | --- |
| SPI | SP,1,1 at $6646 | $664A |
| SRAM | SM,1,1 at $66A2 | $66A6 |

Discovery describes software availability, not a fitted or healthy chip. Boot
does not clock SPI pins, select SRAM mode, PROBE, erase or format its array.
SPI/SRAM use remains independent of responding RTC hardware. An absent or
corrupt main prefix leaves validated RTC/I2C available with capability $03;
common sector 8 failure invalidates its dependent bootstrap/services.

The shared RAM gateway validates the complete sector 8 on activation. The SPI
bridge validates the complete immutable sector 9 prefix before first execution.
HOLD clears executable-validity cache bits while retaining initialized state,
outage capture, policy and RAM ownership. RESET initializes a new trusted
gateway. Validation and unavailable errors cause no SPI clocks. A peripheral
failure or later validation failure cannot free an active reservation before
RESET. With software installed, user RAM ends at $64FF even without EDU.

## Ownership and device policy

The common bank gateway owns the complete operation and preserves caller PCR,
stack, I and decimal state. Driver/journal locks prevent shared scratch or
monitor probe-buffer overlap. Busy refusals leave active requests, counts,
results, locks and pins intact. The request/result block at $6650-$665F is
shared across buses; clients copy needed outputs before another call or HOLD.

Public raw SPI profile 0 SRAM is always denied. Profile 1 mikroBUS remains a
general mode-0 transport with bounded sequential/duplex transfers. SRAM READ,
WRITE and explicit preserving PROBE use private authorized transport. The
managed-policy byte at $66AE defaults to zero on cold initialization and
survives HOLD. Enabling it denies public raw SRAM WRITE; the actual catalog,
workspace ownership and private manager write path are later work.

Phase 4 supersedes that initial policy: the current candidate defaults to
managed WRITE denial even after RESET, and the standalone SRAM utility uses a
private foreground write path. Public READ/PROBE remain available. Updated
models and offline recipes qualify the changed gateway initialization byte.

GPIO checks/cleanup retain the Phase 2 behavior: refuse pending CB flags,
active selects, handshake/pulse modes and Port B input latching before port
access. There is no automatic interrupt acknowledgment. Mode/readback failures
are explicit; SPI transport completion is not an ACK or peripheral-presence
proof. IRQ/NMI/native callers and interrupt-signaling SPI devices remain outside
the foreground contract. A RAM NMI attempt during transfer returns busy without
damaging the active transaction; cross-bank flash NMI handlers are refused.

## Qualification

Models boot the actual matched ROM/RAM images and exercise all caller banks,
software-only discovery, lazy integrity, cold missing-main fallback, shared
locks, managed refusal, cache invalidation and retained RAM bounds. SRAM tests
cover absent/stuck/failed writes, probe preservation, byte/page/sequential mode
restoration, $0FFFF/$10000 and $1FFFF boundaries, duplex and alternating
SPI/SRAM/I2C/RTC calls. Actual RAM NMI reentry and stack checks pass.

The 437-case calendar/weekday suite, confirmed/canceled SET, ACK/history,
fine-trim range/readback failures, TIME/example, boot status, monitor/MAINT
guards and legacy SAVE/RESTORE pass. EUI interruption tests exercise every
replacement-write cut point; valid old identities survive until commit.
The entire mutable identity tail is preserved by compatible code-prefix merge.

The SRAM example reads 16 bytes from $10000 by default and supports a caller-
prepared READ/WRITE/PROBE at entry $2003, copying outputs before HOLD. It is
model-qualified against the resident gateway. Current beta13 boards report
software unavailable because their SPI capability is absent. See
[the API and example instructions](../tools/v2-spi/SPI_API.md).

## Offline installation recipe

The reviewed beta13-to-beta14 recipe updates only B3 sectors C, 8, 9, E, B
and A. CLOCK 1.5, MAINT 1.7 and other B0/B1/B2 contents remain unchanged.
Carry forward current valid configuration/preference and erase accounting;
preserve every EUI-tail byte and fixed F. There is no saved-record commit or
SRAM formatting operation. Independent full backups and current-image matching
are required before a later physical installation.

The RAM migrator was executed against the archived complete images of 2512,
2205 and 2609. Each exact final image and sector order matched its plan. Stale
target preimages and corrupt staged payloads were refused before mutation.
These are offline rehearsals, not new board acceptance or installation proof.
Rehearsal backups/payloads are ignored under BUILD and never included in Git.

## Artifacts and next phase

Build with `python tools/build_v2_spi_resident.py` and
`python tools/build_v2_spi_resident_example.py`. Run resident checks with
`python tools/test_v2_spi_resident.py`; the existing regression scripts use
`STR8_RTC_BUILD=BUILD/v2-spi-resident` and CLOCK build `BUILD/v2-clock-1.5`.
Canonical reports, generated sources, seals and models are under
`BUILD/v2-spi-resident`. `candidate-check.json` binds their hashes. Audit with
`python tools/audit_v2_spi_resident.py` and the backup-exclusion checker.

Phase 3 is complete for the matched unflashed candidate. Next is Phase 4:
named saved-program storage in SPI SRAM, alongside proven flash storage.
Adjustable workspace is Phase 5; physical rollout is Phase 6. Crypto, native
816 and additional physical SPI profiles remain deferred. The published
release remains beta4 and the installed boards remain beta13.
