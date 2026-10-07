# Shared I2C transaction interface

The phase 2 extension candidate supplies a shared transaction engine for RTC and
other I2C devices. This versioned candidate is installed in beta5 on 2512, 2205
and 2609. It uses the same foreground 65C02/816-emulation
profile and caller-bank/NMI requirements as the clock gateway.

Programs discover `I2`, format 1, entry count 1 at `$6510` and call `$6514` with
JSR. Clock discovery remains `RG`, format 1, count 4 at `$6500`; its four entries
are unchanged. First check the kernel descriptor at `$7D04`: `SV`, format 1,
capability flags (bit 0 clock, bit 1 I2C), little-endian gateway pointer, and
little-endian last application-RAM address. Installed bytes are
`53 56 01 03 00 65 FF 64`. Missing/corrupt optional software clears capabilities
and pointer; a cold boot then permits RAM through `$66FF`. Never call a stale
gateway pointer after RESET or monitor reentry without checking discovery.
The allocation is `$6500-$66FF`, protected by the monitor and MAINT 1.6.
With service software installed, the highest user/program RAM address is
`$64FF`, inclusive, even when no EDU board or RTC is present. Only absent or
rejected optional service software on a cold boot can permit user RAM through
`$66FF`. An active reservation survives later validation failures until RESET.
Use the validated kernel descriptor's RAM limit; a device error does not free
service RAM.
RESET must initialize the trusted gateway image; first request validates and
activates the shared flash component. A valid bus service does not require an RTC
to respond or have valid time.

## Request and result

Prepare the eight-byte request at `$6650`; buffers remain in caller-owned board
RAM. See [i2c-api.inc](i2c-api.inc) for symbols.

| Offset | Field |
| --- | --- |
| 0 | Unshifted seven-bit device address, `$08-$77` |
| 1 | Flags: bit 0 repeated START; all other bits must be zero |
| 2 through 3 | Little-endian write-buffer pointer |
| 4 | Write count, 0 through 64 |
| 5 through 6 | Little-endian read-buffer pointer |
| 7 | Read count, 0 through 64 |
| 8 | Completed-call status |
| 9 | Acknowledged write payload bytes, excluding device address |
| 10 | Completed/stored read bytes |
| 11 | Transfer phase |

At least one count must be nonzero. Each nonempty buffer must lie entirely in
`$0200-$64FF`; an empty direction ignores its pointer. Stack, zero page, service
workspace, monitor RAM, I/O and flash buffers are rejected. A flash-resident
client must copy its payload to ordinary RAM first. Keep requests and transmit
buffers stable until return. Overlapping transmit/receive buffers are allowed:
the full transmit part is consumed before receive data is stored.

Write-only sends address/write, payload, STOP. Read-only sends address/read,
receives data, sends final NACK, then STOP. Combined requests send write payload
and then read payload. Flag 1 selects repeated START between them; flag 0 selects
STOP followed by a new START. No automatic scan, device initialization, retries,
bus-clear pulses, clock setting or power-fail acknowledgment is performed.

The current clock-stretch limit is the shared driver's 255 line polls per clock
release. Its elapsed time depends on CPU speed; this is not a millisecond timeout
contract or support for arbitrarily long stretching. Transfer sizes and every
clock wait are bounded. Longer/configurable timeouts require later qualification.

## Returns and policy

Return A is status and C is set for success. I, decimal mode, stack and caller PCR
are preserved. X/Y/N/Z/V are unspecified. The last completed result is in the
request block; a reentrant refusal returns A=8 without changing active outputs.
Results/diagnostics are shared and may be replaced by subsequent clock or bus
calls, so copy them when needed. RTC register operations use this same engine.
The beta6 monitor is another clock client when its banner appears after HOLD;
copy results/counts into your own RAM before returning if they are needed later.

| Status | Meaning |
| --- | --- |
| 0 | Completed |
| 1 | Bus not idle |
| 2 | Slave NACK; phase identifies address versus payload |
| 3 | Clock/STOP timeout |
| 6 | Managed-device policy denied the request |
| 8 | Shared operation already active |
| 9 | Invalid address, flags, counts or buffer range |
| `$80` | Extension absent/incompatible |
| `$81` | Extension integrity failure |
| `$82` | Unsupported NMI handler for a cross-bank call |

Phase 0 is validation/idle setup, 1 write address, 2 write data, 3 read address,
4 read data and 5 STOP. Errors retain the phase where progress failed; successful
calls normally leave the last payload phase. Validation/policy/unavailable errors
report zero progress. A NACK/timeout may follow acknowledged writes or completed
reads; those effects are not rolled back. Counts describe completed bytes, not
proof that a device finished an internal operation. Cleanup attempts STOP and
restores observed VIA state; a physically stuck line cannot be forced healthy.

The managed RTC at `$6F` permits public register reads only: one pointer byte,
repeated START, a nonzero read count, and a range within `$00-$1F`. Data writes,
unknown-pointer reads and RTC SRAM ranges are denied. Clock setting and outage
acknowledgment use the explicit RTC entries, which preserve evidence first.
The MCP EEPROM address `$57` is denied in this interface; its driver/allocation
remains deferred. Other devices can use read/write/combined transactions normally.
This cooperative policy does not prevent a program from directly accessing VIA.

The gateway owns the complete operation, including all related RTC transfers.
Internal RTC adapters call the common engine without taking the same lock again.
IRQ/NMI/native callers and multiple bus masters are not supported by this version.

## Example and verification

To read four bytes from register `$10` at address `$3C`, place `$10` at `$2000`
and prepare: `3C 01 00 20 01 00 21 04` at `$6650`. Call `$6514`; on success,
receive data is at `$2100-$2103`, with written/read counts 1/4.

Build and verify:

```text
python tools/build_v2_rtc.py
python tools/build_v2_rtc_split.py
python tools/test_v2_rtc_split.py
python tools/test_v2_i2c.py
```

Reports in `BUILD/v2-rtc-phase2-split` bind the linked-image hashes. Tests cover
RTC operations through the refactored engine, a modeled second slave with RTC
absent, alternating services, all caller banks, NMI during transfer, page-crossing
buffers, maximum count/boundary, repeated START versus STOP/start, partial NACK
progress, bounded timeout, rejected buffers/arguments and managed-device policy.
The installed firmware additionally passed both SXB CPU types, no-EDU handling,
public MCP register reads, caller-bank/VIA preservation, relocated MAINT and
protection checks. A physical second peripheral has not been qualified. See
[the phase 2 acceptance record](../../docs/STR8N_V2_RTC_PHASE2_2026-10-06.md).
