> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Crypto status offline engine checkpoint

Recorded 2026-10-14 after the owner authorized offline implementation and revised
the earlier board-availability restriction. No boards accessed, no installed
firmware changed and no resident command or public service capability added.
ADC remains excluded.

Later checkpoint: the [offline adapter](STR8N_V2_CRYPTO_ADAPTER_OFFLINE_2026-10-14.md)
now binds this engine to modeled VIA/I2C transfers and shared ownership. The
standalone engine build below retains its default refusing hooks. Board-facing
behavior is implemented in the separate candidate but remains physically
unqualified; there is still no resident command or installation.

The later [2604 checkpoint](STR8N_V2_CRYPTO_2604_2026-10-14.md) records explicit
608B recognition and physical RAM tests. The current A/B engine is 778 bytes
with 12 engine tests; the 764-byte measurements below describe the earlier
A-only checkpoint and remain historical.

## What is implemented

[crypto-status.asm](../tools/v2-rtc/crypto-status.asm) is a 65C02 subroutine engine
linked at $2000 for model testing. It validates the wake response and recognizes
the documented ATECC608A revision 00 00 60 02. Other revisions are returned raw
with Unrecognized device; revision alone does not establish factory variant.

The immutable command table contains Info revision and four four-byte Read
commands restricted to configuration-zone words 0, 2, 3 and 21. They provide
serial bytes [0:3], [8:11], [12] and LockValue [86]/LockConfig [87]. Only those
public fields are extracted. No provisioning or persistent-write command exists
in this engine. Packet lengths/counts and CryptoAuthentication CRC are checked
before consuming data. A command status packet never counts as identity data.

There is one wake attempt and at most eight receive attempts per command.
Only Not responding is retried; malformed responses and bus/device errors are
not retried. Identification survives later public-field errors, and incomplete
serial data is cleared. Cleanup errors are separate from the primary result.
Every path after a successful claim attempts Sleep and then releases ownership;
failed discovery/claim paths do neither.

This is the protocol engine, not a functioning hardware probe. Board-facing
wake, I2C transactions, timed waits, shared-lock integration and command display
are still to be implemented. The default HAL_CHECK returns Service unavailable;
all bus hooks refuse use. No old BUILD probe is reused or treated as evidence.

## Internal adapter contract

This is a private, unversioned offline interface, not an addition to the public
I2C ABI. START is called with JSR in foreground 65C02/816 emulation mode. It
preserves stack balance and I/D flags; A returns RESULT, X/Y and other flags are
unspecified. It uses no zero page. IRQ is masked within the operation; callbacks
must preserve that state and decimal-clear execution. NMI/shared-service and
maximum IRQ-off duration require integration review. The engine is not reentrant.

The current linked image, including command constants and mutable state, occupies
764 bytes ($2000-$22FB). It has no permanent resident allocation. This footprint
excludes the future adapter, console display and shared-service integration.

Callbacks return A=0 on success or one of the result codes below. Scratch X/Y
and arithmetic flags may change. The protocol engine calls:

| Hook | Required future behavior |
| --- | --- |
| HAL_CHECK | Validate active EDU mode and current service discovery; no bus access on refusal |
| HAL_CLAIM | Acquire shared bus/VIA ownership; failed claim leaves existing owner untouched |
| HAL_WAKE | Emit the part-appropriate waveform once and wait recovery, under ownership |
| HAL_SEND | Send exactly eight TXBUF bytes, including command word address 03, then STOP |
| HAL_WAIT | One bounded delay before each command receive attempt |
| HAL_RECEIVE | Receive one complete response, set actual RXLEN, write at most seven RXBUF bytes |
| HAL_SLEEP | Attempt Sleep/STOP cleanup, restore saved bus/VIA state even on error |
| HAL_RELEASE | Release acquired ownership unconditionally; no failure return |

HAL_RECEIVE must bound the count before buffering, complete appropriate NACK/STOP
handling, and report malformed/oversize/truncated responses without overrunning
RXBUF. Return Not responding only for a no-response condition eligible for
polling; retain low-level bus phase/error details in the adapter's own result
area. Never treat a malformed packet as a retryable NACK.

Before binding callbacks to hardware, confirm address/variant and timing from
the fitted EDU and matching specifications. No address is assumed by this
engine. Define elapsed-time bounds at supported CPU speeds, shared-lock behavior,
stuck-bus handling and safe continuation after a public-field transfer failure.
Eight polls alone is not a wall-clock timeout contract. Wake/Sleep can disturb
volatile crypto sessions, so exclusive ownership must cover the whole operation.

## Results

| Field | Meaning |
| --- | --- |
| RESULT | 0 Present; 1 Disabled; 2 Service unavailable; 3 Busy; 4 Not responding; 5 Bus error; 6 Invalid response; 7 Device error; 8 Unrecognized device |
| CLEANUP_ERROR | Sleep/restore error, independent of RESULT; zero when successful or not attempted |
| VALID | Bit 0 supported revision, bit 1 complete serial, bit 2 both lock encodings valid |
| REVISION | Four raw revision bytes; trust identity only when VALID bit 0 is set |
| SERIAL | Nine bytes, cleared if any serial read fails |
| LOCKS | Raw LockValue, LockConfig; 00 locked, 55 unlocked; require VALID bit 2 |
| FIELD_ERRORS | Four codes for serial words 0/2/3 and lock word 21; FF means not attempted |
| DEVICE_STATUS | Last CRC-valid command status byte; consult associated errors, since zero can also be an unexpected status-only response |

The report consumer must display field errors and CLEANUP_ERROR alongside any
Present result. Presence does not prove provisioning or cryptographic health.
Not responding does not prove physical absence. Repeated calls clear prior
results; there is no cached presence state.

## Offline verification

Run with the repository's Python/py65 environment and WDC tools on PATH:

```text
python tools/build_v2_crypto_status.py
python tools/test_v2_crypto_status.py
```

Generated output is isolated in BUILD/v2-crypto-status-offline. The manifest and
test receipt bind to the linked image hash and explicitly record no hardware
qualification. The linked default is unavailable; generated assembler/linker
files are model artifacts, not approved board loaders or installation packages.

Eleven tests execute the linked machine code through scripted HAL callbacks.
They cover success, disabled/unavailable/busy refusal, wake failure, corrupt
responses, all 56 single-bit revision-packet corruptions, unrecognized revision,
device status packets, partial public fields, invalid lock encodings, eight-poll
exhaustion and last-attempt success, send/wait/cleanup errors, stale-result
clearing, and I/D and stack preservation. They check that zero page, I/O, flash,
gateway/descriptor memory and unrelated upper RAM are untouched by the engine.

These tests do not exercise physical I2C, wake timing, RTC coexistence, caller
bank switching, shared-lock implementation or hardware persistence. Qualification
of those remains pending, as does resident placement and command integration.

## Protocol references

- [Microchip Info revision](https://onlinedocs.microchip.com/oxy/GUID-E8090678-FB6F-4FDB-B2FD-C019408533ED-en-US-2/GUID-4FC46CBF-F416-4833-8821-BE9C98F0D739.html).
- [Microchip configuration-zone Read](https://onlinedocs.microchip.com/oxy/GUID-E8090678-FB6F-4FDB-B2FD-C019408533ED-en-US-2/GUID-F88469C4-8390-49C8-9815-06FDBED5CAE2.html).
- [Microchip CryptoAuthLib command constants](https://github.com/MicrochipTech/cryptoauthlib/blob/main/lib/calib/calib_command.h).
- [Detection/status plan](STR8N_V2_CRYPTO_DETECTION_STATUS_PLAN_2026-10-14.md).
