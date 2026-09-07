# STR8-N / HIMON / ASM LED status proposal and implementation record

Status LEDs are useful only when their owner and meaning are predictable. The
W65C02SXB/EDU PIA Port A is therefore treated as an explicitly owned,
full-byte display. STR8-N, HIMON, ASM, a RAM flash worker, and a user
application may all use the LEDs, but only the current owner writes them.

Status: the minimal STR8-N slice and the first FTDI host-presence follow-on are
implemented, host-validated, and board-accepted in STR8-N v1.31 on COM4 on
2026-09-06. The board confirmed the active-high four-green/four-red mapping,
`$00`, `$01`, `$21`, `$41`, `$43`, and `$F0`, worker mutation and return
behavior, handoff release, and application ownership across public raw console
calls. The STR8-N `$07`/`$0B` activity slice is implemented, host-qualified,
and board-accepted on the same date. HIMON, ASM, and detailed error patterns
remain proposed follow-on work.

## Ownership and layering

| Execution context | Owner | Required behavior |
| --- | --- | --- |
| Reset, STR8-N menu, recovery, installer | STR8-N | Publish STR8-N state |
| HIMON command loop | HIMON | Publish the same normal console states |
| ASM execution | ASM | Publish assembly state, then restore HIMON state |
| Flash erase/program/verify interval | RAM worker | Override the display with `$F0` |
| User application or another bank | Application | May use any Port A pattern or function |
| Public `CHARIN`, `CHAROUT`, `CHAR_READY` | No LED owner | Perform raw I/O without changing Port A |

The PIA write primitive belongs at the hardware layer. Policy does not.
STR8-N, HIMON, and ASM use private semantic wrappers or explicit state
transitions around raw console I/O. The public STR8-N console ABI remains free
of LED side effects, so a RAM application can call it while keeping its own
display.

Each owner writes a complete byte. There is no cross-owner set/clear shadow
byte and no interrupt or background monitor that can overwrite a new owner's
display. On a successful program or bank handoff, system firmware writes
`$00` and stops touching the PIA. The new program may immediately replace that
value. If it voluntarily adopts this contract, it should reassert its own
state on entry.

The RAM flash worker is the one deliberate preemption. It writes `$F0`
immediately before the first operation that can alter flash, holds it through
the last required verification, and returns control only after Bank 3 is
visible again. The worker restores `$01` before returning; the STR8-N command
loop later publishes `$21` or `$43` when it waits again. The worker must not
call a ROM LED routine while flash banks are switched.

## Normal bit contract

The proposed physical mapping is four active-high green LEDs in the low
nibble and four active-high red LEDs in the high nibble:

```asm
LED_G_RUN       EQU     $01
LED_G_HOST      EQU     $02
LED_G_RX        EQU     $04
LED_G_TX        EQU     $08

LED_R_FAULT     EQU     $10
LED_R_NO_HOST   EQU     $20
LED_R_RX_WAIT   EQU     $40
LED_R_TX_WAIT   EQU     $80
```

Normal states are composed from these flags. `G_HOST` and `R_NO_HOST` are
mutually exclusive, as are `G_RX`/`R_RX_WAIT` and `G_TX`/`R_TX_WAIT`.
Activity remains latched until the next meaningful state; a single
instruction-width pulse would not be visible. `R_FAULT` can accompany green
bits when the firmware is still running and recovery remains available.

| Value | Normal meaning |
| ---: | --- |
| `$00` | Display released; no system-firmware owner |
| `$01` | Firmware running; host state not established or not applicable |
| `$21` | Running and waiting for the FTDI host |
| `$03` | Running, FTDI host present, idle |
| `$41` | Running and waiting for input; host state not sampled |
| `$43` | Running with host present, waiting for input |
| `$07` | Running with host present, receiving |
| `$83` | Running with host present, blocked waiting for output space |
| `$0B` | Running with host present, transmitting |
| `$0F` | Running with host present, bidirectional transfer active |
| `$13` | Recoverable fault; console remains available |
| `$53` | Recoverable input fault; waiting for corrected input |

FTDI host presence means the active-low PWE# input was sampled asserted. It
does not prove that a particular terminal application is open. The current
owner samples it when changing semantic state or entering a blocking wait;
there is no autonomous enumeration monitor.

## Exclusive red codes

With all green LEDs off, the high nibble is an exclusive stopped or
exceptional code rather than a combination of normal flags.

| Value | Exceptional meaning |
| ---: | --- |
| `$10` | BRK, debugger stop, or generic stopped fault |
| `$20` | Startup stopped without a usable host |
| `$30` | Image, signature, or validation failure |
| `$40` | Input format or checksum failure |
| `$50` | Protected address or invalid range |
| `$60` | Unresolved import, symbol, or link failure |
| `$70` | Flash erase failure |
| `$80` | Flash program failure |
| `$90` | Flash verification failure |
| `$A0` | Application returned unexpectedly |
| `$B0` | RAM, vector, or persistent-state failure |
| `$C0` | Operator abort awaiting acknowledgement |
| `$D0` | Recovery or maintenance required |
| `$E0` | Fatal internal error |
| `$F0` | Flash mutation active; do not reset or interrupt power |

These detailed failure codes are a vocabulary, not a requirement that the
first implementation detect every condition. A component must not display a
more specific code than it can support with an existing, reliable result.

## Implemented minimal first slice

The first implementation proves ownership and the safety-critical override
with only four states:

1. Reuse the existing PIA initialization and publish `$01` once STR8-N owns
   the display.
2. Publish `$41` immediately before STR8-N's main blocking command wait. This
   deliberately makes no PWE# claim.
3. The RAM worker publishes `$F0` at the shared flash-unlock boundary and
   retains it through verification. After restoring Bank 3 it publishes
   `$01` before returning; the command loop later publishes `$41`.
4. Publish `$00` immediately before a successful HIMON, guest-bank, or user
   application handoff. No subsequent STR8-N console service may change it.

This slice does not add FTDI enumeration, per-byte RX/TX activity, error-code
classification, animation, a public LED ABI, or a persistent shadow byte. It
also does not change the behavior of the public raw console entry points.
The linked resident is 3,331 bytes at `$F000-$FD02`; the worker is 608 bytes at
`$0200-$045F` and stored at `$FD50-$FFAF`. The combined 33-byte growth leaves
77 erased bytes at `$FD03-$FD4F`, above the enforced 64-byte minimum. The
41-byte public bank-selector prefix remains `$0200-$0228`.

The host-built canonical top BIN SHA-256 is
`51F84BB7E195882F96C684054947FB25986230546967A549C9EE55F8CEF5C248`.
The worker S19 SHA-256 is
`CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713`.

`make all` passes, including layout, public-console byte guards, RAM-load and
range contracts, promotion identity, 1,560 linked parser cases, and explicit
checks for each compiled LED boundary. The 2026-09-06 board run proved:

- the provisional color order and polarity;
- `$41` at the STR8-N input wait;
- `$F0` throughout a real guarded erase/program/verify interval;
- restoration after both successful and failed worker returns;
- `$00` at handoff; and
- an application-defined Port A pattern survives calls to public
  `CHARIN`/`CHAROUT`.

The worker probe programmed and verified `$A5` across scratch sector B2:8,
erased and verified all 4096 bytes back to `$FF`, checked `$01` after both the
successful path and a write-preflight failure, and then used Bank Maintenance
to prove B2 remained fully erased and D2 remained empty. B1:F stayed the
protected B3:F backup. The first all-`$FF` probe correctly performed no flash
unlock because the worker detected an already-erased sector; the accepted
dense-pattern rerun is the mutation proof. See the
[board-test report](LED_STATUS_BOARD_TEST_2026-09-06.md) and retained
[transcript](LED_STATUS_BOARD_TRANSCRIPT_2026-09-06.txt).

## Implemented host-presence follow-on

The next slice samples the FTDI PWE# input on VIA Port B bit 5 immediately
before the private STR8-N command wait. PWE# is active low. A configured FTDI
host therefore changes the former unsampled `$41` wait to `$43`; PWE# high
publishes `$21`. The public raw console entry points remain byte-identical and
LED-neutral. The check does not run in an interrupt or background task, so a
host transition during an existing blocking wait appears on the next command
wait.

This follow-on added 12 resident bytes and did not change the worker. That
resident was 3,343 bytes at `$F000-$FD0E`; the worker remained 608 bytes
at `$0200-$045F` and stored at `$FD50-$FFAF`. The erased margin is 65 bytes at
`$FD0F-$FD4F`, one byte above the enforced 64-byte minimum. The 41-byte public
bank-selector prefix remains `$0200-$0228`.

The board-accepted host-presence top BIN SHA-256 is
`3E1F63035C3CA63C73830AD628D89B8C5B591F6768CA3E80788097928A65C015`.
The unchanged worker S19 SHA-256 is
`CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713`.

The guarded updater installed and verified this exact top image. The operator
observed `$43` at the installed STR8-N prompt. A 17-byte RAM probe using the
same predicate then showed `$43`, changed to `$21` when Windows disabled the
FTDI USB Serial Converter, and returned to `$43` when the device was
re-enabled. This proves the PWE# polarity and both values on the board; the
installed `$21` branch is additionally guarded by an exact-byte host check.
See the [follow-on board report](LED_HOST_PRESENCE_BOARD_TEST_2026-09-06.md)
and [retained transcript](LED_HOST_PRESENCE_BOARD_TRANSCRIPT_2026-09-06.txt).
The v1.31 promotion changes only the final identity digit from the tested
v1.30 top, and its guarded installation, RESET/warm handoff, identity, and
live `$43` wait passed separately. See the
[v1.31 promotion report](STR8N_V1_31_VERSION_BOARD_TEST_2026-09-06.md).

## Implemented STR8-N I/O activity follow-on

The next measured slice adds activity only to paths owned by STR8-N:

- `$07` is published after the private line editor accepts a byte. Printable
  echo uses raw CHAROUT, so `$07` remains latched while the editor waits for
  the next byte.
- `$07` is published before each STR8-owned S19 record receive used by `L`,
  `I`, receive-error quench, and HIMON update. The public `$F009` record entry
  bypasses this wrapper and remains LED-neutral.
- `$0B` is published by a private output wrapper immediately before the raw
  blocking CHAROUT operation. STR8 strings, numeric fields, progress dots,
  and boot-selector output use this path.
- The command loop replaces activity with `$21` or `$43` on its next input
  wait. Successful handoffs still publish `$00`, and flash mutation still
  overrides normal activity with `$F0`.

This slice adds 25 resident bytes. The resident is 3,368 bytes at
`$F000-$FD27`; the worker remains 608 bytes at `$0200-$045F` and stored at
`$FD50-$FFAF`. Forty erased bytes remain at `$FD28-$FD4F`. Because the former
64-byte reserve is now being used deliberately, the layout checker enforces a
32-byte minimum and still rejects any resident/worker overlap. The selector
prefix remains 41 bytes at `$0200-$0228`.

The host-built candidate top BIN SHA-256 is
`9CA8573C48F7FEE34FA9A83A7D61672DCA77ECC2CA91A611C76EFADDE54E6C2E`.
The worker S19 remains
`CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713`.
Host regression checks freeze the public console bytes, verify the private
activity opcodes and call targets, validate every compact message page after
the code growth, and retain all 1,560 linked range-parser cases. Board proof
confirmed `$07` latched after an accepted line byte and `$0B` latched after
the installed private output wrapper emitted `T`. See the
[I/O activity board report](LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md) and
[retained transcript](LED_IO_ACTIVITY_BOARD_TRANSCRIPT_2026-09-06.txt).

## Future periodic heartbeat overlay (proposal only)

A future timer interrupt may add a heartbeat without replacing the foreground
status. Reserve Port A bit 7, the leftmost red LED, as a short pulse over the
current base value. The lower seven bits continue to identify the state:

| Base state | During heartbeat pulse | Meaning |
| --- | --- | --- |
| `$01` | `$81` | STR8-N run plus heartbeat |
| `$21` | `$A1` | no-host wait plus heartbeat |
| `$43` | `$C3` | host-present wait plus heartbeat |
| `$07` | `$87` | receive activity plus heartbeat |
| `$0B` | `$8B` | transmit activity plus heartbeat |
| `$F0` | `$F0` | flash mutation; heartbeat suppressed |
| `$00` | `$00` | display released; heartbeat disabled |

The preferred visible cadence is one pulse per second, with bit 7 asserted for
roughly 50-100 ms. This reads as one red tick while the base pattern remains
recognizable; it is not a 50-percent-duty alternation between two status
codes.

Implementation requires a private base-status shadow byte, heartbeat phase or
countdown, and an explicit LED-owner/heartbeat-enable flag. Foreground status
publishers update the shadow and display the base with the current heartbeat
phase applied. The interrupt preserves every register and processor flag it
uses, acknowledges its timer source, and writes Port A only while its component
owns the display.

STR8-N disables the overlay before `$00` handoff. HIMON disables it before `G`
or any other transfer to a user program and reclaims it only if that program
returns to the monitor. ASM-F2 remains under HIMON ownership and therefore
inherits HIMON's overlay. Flash mutation keeps solid `$F0`; the heartbeat must
not obscure it. Public raw console and record services remain LED-neutral, and
the heartbeat is not a public LED ABI. These ownership rules prevent a
periodic firmware interrupt from overwriting an application's eight-bit Port A
display.

This proposal has no implementation, ROM-size measurement, interrupt source,
or board proof yet. Selecting and qualifying the periodic timebase is a
separate prerequisite.

## Later slices

Continue with one independently testable behavior at a time:

1. Add `$03` host-present idle only at a semantic boundary that keeps the
   display useful.
2. Add supported terminal failure codes at existing error boundaries.
3. Copy the shared constants and ownership rules into HIMON, then ASM; each
   component restores its caller's state on return.
4. Document the optional contract for user programs while retaining their
   right to use all eight bits arbitrarily.
5. Select a periodic interrupt source and measure the heartbeat overlay above
   as its own candidate slice.

Until that slice exists, a steady `G_RUN` means only that firmware reached and
published that state.
