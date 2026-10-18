> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Crypto status RAM display on 2604

On 2026-10-15 the owner requested seeing the status on 2604. The console client
was built, tested, loaded into ordinary RAM and run twice on COM5. No flash
installation, provisioning or clock-setting operation was performed.

At the existing B3 monitor, enter:

```text
G 2800
```

The actual board output was:

```text
CRYPTO STATUS (RAM)
Status:        Present
Device:        ATECC608B
I2C address:   $60
Revision:      00 00 60 03
Serial:        0123DE7CADBDB846EE
Configuration: UNLOCKED
Data/OTP:      UNLOCKED
Cleanup:       OK
```

COM5 was closed/released after the final report. The owner can reconnect their
terminal at 115200, 8-N-1 and use G 2800. The temporary program occupies
$2000-$2BDF, with entry $2800; loading another application can overwrite it.
It is not a saved flash program or a new monitor command. No key-slot contents
are displayed or read, and lock states do not establish provisioning readiness.

The overwritten RAM range was read twice and archived before staging. It is
deliberately left holding the utility so the owner can see and rerun it. The
previous RAM is retained at
`output/qualification/crypto-display-2604-2026-10-15/ram-prior.bin` for later
load-only restoration. Do not execute that backup as a program.

## Source and verification

- [Console client](../tools/v2-rtc/crypto-display.asm): 992 bytes at $2800.
- [Builder](../tools/build_v2_crypto_display.py): binds to the existing qualified
  1,811-byte adapter and creates a dense RAM-only package.
- [Display tests](../tools/test_v2_crypto_display.py): five tests pass, executing
  the client, adapter and shared provider with a digital bus model. They cover
  A/B identification, unknown revision, absent/unavailable service, partial
  fields, cleanup errors, EDU OFF and invalid discovery. OFF/invalid discovery
  neither touches the bus nor reads reclaimed service RAM.
- [Board display tool](../tools/show_v2_crypto_board.py): checks the exact USB
  identity, uses the shared serial lease and the tested load-only uploader,
  archives RAM, explicitly configures $60/8 MHz, verifies the first call's
  result/validity/cleanup and released lock, then prints a second live report
  as its last board command. Failure after staging attempts load-only RAM
  restoration; success intentionally leaves the utility available.

The client checks service discovery before calling the existing read-only RTC
STATUS entry to revalidate the shared provider after HOLD, then calls the
crypto engine. It reports unknown fields and field/cleanup errors explicitly.
The actual serial transcript and successful report are in
`output/qualification/crypto-display-2604-2026-10-15/`.

This adds a standalone RAM status display. Resident placement, saved-program
packaging and broader physical qualification remain separate work. See the
[previous 2604 qualification](STR8N_V2_CRYPTO_2604_2026-10-14.md) for the
adapter evidence and initial loader-incident recovery.
