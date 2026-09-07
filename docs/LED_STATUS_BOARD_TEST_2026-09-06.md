# STR8-N v1.30 minimal LED-status board test — 2026-09-06

> **Historical candidate:** this report retains the exact minimal-slice proof.
> The host-presence and I/O-activity follow-ons have their own
> [host-presence report](LED_HOST_PRESENCE_BOARD_TEST_2026-09-06.md) and
> [activity report](LED_IO_ACTIVITY_BOARD_TEST_2026-09-06.md).

The minimal `$00`, `$01`, `$41`, and `$F0` status slice passed on the EDU
board at COM4, 115200 baud. The tests exercised the installed canonical top,
the unmodified stored production worker copied to `$0200`, the public raw
console ABI, a disposable flash sector, physical RESET, and final read-only
bank inventory.

## Exact artifacts

| Artifact | SHA-256 |
| --- | --- |
| Bank-3 `$F000-$FFFF` BIN | `51F84BB7E195882F96C684054947FB25986230546967A549C9EE55F8CEF5C248` |
| Production worker S19 | `CBD477AD62A0FF7FC14DE22F3575C7B05834C973A5DF622A6678DEF6C4577713` |
| Console ABI probe S19 | `E53ED8B7622D512267979C52B9153617823487704B1F1D043D53FB8C009EF2C1` |
| LED worker probe S19 | `54D3FE0D7DCA8DC7D40BF5FE5CA373ECFA67AFB792B87EB887BC991319011197` |
| Bank Maintenance S19 | `A0645280E60A12EA9928E7E30A08B3DA7B7E897EB8846ADFA8A2367629AE114F` |

The linked resident occupies `$F000-$FD02` (3,331 bytes). The worker occupies
`$0200-$045F` and is stored at `$FD50-$FFAF` (608 bytes), leaving 77 erased
bytes at `$FD03-$FD4F`. The public selector prefix remains `$0200-$0228`.

## Results

The guarded top updater installed and verified the candidate. Its pre-update
backup of the prior B3:F image remained in protected B1:F.

The console ABI probe observed `$00` on entry through `L`, set a static
application-owned `$A5`, and retained `$A5` through ABI query, console init,
`CHAROUT`, `CHAR_READY`, `CHARIN`, and BRK-vector checks. The operator
confirmed the physical display was static `$A5`. A physical RESET then showed
`$01` during STR8-N startup and `$00` after the warm HIMON handoff.

Selecting `S` reached the STR8-N command loop and the operator confirmed
`$41`. This establishes the low green RUN bit, the high red input-wait bit,
and active-high polarity.

The initial worker probe staged all `$FF` into already-erased B2:8. It returned
PASS without showing `$F0`; log timing was about 48 ms from the pre-operation
message to the completed message. Source review then confirmed that the
worker correctly skipped both erase and programming, so it never crossed the
flash-unlock boundary. No mutation occurred. This refusal/no-op result is
retained because it prevents a false hardware claim.

The accepted rerun first used the read-only Bank Maintenance map to require
B2:8 erased, B2 fully erased, D2 empty, B1:E marked WORK, and B1:F marked as
the B3:F backup. The probe copied and read back the exact stored production
worker, preflighted B2:8, and pre-armed `$F0` while awaiting the final `Y` so
the physical pattern was human-visible. The operator confirmed all four red
LEDs on and all four green LEDs off. The public raw input service did not
change that value.

After `Y`, the production worker reasserted `$F0` at every flash-unlock
boundary, programmed `$A5` into every byte of B2:8, verified the full sector,
returned through Bank 3 with `$01`, erased the sector back to `$FF`, and
verified all 4096 restored bytes. A known program-record mode then requested
an impossible zero-to-one change at Bank-3 `$F000`; its preflight failed
before flash unlock, and the probe verified the returned Port A latch was
`$01`. The operator independently confirmed the final physical display was
`$01`.

After physical RESET, a final read-only map again reported B2 entirely erased,
D2 empty, B1:E WORK, and B1:F backup. Quitting Bank Maintenance returned
through STR8-N and warm-booted HIMON normally. Separate explicit selector
`C` and `W` runs then reached `BOOT COLD`/`RAM ZERO OK` and `BOOT WARM`,
respectively. Both reached HIMON `00.0902(1707)`, and the operator confirmed
the display was released to `$00` after the final warm handoff.

These results accept the minimal slice. PWE# host-presence states, RX/TX
activity, detailed error codes, and native HIMON/ASM ownership remain later,
separately measured work.

## Owner-local evidence

The append-only JSONL logs under `BUILD/v1.30/local/` are excluded from the
published release. Their hashes are:

| Log | SHA-256 |
| --- | --- |
| `led-board-session.jsonl` | `BF808F143E4FF22FA2F4453AD7A1AE635463C8F1208A41C56ACE918FFF47ECA3` |
| `led-physical-reset.jsonl` | `6D2F3FA77D1B06F2FF8D84063830B21F242199C2211990B2127F714513432EBA` |
| `led-worker-board-session.jsonl` | `546B9D3198D9F20E9C8D8733213A9B8EDF358B98D500F227ABB9EF357CDAB64F` |
| `led-worker-reset.jsonl` | `C0C2CE7FFB83C97F0E623E6E0A369C8E8C2D5DE96FFEE289D23CEADCBB868EA0` |
| `led-worker-visible-session.jsonl` | `B477931CBFC7F3E299455661D799E65CE03FC3D69CE9A1C64B258E9400D9EAB3` |
| `led-worker-visible-reset.jsonl` | `37E324B4CEBC80203BCFA6DA03590A76D0C96A77A6E97379C44CC176979D7909` |
| `led-final-board-session.jsonl` | `A04E610B835E7DFDEB8F34AC7A18B8FFA56A2B5E4501EB524535FEDFF5E59251` |
| `led-final-reset.jsonl` | `4F8C22D20DD4A48E1C0EFE750549598B13DC70792C2B71761CFE9E597084654D` |

The compact retained transcript is
[LED_STATUS_BOARD_TRANSCRIPT_2026-09-06.txt](LED_STATUS_BOARD_TRANSCRIPT_2026-09-06.txt).
