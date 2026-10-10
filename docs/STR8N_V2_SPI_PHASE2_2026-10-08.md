# SPI SRAM Phase 2 RAM prototype qualification

Recorded 2026-10-08. The W65C02S SPI/SRAM RAM prototype passed linked-code
models and scoped board qualification on 2512, 2205 and 2609. Both EDU boards'
complete 128 KiB SRAM contents matched independent pre-test reads and final
readbacks. Flash, EEPROM history, factory EUI, remembered identity and RTC
control/trim were preserved. The clocks continued running without SET/ACK/TRIM.

The installed firmware remains beta13/CLOCK 1.5. This phase loads application
RAM only; it does not publish or install resident SPI discovery entries.
Named SRAM program storage and adjustable workspace remain later phases.

## Measured W65C02S implementation

| Item | Measured size |
| --- | --- |
| Standalone prototype code | 1,035 bytes, $3000-$340A |
| Main SPI/SRAM logic | 627 bytes |
| Shared GPIO, mode and pointer helpers | 217 bytes |
| Standalone locks, bank gateway and return wrapper | 191 bytes |
| Qualification client | 287 bytes, $2000-$211E |
| Initialized service load image | 3,569 bytes through $3DF0; includes zero padding |
| Deepest modeled foreground stack | 13 bytes, including caller return |

One byte routine implements transmit, receive and duplex exchange. It uses
compact 65C02 instructions including STZ, BRA, TSB/TRB and accumulator INC,
with short loops and conditional-branch relaxation. Existing verified beta13
buffer-validation helpers are reused rather than duplicated. The prototype
therefore requires that exact provider image; the host verifies it before
loading/execution. It maps B3 for those helpers and restores the complete PCR.
No new zero-page cells are allocated. IRQ/decimal state and stack are preserved.

The original Phase 1 budget of 640 bytes for all combined new logic was too
small for the checked interface and preserving probe. **Revised placement:**
target the measured 627-byte main logic to the recovered B3:9 immutable prefix
and the 217-byte shared helpers to sector 8's 237-byte gap after compacting the
banner. Preserve the entire $9C00-$9FFF identity tail. The standalone 191-byte
wrapper is not copied as another resident gateway: Phase 3 must merge it with
the existing framework, regenerate cross-module addresses/seals and measure
the final bridges, descriptors and dispatch. This is a same-sector placement
proposal; full integrated fit and qualification remain Phase 3 work. No extra
sector has been allocated.

The modeled bit loop gives minimum high/low periods of 24/37 CPU cycles on
the tested payloads. At an illustrative 8 MHz these are 3.0/4.625 microseconds.
These are instruction-cycle bounds, not physical scope measurements or a
configurable SPI frequency promise. Hardware read/write qualification used the
boards' existing clocks.

## Prototype interface

`SP`,1,1 at $3000 has its JSR entry at $3004. `SM`,1,1 at $3007 has its entry
at $300B. These are provisional RAM-prototype addresses. The proposed resident
$6646/$66A2 descriptors do not exist on the installed boards yet. Callers use
the shared request at $6650-$665F, the Phase 1 field layouts, and caller-owned
buffers entirely within $0200-$64FF. Copy results before another service call
or HOLD; the qualification client copies them to $3E10 first.

The client takes requests at $3E00, type/bank/managed-policy parameters at
$3E20-$3E22 and exposes copied diagnostics at $3E10-$3E38. `G 2000` performs
one request. `G 2003` performs 128 bounded 64-byte READ calls and fills
$4000-$5FFF with an 8 KiB block. Both source and loaded RAM images are checked
before execution. Loading CLOCK afterward replaces the prototype code, leaving
the normal monitor/service environment ready.

Public SPI supports mode 0, write-then-read, read-only clocks with a filler byte
and full duplex with equal counts. Exactly in-place or disjoint duplex buffers
are allowed; partial overlaps are rejected. Each direction is limited to 64
bytes. A successful transaction means clocks/stores completed; there is no
fabricated SPI ACK or implied device-presence result.

SRAM provides explicit PROBE, READ and WRITE, with three address bytes and
1-64 byte payloads. Both physical and CPU end arithmetic are checked before
transfers. The private adapter sends a four-byte command/address header directly
through the shared byte engine, then the caller's payload. A 64-byte WRITE is
one bounded 68-byte internal frame: no packet-copy buffer or 60+4 splitting is
needed. Public SPI buffer limits remain 64 bytes per direction.

READ/WRITE temporarily select and verify sequential mode if needed, then
restore and verify the prior mode. PROBE toggles one byte at $1FFFF, within
the reserved final 32-byte area, verifies it, restores it and verifies restoration.
Its reported capacity is the configured 23LCV1024 size; the separate lower/upper
alias test establishes address bit 16 on the real boards. Failed mode/data or
restoration checks return unusable status 7. Mode/battery retention is never
inferred solely from a successful clocked transfer.

Before managed storage exists, the prototype can perform explicit raw writes.
A controlled policy flag at $3DF0 models managed ownership: public raw SRAM
SPI and raw SRAM WRITE then return denial 6 before pin changes. The real catalog
and workspace manager, ownership handles and private write authorization remain
future work. The software policy is cooperative; direct VIA access is possible.

## VIA ownership and qualification setup

The engine uses VIA1 PB0 clock, PB1 MOSI, PB5 MISO and PB2/PB3 selects. It
checks the original select/DDR state, preserves unrelated driven bits, releases
select before restoration and never substitutes VIA2's flash-bank PCR for these
pins. Pending CB1/CB2 flags, Port B handshake/pulse mode and Port B input
latching are refused before port access. New asynchronous CB activity during
an exclusively owned transfer is outside this prototype's contract. It does
not support an interrupt-signaling mikroBUS peripheral yet.

2609 initially returned busy 1 with IFR $1A, IER $80, PCR/ACR/DDRB $00.
The prototype left those flags intact. Qualification recorded the state and
explicitly acknowledged only the disabled CB flags through a Port B read,
after checking that no CB interrupt was enabled, no handshake mode was active
and the SPI pins were inputs. IFR became $02; control registers and pin
directions were unchanged. This was test setup, not hidden driver cleanup.
The failed first attempt and the setup evidence are retained locally.

## Model coverage

Linked opcodes ran against bit-level VIA, SRAM and synthetic second-device
models. Checks covered sequential/duplex transfers, exact in-place and positive/
negative disjoint boundaries, partial-overlap rejection, maximum counts and
page-crossing CPU buffers. Busy refusal preserved active request/results and
pins. Unsupported arguments, modes, profiles, protected buffers and active
VIA configurations refused before transfers.

SRAM models covered byte/page/sequential mode restoration, $0FFFF/$10000 and
$1FFFF boundaries, missing/stuck data, ignored writes and failed restoration.
All four caller banks, preserved flags/PCR/stack/RTC output, RAM NMI reentry
refusal and the bulk client passed. NMI handler stack use is excluded from the
13-byte foreground measurement. IRQ/NMI callers and native 816 remain unsupported.

## Physical board coverage

| Board | Result |
| --- | --- |
| 2512 COM4, W65C02SXB, no EDU | PASS: bounded unusable status, all caller banks, invalid range refusal; flash unchanged |
| 2205 COM3, W65C02SXB, EDU | PASS: full array archived twice; preserving boundary/alias tests; full final array identical |
| 2609 COM8, W65C816SXB, EDU | PASS in emulation after explicit disabled-flag setup; same array/boundary/alias checks |

Both EDU chips initially used mode $40, and every completed operation retained
that mode. Pattern tests covered $00000, $0FFFE across the 64 KiB boundary,
$10000, $1FFC0 and $1FFFF. Distinct values were held simultaneously at $00040
and $10040, then read separately before restoration, proving non-aliasing.
The CPU buffer ending exactly at $64FF succeeded; overflow was rejected.
The complete final 131,072-byte comparisons proved that all test bytes were
restored, beyond the individual test readbacks.

All four flash banks matched repeated pre-test backups and final readbacks.
Both EDU EEPROM arrays, factory/protection bytes and clock control/trim $80/$00
matched the prior archives. The clocks advanced; original UTC baseline hashes
were retained. Final ports were closed with all boards at B3. No physical NMI,
native SPI, external mikroBUS, battery-removal, crypto or new flash installation
was included in this scope.

## Reproduce and continue

Build/model checks: `python tools/build_v2_spi_prototype.py` and
`python tools/test_v2_spi_prototype.py`. Builders and model outputs remain under
`BUILD/v2-spi-phase2`. Owner-local hardware evidence is under
`output/qualification/spi-phase2-2026-10-08`; `acceptance.json` binds the models,
loaded images, archives and final state. Recheck with
`python tools/audit_v2_spi_phase2.py --root output/qualification/spi-phase2-2026-10-08`.
Raw flash/SRAM backups and transcripts remain ignored.

Phase 2 is complete for this RAM-only scope. Next is Phase 3: integrate the
measured driver/helpers, merge the gateway, publish independent discovery and
memory guards, and build a matched resident candidate before any installation.
User RAM still ends at $64FF with the currently installed software, even without
EDU. See [the phased plan](STR8N_V2_SPI_SRAM_PHASED_PLAN_2026-10-07.md) and
[Phase 1](STR8N_V2_SPI_PHASE1_2026-10-07.md).
