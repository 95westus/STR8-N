> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Crypto status adapter offline checkpoint

Recorded 2026-10-14. The owner authorized adapter implementation and offline
testing; no boards are available. No board access, flash writes, installation,
resident command or public ABI change occurred. ADC remains excluded.

Subsequent [2604 RAM qualification](STR8N_V2_CRYPTO_2604_2026-10-14.md) revealed
an ATECC608B. Explicit support for its documented revision increases the complete
candidate to 1,811 bytes, with 15 adapter and 12 engine tests. The sizes, hash,
timings and coverage below describe the original A-only offline checkpoint.

## Candidate and scope

[crypto-adapter.inc](../tools/v2-rtc/crypto-adapter.inc) binds the existing
[status engine](../tools/v2-rtc/crypto-status.asm) to VIA PA0/SCL and PA7/SDA.
It implements wake, complete command transmission, count-bounded reception,
poll delays, Sleep cleanup and shared ownership. The builder extracts INIT,
RESTORE and bit-level primitives directly from the existing RTC source; it
does not modify the RTC or public I2C driver.

The complete RAM candidate is 1,797 bytes at $2000-$2704, including engine,
adapter, command constants and mutable data. It uses no zero page and changes
no memory reservation. It does not switch flash banks or modify PCR. No monitor
display or resident placement is included. The standalone 764-byte engine and
its refusing hooks remain available as a separate build.

Candidate SHA-256:
`cb29990ab847fbadec091e68e751f4a0aadfccb000acb8270a94132410ff2902`.

## Discovery, configuration and ownership

The candidate is disabled by default. CA_ENABLE must be A5, CA_ADDRESS must be
an explicitly selected seven-bit target, and CA_MHZ must be 1, 2, 4 or 8.
Tests use address 60; that is a model input, not a newly verified fitted-board
address. Addresses outside 08-77 and managed EEPROM/RTC addresses 57/6F are
rejected. Confirm the actual crypto address and CPU frequency before any future
board prototype is prepared. There is no address scan or address rewrite.

The adapter first checks the active EDU latch. OFF returns Disabled without
touching reclaimed service RAM or bus pins. ON requires SV format 1, I2C
capability, gateway $6500, application end $64FF, active reservation FF, the
I2 format-1/count-1 signature and the existing code-verified ready bit.
It never calls the gateway to activate or validate a missing service.

This is a private adapter pinned to the current service layout, not a portable
public lock API. It imports SVC_BUSY at $6660 and SVC_DRIVER_BUSY at $6669
from the current service-equate source. It refuses either busy flag, claims
SVC_BUSY with IRQ masked, and holds it through wake, polling and cleanup.
The public gateway is never called internally while that lock is held. Its
existing busy check protects RTC/I2C/SPI clients from entering concurrently.
Any future service-layout change requires renewed adapter review.

Both bus pins must already be released and idle before the adapter changes
their latch or direction. Failed preflight releases its lock without bus writes.
The adapter preserves unrelated VIA direction and driven output values. It
drives bus lines low or releases them, never drives high. After a failed STOP,
it explicitly releases both bus pins before restoring the observed port state.

Foreground 65C02 / 816 emulation contracts still apply. IRQ remains masked for
the complete operation and I/D flags and stack balance are restored. The model
includes an RTI-only NMI handler and a nested gateway refusal; it does not qualify
arbitrary NMI handlers. NMI code must not access this bus or corrupt adapter
state. Native mode, interrupt clients and multiple bus masters remain unsupported.

## Transfers, failures and diagnostics

The engine still sends only Info revision and four public configuration-word
reads. Each transaction uses a complete packet and STOP. Reception reads the
count before indexing the seven-byte buffer and accepts only counts 4 or 7.
An invalid count causes one discard byte with NACK followed by STOP; no
untrusted count controls a buffer index. The last normal response byte is
NACKed. The engine then checks packet count, CRC and expected payload form.

One wake attempt is followed by recovery delay. Command reads have at most
eight polling attempts. Only an address NACK with successful STOP is retryable.
Payload NACK, malformed framing and clock/STOP failure latch CA_BROKEN, preventing
later command traffic. Sleep cleanup is still attempted, followed by VIA restore
and lock release. An address NACK followed by STOP timeout returns Bus error,
not a retryable Not responding result.

RESULT, VALID, FIELD_ERRORS and CLEANUP_ERROR retain their
[engine meanings](STR8N_V2_CRYPTO_STATUS_OFFLINE_2026-10-14.md#results).
After identity is established, a later transport failure can leave RESULT=Present
with field errors: a future display must show those errors and cleanup status.
The adapter adds:

| Field | Meaning |
| --- | --- |
| CA_FAULT_CODE | First nonzero raw transport event: 1 not idle, 2 NACK, 3 timeout, 9 invalid count |
| CA_FAULT_PHASE | Phase of that event: 0 preflight, 1 write address, 2 payload, 3 read address, 4 read data, 5 STOP, 6 wake |
| CA_STOP_ERROR | 3 if any STOP failed, otherwise zero |
| CA_BROKEN | Later normal command traffic is refused after a fatal transport fault |

Diagnostics reset on every invocation, including discovery/configuration refusal.
The first event may be an ordinary busy-poll NACK even when the final result
succeeds; consult the final result and field/cleanup errors. Diagnostics do not
assert physical absence or recovery from a stuck line.

## Cycle-based timing evidence

The generated adapter's delay loop scales with the explicit MHz setting. The
digital model measures linked 65C02 instruction cycles, including generated
long branches. Microchip specifies at least 60 us wake-low and 1.5 ms recovery,
or 20 ms recovery when power-on self-test is enabled. The candidate delays
cover the 20 ms case in these modeled profiles.
[Microchip timing table](https://ww1.microchip.com/downloads/aemDocuments/documents/SCBU/ProductDocuments/DataSheets/ATECC608A-CryptoAuthentication-Device-Summary-Data-Sheet-DS40001977B.pdf).

| Configured MHz | Wake low, us | Recovery to first START, ms | Minimum poll delay, ms | Normal success, ms | All commands succeed on eighth poll, ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 152 | 26.973 | 6.746 | 177.242 | 463.692 |
| 2 | 132 | 24.687 | 6.173 | 113.880 | 355.105 |
| 4 | 122 | 23.543 | 5.887 | 82.197 | 300.810 |
| 8 | 117 | 22.972 | 5.743 | 66.355 | 273.661 |

These are ideal digital-bus scenarios, not physical timing qualification or
universal wall-clock deadlines. Each SCL release retains the existing finite
255-poll bound. Clock stretching and NMI activity can add latency beyond the
table; the MHz setting must match the actual CPU clock. The complete IRQ-off
interval and physical timing still require board review before resident use.

## Verification and remaining gates

```text
python tools/build_v2_crypto_adapter.py
python tools/test_v2_crypto_adapter.py
python tools/test_v2_crypto_status.py
```

Output is isolated under BUILD/v2-crypto-adapter-offline. The builder also links
unmodified RTC and shared-gateway fixtures for testing. The manifest binds source,
candidate and fixture hashes; the test receipt records cycle measurements and
explicitly states that no hardware/electrical qualification occurred.

Fourteen adapter tests pass. They execute real linked adapter/engine machine
code and digital START/STOP, address, ACK/NACK and byte transfers. Coverage
includes four clock profiles and I/D combinations; default/configuration and
discovery refusals; preexisting shared/driver locks; absent devices; stuck and
externally driven pins; payload NACK; clock and STOP faults; malformed counts
and CRC; polling exhaustion and eighth-attempt success; Sleep failure;
diagnostic reset; gateway reentry refusal; and alternating crypto/RTC calls.
Crypto works in the model without an RTC, and RTC reads still work without
crypto. The existing eleven engine tests also pass.

The model checks buffer/state boundaries, no zero-page/flash/gateway-request
changes, preserved VIA outputs, open-drain behavior and lock release. The actual
public gateway returns Busy during crypto ownership without changing bus pins.
The RTC coexistence fixture performs a normal read without changing registers.

Physical pull-ups, rise times, electrical contention, actual command execution
times, incidental ATECC608A wake/corruption during other slow I2C traffic,
retained provisioning and real board clock accuracy are not modeled. In
particular, digital RTC coexistence is not proof of physical coexistence.
The fitted address/variant, CPU types, timing, NMI behavior and retained-state
preservation remain board qualification gates. No loader or installation path
has been added; monitor status display and resident placement remain pending.

## References

- [Detection/status plan](STR8N_V2_CRYPTO_DETECTION_STATUS_PLAN_2026-10-14.md).
- [Shared I2C contract](../tools/v2-rtc/I2C_API.md).
- [WDC EDU wiring](https://www.wdc65xx.com/wdc/documentation/W65C02EDU.pdf).
- [Microchip ATECC608A/B differences, including incidental wake behavior](https://onlinedocs.microchip.com/oxy/GUID-91D4A0CB-3AFD-443D-B23E-4D22AD0B49DB-en-US-1/GUID-46FD2FED-DEA0-4C69-B301-DDD5359198AD.html).
