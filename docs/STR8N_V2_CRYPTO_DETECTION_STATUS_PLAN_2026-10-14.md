> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# STR8-N optional crypto detection/status plan

Recorded 2026-10-14. Updated by owner authorization the same day: offline
implementation, test-code development and feature builds are now permitted.
No boards are currently available. Physical qualification and installation
remain deferred until boards are available. No working hardware crypto support
is claimed. See the [offline engine checkpoint](STR8N_V2_CRYPTO_STATUS_OFFLINE_2026-10-14.md).
The later [offline adapter checkpoint](STR8N_V2_CRYPTO_ADAPTER_OFFLINE_2026-10-14.md)
adds modeled wake, bus transfers and shared ownership; physical qualification
and installation remain pending.

Later on 2026-10-14, the owner made 2604 available for RAM-only qualification.
It reports ATECC608B revision 00 00 60 03, so the engine now explicitly accepts
the documented ATECC608A and ATECC608B revisions. Other revisions still return
Unrecognized device. See the [2604 checkpoint](STR8N_V2_CRYPTO_2604_2026-10-14.md).
This supersedes the blanket no-boards statement above for 2604; other physical
coverage and any installation remain pending.

## Purpose and scope

Identify the optional EDU ATECC608A/B and report observed availability without
changing keys, provisioning, configuration, retained storage or RTCC state.
The owner's boards have crypto fitted; other EDU boards may omit it. Report
crypto availability independently of RTCC and SPI SRAM availability.

Start with an explicit manual operation. `CRYPTO STATUS` is illustrative syntax,
pending command-space and placement review. Automatic boot probing is deferred.
ADC detection is excluded from this work; no ADC detection task is planned.

Report validated device revision and, where supported by the confirmed part,
public serial number and configuration/data lock states. Lock state does not
prove that useful keys are provisioned. Identification is not cryptographic
authentication or a complete health test.

Exclude provisioning, persistent writes, locking, address changes, secret-slot
reads, key generation, signing, random generation, hashing and image validation.
Do not dump configuration or key-slot contents as a status feature.

## Existing interface and design decisions

The [shared I2C interface](../tools/v2-rtc/I2C_API.md) provides bounded transfers,
error phases and caller-owned buffers. Preserve its public ABI, service
discovery, EDU ON/OFF behavior and RAM reservations. Hardware absence does not
reclaim software-reserved RAM.

Info and individual public configuration reads fit the current 64-byte limit.
Use small supported configuration reads. The larger-packet path recorded in
[SPI Phase 1](STR8N_V2_SPI_PHASE1_2026-10-07.md) can remain deferred.

Explicit wake handling is required. Public I2C rejects address zero and does
not automatically wake devices. Design a crypto adapter that owns the entire
wake/command/read/cleanup sequence under shared bus/VIA ownership. Internal
transfers must not reacquire the same lock. Do not weaken public validation or
add automatic wake traffic to ordinary RTC/I2C operations.

Before coding, confirm the fitted variant, expected seven-bit address, public
field layout, revision interpretation and timing against EDU documentation and
matching Microchip specifications. Factory variants can differ in address;
do not assume one address identifies all variants. Do not use a general bus
scan or rewrite an address to make detection work.

Measure flash, RAM, zero-page and stack costs before choosing placement or final
syntax. Preserve existing foreground CPU/bank/interrupt contracts and unrelated
VIA state. No permanent large packet buffer is required by this initial scope.

## Proposed operation

1. Check active EDU mode and validated I2C software discovery before bus access.
   Disabled or unavailable services return immediately.
2. Acquire shared ownership and check bus usability. Return Busy without
   disturbing an active operation if ownership cannot be acquired.
3. Generate the documented wake waveform, wait its recovery interval and read
   the wake response at the expected address.
4. Validate wake-response length, status and CRC. An ACK alone is insufficient;
   a generic wake response alone does not identify an ATECC608A.
5. Issue Info in revision mode. Bound execution waits/polling, then validate
   framing, CRC, device status and revision interpretation.
6. Read only public configuration blocks needed for serial and lock states.
   Validate each response. If identification succeeds but a field read fails,
   retain identification and report that field as unknown with its error.
7. Attempt documented Sleep cleanup where appropriate, restore bus/VIA state
   and release ownership on every exit. Preserve the primary error and report
   cleanup failure separately. Attempted cleanup does not prove bus recovery.

Wake/Sleep affect volatile device state, so this operation must not interrupt
another crypto exchange. Persistent keys, configuration and lock states must
remain unchanged.

Specify finite maximum wake attempts, command polls and total operation duration
before implementation. Document timing at each supported CPU speed. The current
255 clock-poll bound is not a millisecond timeout guarantee. No endless retry,
automatic bus-clear pulses, RTC writes or storage access is permitted.

## Results

| Result | Meaning |
| --- | --- |
| Disabled | Active EDU mode is OFF; no bus access |
| Service unavailable | Required software discovery/integrity failed |
| Busy | Another operation owns the shared service |
| Not responding | No valid response at the expected address within attempt limits |
| Bus error | Bus idle, clock or STOP failure; retain phase/details |
| Invalid response | Bad length, framing or CRC |
| Device error | Valid device error packet; preserve status code |
| Unrecognized device | Valid response but revision does not establish support |
| Present | Supported revision identified; public-field results reported separately |

Do not label Not responding as Not fitted: address, wiring, timing or device
faults can produce the same observation. Do not equate Present with readiness
for signing or other crypto functions. Prefer a fresh manual probe; any future
cached result must be labeled as a prior observation and invalidated at RESET.

Failure must return control to the monitor and preserve available RTCC, flash,
SPI SRAM and recovery services. A physically stuck shared I2C bus may also
prevent RTCC communication; report that shared fault honestly while leaving
the monitor and unaffected services usable.

## Implementation and qualification sequence

1. Confirm part/address/timing, review current placement and specify request,
   results, timing limits and command presentation before coding.
2. Implement the smallest isolated adapter/status client and model tests.
   Cover success, asleep device, no response, Busy, EDU OFF, missing software,
   truncated/bad-CRC responses, device errors, unknown revision, partial field
   failures, bounded polling and cleanup failures. Assert that no persistent
   write/provisioning commands are emitted.
3. Check caller-bank/VIA/state preservation, unchanged public I2C behavior and
   RAM reservations, plus alternating RTC/SPI/crypto operations. Models do not
   qualify physical wake timing or electrical behavior.
4. Qualify a reversible RAM prototype on physical boards before considering
   resident integration. Cover supported CPU types/speeds, repeated status,
   present/absent/unresponsive devices and mixed optional-component cases.
   Use safe fixtures for absence/fault tests without disturbing provisioning
   or retained data. Verify EDU OFF causes no crypto bus traffic.
5. Capture response bytes, decoded fields, measured wake/response timing,
   finite failure durations and state-preservation evidence. Compare permitted
   public configuration/lock fields before and after; keep secrets out of logs.
6. Review evidence and measured placement before a separate installation
   decision. Bind receipts to exact candidate hashes and board transcripts.
   Any later flash installation requires normal backup and readback checks.

Acceptance requires validated identification on fitted hardware, honest bounded
failure reporting, persistent-state preservation and unaffected-service checks.
Offline implementation may proceed while boards are unavailable; physical
qualification and installation remain pending. Offline test success does not
complete the TASKS feature item.

## References

- [Optional-component backlog](../TASKS.md#optional-edu-component-detection-recorded-2026-10-14).
- [Microchip ATECC608A summary datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/SCBU/ProductDocuments/DataSheets/ATECC608A-CryptoAuthentication-Device-Summary-Data-Sheet-DS40001977B.pdf).
- [Microchip Info revision identification](https://onlinedocs.microchip.com/oxy/GUID-91D4A0CB-3AFD-443D-B23E-4D22AD0B49DB-en-US-1/GUID-46FD2FED-DEA0-4C69-B301-DDD5359198AD.html).
- [Microchip wake-token description for the TFLXTLS variant](https://onlinedocs.microchip.com/oxy/GUID-E8090678-FB6F-4FDB-B2FD-C019408533ED-en-US-2/GUID-1E4F722E-9D9B-4EEA-836D-94E8913F0B03.html).
  Confirm applicability to the fitted variant before selecting constants.
