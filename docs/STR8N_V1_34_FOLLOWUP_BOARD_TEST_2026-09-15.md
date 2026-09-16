# STR8-N v1.34 power, interrupt, and worker board tests

Date: 2026-09-15. Port: COM4, 115200 baud. All three requested follow-up
areas passed. These results extend the
[initial v1.34 board session](STR8N_V1_34_BOARD_TEST_2026-09-15.md).

## Power-cycle and NMI

Receive-only capture was active before the operator was asked to remove
power, wait five seconds, and reconnect it. The log records USB disconnect
and reconnect, then `RST H`, `STR8-N 1.34`, the selector, `BOOT WARM`, and
`HIMON V 00.0910(2121)`. The off-time was not independently measured.

At the HIMON prompt, the operator confirmed one physical NMI press. The
captured result was `NMI PC=E55C` with registers and a recovered monitor
prompt. This exercises the installed `$F0CF` NMI entry and RAM-vector
dispatch to HIMON. No flash operation was active.

## Actual timer IRQ

The new RAM-only probe uses VIA1 Timer 1 to generate an IRQ while Bank 3 is
selected. It passed through the installed `$F0E3` IRQ/BRK entry and reported:

```text
V1.34 VIA1 TIMER IRQ / A-X-Y / STACK / B=0 / RTI: PASS
```

The probe checks the handler-entry and returned A/X/Y values, stack balance,
stacked status B/D/I bits, timer interrupt flags, and successful RTI. It
restores the prior IRQ vector, ACR, and timer latches and disables its timer
interrupt before entering RESET. It does not preserve timer phase and
performs no flash or bank-latch writes. See the
[probe instructions and register references](../tools/interrupt-test/README.md).

An initial manually linked transfer contained S9 `$0000`; the resident
correctly refused it with `BAD`. The maintained `make irq-test` target now
sets S9 `$2000`, and its host test explicitly verifies this entry before use.
The corrected artifact produced the hardware PASS above. The failed attempt
remains in the transcript.

## Optimized worker flash test

The read-only map identified an AP at B2:8 and an erased B2:9. The v1.34
probe was therefore rebuilt for **B2:9**, CPU `$9000-$9FFF`. B1:F remains
the recovery backup; neither it nor the AP sector was selected for mutation.

The probe copied and verified the exact 568-byte production worker from
`$FD78` into `$0200`. It independently checked all 4,096 target bytes were
erased before arming. The operator confirmed all red LEDs for the `$F0`
pre-write indication. After the second explicit `Y`, it:

1. Programmed and verified the full `$A5` pattern with the production worker.
2. Independently compared all target bytes with the staged pattern.
3. Erased and verified the sector back to `$FF`, then independently compared
   the full sector again.
4. Requested an invalid `$FF` record over Bank-3 `$F000`, requiring rejection
   before writing, carry clear, Bank 3 restored, and return LED `$01`.

The board printed `FAILED WRITE PREFLIGHT RETURN LED $01: PASS` and
`B2:9 ERASED; LED WORKER TEST: PASS`. The operator confirmed one green LED,
then pressed RESET. Capture showed `RST H`, 1.34, and warm HIMON recovery.
The observed LED states are the pre-write and completion states; transient
pulse timing was not measured.

The final maintenance map again showed B2:9 erased and the AP envelopes
at B1:9 (`L06A6`) and B2:8 (`L0C2A`). Directory rows were unchanged. A final
complete top-sector readback is byte-identical to the initial session's
post-update image, including code, directory, configuration, and vectors.
The board was left at the HIMON prompt and COM4 released.

## Artifact identity and evidence

The map checks exposed a maintenance-tool startup defect: after copying its
private worker over `$0200`, it called `$0203` to select Bank 3 for reading
the configured work/backup locations. That address is the private worker's
`IW` header, not the resident selector; the call could enter the private
dispatcher using stale mode/record state. The first map omitted the W/B role
labels. The repaired RAM startup selects Bank 3 directly through PCR and
restores the entry bank, without calling the overwritten selector. This
does not change the resident BIN or optimized worker.

The linked regression runs 216 startup cases across all three maintenance
variants, entry banks, non-bank PCR bits, and stale worker modes. It requires
correct B3 role reads, exact entry-bank restoration, no private-worker
dispatch, and no flash writes. The standalone repaired tool was reloaded
for repeated board map checks; its private flash worker remains byte-identical.

| Artifact | SHA-256 |
| --- | --- |
| Canonical v1.34 top BIN | `9538D97854BA9D5D76143CBA0FEDB3B2E7CE18F977CE89557406E63404026CB7` |
| Live top including preserved directory | `D9A418127C870E5DFDB535B20EDFAE276124D86AAB4616B3B28581392BADACB0` |
| IRQ probe S19 | `36A1277C0DC2B58076633CFA68F4E4FBE9467DED1BE7AF8B4361BF3294769E74` |
| B2:9 worker probe S19 | `E8C34448A3C5FE9513DA76429B8310708BCD620B6338C753EF02E453C2897294` |
| Repaired standalone Bank Maintenance S19 | `95AEE537E486E6A16E40DBD3CE7BAA181D018F44AB13F6A29601779D77650C2F` |
| Follow-up raw received bytes | `3363B37408FF772AB5AB8967DD32424877E84668405252CAEC63A268C98BD4CD` |

The [receive transcript](STR8N_V1_34_FOLLOWUP_BOARD_TRANSCRIPT_2026-09-15.txt)
retains the probes, maps, and complete final top dump. Append-only TX/RX and
USB reconnect events are in `BUILD/v1.34/board/2026-09-15-followup.jsonl`;
binary captures are retained alongside it. Earlier session logs are unchanged.

`make board-probe-check` checks the linked probe artifacts with py65:
IRQ success/timeout/busy refusal and cleanup, and worker success plus occupied
scratch refusal. The flash model requires mutations stay inside B2:9,
all banks finish unchanged, and no write occurs on occupied-sector refusal.
These checks supplement the actual board observations above.

Run `make bank-maint-role-check` to build and check all three maintenance
variants. The migration kit and release package carry the repaired tools.

Remaining broader release gates include Bank 0-2 guest boots, the resident
installation transaction, injected flash failures/recovery, directory refresh,
transient LED timing, and complete factory migration. This session does not
claim those paths or interrupt safety during flash mutation.
