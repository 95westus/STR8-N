# RTC tick alignment board routine

This temporary RAM program supplies observation, delay calibration, and bounded
seconds-register phase correction for the [host driver](../../tools/rtc_phase_align.py).
The [paper](../../docs/RTC_TICK_ALIGNMENT.md) describes the method and the
[saved results](../../docs/RTC_TICK_ALIGNMENT_RESULTS_2026-11-01.md) record its
four-board validation.

`phase.asm` is the complete WDC assembly source, including the VIA/I²C driver.
Its expanded branches are retained exactly as assembled for the validated image.
It uses 65C02 instructions, also qualified in 65C816 emulation. It assumes the
installed monitor's console entry points at `$7E67` (return), `$7E6D` (output),
and `$7E70` (input), and VIA registers `$7FCF` and `$7FC3`.

## Build and verification

From the repository root, with Python and WDC02AS/WDCLN installed:

```text
python -B tools/build_rtc_phase.py
python -B tools/test_rtc_phase.py
python -B tools/test_rtc_phase_host.py
```

The model test requires py65 and the pinned py65816 model described in the
[operating notes](../../docs/RTC_TICK_ALIGNMENT.txt). All three commands are
offline and open no board ports. Use `--out` for a fresh build directory and
pass that directory as `--build` to the tests and host commands.

The default output is `BUILD/rtc-phase/`; existing output directories are
refused. The builder requires the qualified 1077-byte image SHA-256
`28c6ad2421d2d6425dee27605dca5df3d3f58e4efcfb4766cf0f4fffc8550b92`
and the complete symbol map in `tests/baselines/rtc-phase.json`.
The host additionally requires all 30 passing CPU/I²C model cases in
`proof.json`. Rebuilding never reuses the historical `BUILD/rtc-phase-r3/`
artifacts or the older RTC collector source.

## Host and board interface

The host backs up and verifies `$2000–$2434` before loading this image. No
zero-page storage is used. The monitor's normal stack and console activity
are outside the borrowed-block preservation claim.

| Symbol | Role |
| --- | --- |
| `CALIBRATE` | Run `TICKS` delay iterations without RTC writes. |
| `OBSERVE` | Stream RTC snapshots, one per host handshake. |
| `PAUSE_CLOCK` | Check guards, stop the oscillator, wait, and restart autonomously. |
| `KEY` | Two-byte `PH` authorization key, consumed before correction. |
| `TICKS` | Little-endian delay count, restricted to 1 through 16383. |
| `EXPECTED` | Expected control and trim bytes, compared before correction. |
| `ADJUST` | 0 preserves the second; 1 adds one second, refusing second 59. |
| `STATUS` | 0 on success; bus errors or `$E1` refusal / `$E2` restart error otherwise. |
| `RAW` | Nine RTC registers followed by eight power-fail timestamp bytes. |

Each operation emits `!` and waits for `r`. Replies contain `@`, one status
byte, and 17 raw bytes. Observation repeats until a handshake byte other
than `r` returns to the monitor. The host uses `q` to end observation.
The host reads all entry and variable addresses from the verified symbol map.

The only RTC write transaction has a fixed device and register: MCP7941x
RTCSEC at address zero. Correction requires a running oscillator, a clear
power-fail latch, disabled alarms, and matching control/trim bytes. After
clearing ST, the routine performs a finite stop wait and bounded delay,
then attempts restart without further host input. Persistent bus failure
can prevent restart and is reported as an error.
