# 2512 Foundation saved-default WDC launcher boot: passed

October 30, 2026, **65C02 / FT245**. The owner continued the
[two-erase scope](2512_WDC_DEFAULT_BOOT_SCOPE.md), then pressed 2512 RESET
once when its receiver was armed. Foundation booted the saved B0 launcher
without a chooser key, entered the pinned WDC debugger, and returned through
public RESET. Original FLASH, B default and owner RAM/ZP were restored.
The [sanitized receipt](../monitors/validation/2512-wdc-default-boot.json)
records the independent audit. F and published downloads are unchanged.

## Actual boot and return

1. Fresh native owner RAM/ZP captures agreed. Two complete reads of every
   flash bank matched the preserving checkpoint, including original FLASH at
   B0:8 and the pinned WDC ROM at B0:F. All 24 prior journal records were saved.
2. OPAQUE committed C800/1038 before replacing B0:8 with the project launcher.
   Its sector and complete bank postimages matched. CONFIG saved default 0 at
   C900/1039; B0 was already enabled at 8000, so no entry/enable write occurred.
3. Original owner RAM was restored before arming the receiver. One physical
   RESET produced frozen Foundation's identity, the complete 6→0 countdown and
   `WDC B0 / BASE1 DEFAULT BOOT`. The saved startup log interval contains **RX
   only**: no host chooser key was sent.
4. WDC returned exact SXB2 identity `535842322c010000c8000000`. Two independent
   visible-bank reads matched the launcher-bearing B0 image. Its verified RAM
   return packet selected B3 and jumped to public F004 RESET. The receiver
   selected S and confirmed recovery. No vendor flash/erase or application
   execution command was sent.
5. CONFIG restored default B and its original MON generation 00000008 at
   CA00/1040. After verifying that policy, OPAQUE reserved CB00/1041 and restored
   original FLASH at B0:8. All four final banks matched two independent reads.
   BASE1 and native Dump verified restored owner RAM/ZP. Final MON B / B3>,
   COM4 released; no flash, settings or RAM restoration remains pending.

## Accounting and preservation

| Item | Before | Final |
| --- | ---: | ---: |
| B0:8 tracked count | 8 | 10 |
| B0:9 tracked count | 14 | 14 |
| C / D / E / F counts | 53 / 33 / 28 / 24 | Unchanged |
| Committed records | 24 | 28 |
| Latest sequence | 1037 | 1041 |
| Saved default | B | B, original generation 00000008 |

Exactly two target erases and two settings appends ran: four new records at
C800–CB00. Every one of the 24 original raw records remains at its original
address. Bank enables/entries, unknown-history mask and other latest-record
fields are preserved. B0/B1/B2 are byte-for-byte originals; B3 differs only by
the four admitted appends. Counters are conservative tracked attempts, not
lifetime totals. Three ordinary append pages remain: CC00/CD00/CE00; CF00 is
reserved. Future write scopes must forecast that remaining capacity.

There were **zero F writes, C/D erases, MON A/B/E rewrites or power cuts**.
One WDC assembler/linker build produced the 133-byte launcher, padded to one
4 KiB sector; no F or existing RAM component was rebuilt, and no CPU simulation
ran. Three software Foundation restarts handled CONFIG exits and WDC return;
these are distinct from the owner's one physical RESET.

RTC sampler/profile `MON-G8-NATIVE-TIME`, clock settings, trim, power-fail flags,
schedule and baselines were unchanged. No SPI SRAM/PROGRAM or WORKSPACE data
write occurred. Other boards remained outside the trial. Source commits stay
local; no push, ZIP or release asset change occurred.

## Reusable example and limits

The [commented launcher source](../apps/examples/wdc-b0-launch.asm) and
[candidate BIN/manifest](../apps/candidates/wdc-b0-launch-g00000001/README.md)
contain project code and compatibility fingerprints; the owner must already
supply the pinned vendor B0:F ROM. The example uses one 4 KiB entry sector plus
the existing 4 KiB vendor sector. It is not left installed on 2512 after this trial.

This closes **Foundation physical RESET → saved B0 opaque launcher → pinned
WDC Main → public RESET/recovery** for this 65C02 ROM. It bypasses vendor F818
reset, its lamp/CS sweep, EDU VIA DDRB write and application timeout. Direct
hardware-bank-selector boot into F818, other CPUs/vendor ROMs and NFM2 factory
migration remain separate and unqualified by this case.

Private evidence:
`C:\SRC\STR8-N\output\qualification\2512-WDC-default-boot-trial-20261030-r1`.

Original B0 final SHA-256:
`5b72e8041c01f1fab145f8926a01b2be02ba807c654525bc04eed450a48c245f`.

Final B3 SHA-256:
`8a6a6fc1018e189a9ee4b2a43d37262bac7604e3162ba36b4541b8954c8d3fae`.
