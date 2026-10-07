# Phase 2 optional RTC flash extension

Recorded 2026-10-06. The measured candidate keeps RTC code in resident Bank 3
flash and its call gateway and mutable state in board RAM. Activation remains
on the first program clock or I2C request. The separate-sector design is now
integrated in the beta5 candidate and installed on boards 2512, 2205 and 2609.
Phase 1 sources and published beta4 firmware remain unchanged. See
[the integrated acceptance record](STR8N_V2_RTC_PHASE2_2026-10-06.md) for
artifact identity, migration, hardware results and remaining scope.

## Extension architecture

Use a separate versioned RTC descriptor and call table, following the existing
RESTORE/SAVE/TABLE extension pattern. A trusted RAM gateway selects resident
Bank 3, validates the RTC component on first request, initializes its private
state, calls the flash entry, then restores the caller's full bank-selection
register. The code stays in flash; activation initializes the RAM side instead
of copying the whole driver. Activation never sets time or acknowledges an outage.

When software support is enabled, reserve its RAM from RESET and retain the
service until RESET or explicit safe invalidation. Missing/corrupt software,
missing hardware, and unusable clock time remain separate results. Boot,
recovery and existing RST operation must work without the RTC component.

## Shared I2C interface

Expose a versioned I2C transaction service beneath the RTC service. Both may
share the extension sector, but programs discover their interfaces separately.
The I2C interface must not depend on a valid/running RTC, and should remain
usable for other wired devices when clock support is disabled or the MCP is
absent. Activation occurs on the first request for either service; no automatic
bus scan, clock setting, or device initialization occurs at boot.

The public operation should describe a complete transaction: seven-bit device
address, caller-owned write buffer/count, caller-owned read buffer/count, and
whether a repeated START is required between write and read. Support write,
read, and combined register-address/write-then-read patterns. Return explicit
busy, NACK, timeout, and argument failures with defined partial-transfer results.
Bound lengths, buffer ranges, retries, and clock-stretch waits.

Keep bus ownership for the complete operation so clients cannot interleave START,
data, and STOP. RTC operations hold ownership across their related transfers and
use internal transport calls that do not reacquire the same lock. Restore VIA
state and release bus lines on completion/error where possible. The first
interface remains foreground-only, single-master, and nonreentrant, using the
same documented CPU/bank/interrupt contracts as the gateway.

Normal clock clients use the RTC API. Raw transfers that bypass managed clock
setting or power-fail acknowledgment policy require explicit authorization;
publishing I2C must not silently remove those controls. This is a cooperative
service policy, not hardware memory isolation.

The candidate now exposes separate `RG` clock and `I2` bus descriptors. RTC
register reads/writes use the same transaction engine as public clients, through
private adapters that keep managed clock authorization. Public clients use
caller-owned RAM buffers, up to 64 bytes per direction, and receive completed-byte
counts and failure phase. RTC register reads are permitted; unmanaged RTC data
writes and MCP EEPROM/SRAM access are denied. The limit on clock stretching is
255 line polls, not a millisecond guarantee. See
[the provisional I2C ABI](../tools/v2-rtc/I2C_API.md).
SRAM/EEPROM drivers and allocations remain
deferred, as do alarms and automatic probes of other EDU devices.

## Measured footprint

| Part | Bytes | Model location |
| --- | --- | --- |
| Flash RTC/shared-I2C driver and seal | 1760 | B3 `$8000-$86DF` |
| RAM gateway code | 326 | `$6500-$6645` |
| RAM buffer access thunks | 8 | `$66B0-$66B7` |
| I2C request/results | 12 | `$6650-$665B` |
| Gateway variables | 9 | `$6660-$6668` |
| Private driver state | 57 | `$6669-$66A1` |
| Public/result/client buffers | 64 | `$66C0-$66FF` |
| Complete RAM reservation including gaps | 512 | `$6500-$66FF` |

The phase 1 prototype reserved 4096 bytes. The split candidate reserves 512 RAM
bytes and retains most executable code in flash. The integrated component also
stores the 512-byte gateway template at B3 `$86E0`, for 2272 payload bytes in
sector 8. Monitor discovery/protection lives in the A/B slots and verified E
launcher. MAINT 1.6 occupies RAM `$2000-$3DFA`, clear of the reservation.
The candidate ABI remains versioned; see the acceptance record for discovery.

## Flash layout proposal

Beta4 E contains 1726 launcher bytes, 1649 RST bytes, a 256-byte descriptor
table, a 16-byte capability area and a two-byte launcher seal. This leaves at
most 447 raw bytes across gaps/tail, subject to allocation boundaries. The
1760-byte RTC/I2C provider cannot fit there without moving or shrinking other code.
The reserved `$EF00-$EFFF` tail alone is only 256 bytes.

A separate RTC extension sector preserves the existing E interfaces:

| Region | Proposed ownership |
| --- | --- |
| B3 sector 8 | Optional RTC/I2C provider and verified RAM template |
| B3 sector 9 | Later explicit allocation |
| B3 A/B | Existing monitor slots |
| B3 C/D | Existing journals |
| B3 E | Launcher/RST interfaces, service bootstrap and full-sector seal |
| B3 F | Reset/recovery core and public facade |
| B1 sectors 8/9 | Relocated saved MAINT 1.6 record |

B3 sectors 8/9 previously held MAINT. The migration verifies a relocated MAINT
1.6 record in freshly backed-up B1 before reusing those B3 sectors. Normal
monitor and MAINT 1.6 operations protect B3 sector 8 and active service RAM.
The unchanged static MAINT 1.5 artifact still loads/runs/returns in the model;
it predates this ownership policy, so use the installed 1.6 for maintenance.

## Gateway and interrupts

The model gateway's `RG` descriptor is at `$6500`, with READ, STATUS, SET and
ACK at `$6504`, `$6507`, `$650A` and `$650D`. It preserves I/decimal state, stack
balance, the caller's PCR and the driver's VIA guarantees. All bank changes and
the return path execute in RAM. Its first-request CRC executes no provider code
before verification. First-call SET/ACK inputs survive private-state initialization.

B3 execution uses its existing hardware vector paths. Cross-bank calls in this
prototype require an NMI handler in RAM that preserves selection; an unsafe
flash handler is refused before remapping. A caller already in B3 can retain
its valid flash handler. IRQ is masked for the foreground call. The model injects
NMI during provider execution under these supported profiles. This is not a
general bank-aware NMI dispatcher. Unsupported cross-bank NMI profiles return
`$82` before mapping. Native RTC calls and calls from
interrupt handlers remain excluded.

## Integration requirements

1. Publish and clear versioned discovery across physical/software RESET,
   monitor reentry and older A/B slot selection without moving existing entries.
2. Bootstrap the RAM gateway from trusted/verified code. Invalid optional
   components must never supply executable bootstrap bytes before verification.
3. Protect configured RAM in M/L/RESTORE, launch checks and reported program
   limits. No overlapping S19 record may overwrite it; unrelated earlier records
   may remain applied under the existing loader contract.
4. Protect the backing flash component while registered, or invalidate cached
   verification before update/erase/removal and subsequent calls. The model
   proves revalidation after invalidation; integrated monitor/maintenance hooks
   now protect ownership and preserve initialized outage capture across HOLD.
5. Preserve MAINT/RST behavior through migration and verify both slots, recovery,
   absent RTC software and absent EDU hardware on both CPU types.

RTC SRAM/EEPROM remain deferred. They are not code storage, gateway scratch,
discovery state or prerequisites for activation. Future SRAM outage caching is
separate from this implementation.

## Build and proof

```text
python tools/build_v2_rtc.py
python tools/build_v2_rtc_split.py
python tools/test_v2_rtc_split.py
python tools/test_v2_i2c.py
```

The first command supplies the phase 1 I2C fixture dependency. The split builder
reads that source and binds every mutable symbol to RAM without editing it.
Outputs stay under `BUILD/v2-rtc-phase2-split`; no tool opens a serial port.
The report binds provider/gateway hashes and covers all four caller banks,
first-request checks and cached calls, SET/ACK initialization, absent/stuck
hardware, missing/corrupt components, NMI profiles, state preservation and
revalidation after invalidation.
The public-I2C report additionally covers a modeled second slave with RTC absent,
alternating bus/clock operations, reads/writes, repeated START and STOP/start,
page-crossing/max-length buffers, partial NACK progress, timeout, rejected memory
ranges and preservation of managed-device policy. Both reports bind the current
image hashes; hardware qualification is recorded separately below.

The integrated build adds `build_v2_rtc_kernel.py`, `build_bank_maint_rtc.py`,
`test_v2_rtc_kernel.py`, and a backup-bound modeled migration. Do not install
sector 8 over an existing MAINT record without the verified relocation plan.
See [integrated acceptance](STR8N_V2_RTC_PHASE2_2026-10-06.md),
[the overall direction](STR8N_V2_RTC_DIRECTION.md) and
[phase 1 acceptance](STR8N_V2_RTC_PHASE1_2026-10-06.md).
