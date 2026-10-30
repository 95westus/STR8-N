# 2512 native utilities checkpoint

**Installed and accepted October 30, 2026.** MON A/B g0000000A, services g6,
WB2 g8, native CLOCK/FLASH-MAINT g1, RAM loader r7 and HOST repair r8. This is
a usable native-utilities candidate; the complete b35 shipping contract is not
closed. Published downloads and frozen F were not changed.

The [operator manual](NATIVE_UTILITIES_MANUAL.md) gives commands, installation,
hardware profiles and memory ownership. The [receipt](../monitors/validation/2512-native-utilities.json)
records the accepted scope and component bytes.

## Accepted workflows

- VERSION/V, concise fresh TIME and quiet Q retaining the selected bank/cache.
- Full CLOCK STATUS/VERSION, invalid-date rejection and canceled SET.
- R CLOCK/R FLASH/R MAINT, APPS and BOOT display/default-generation save.
- FLASH READ/16-by-16 VIEW/EDIT, cancellation and C/D/F refusal; real 1-to-0
  BYTE, edited 4 KB WRITE, ERASE back to original blank B0:9 and Q.
- HOST/OIP1 reads, identical no-erase replacement, Q to FLASH and Q to MON.
- EDU ON, SRAM, WORK, TABLE P and BATCH VERSION;TIME.
- Flash STORE/RESTORE into RAM, PROGRAM STORE/RESTORE/run, verified source
  erase, then automatic PROGRAM lookup/run.

NFCOPY remains in PROGRAM at $9000, load/entry $3000, eight bytes. It prints P
and returns through public HOLD. Existing CLK/CLOCK records were retained.
B0:9 is FF again. B0/B1 owner images, WORKSPACE, owner RAM $0200-$66FF and
owner ZP $00-$DF were preserved. EDU is ON for this session; COM4 is released
at B3>. Native TIME/NIST re-admission passed nine observations without RAM
upload, SET, trim or ACK; historical samples, baseline and cadence remain.

## Allocation and space

| Region | Component |
| --- | --- |
| B2:8/9/A | Shared WB2/SP1 bundle |
| B2:B/C/D | CLOCK RAM-overlay image |
| B2:E/F | FLASH/MAINT RAM-overlay image |
| B3:8 | RTC provider, RAM gateway and loader |
| B3:9 | History code/return template; target metadata at 9C00-9FFF |
| B3:A/B | Identical MON A/B |
| B3:C/D | Target boot/wear journal |
| B3:E | Services/maps/wear/APPS/dispatch |
| B3:F | Unchanged 4096-byte Foundation |

**56 KiB firmware including F + 8 KiB journal = 64 KiB.** Optional payload
above F is 52 KiB. B0/B1 remain owner space, with their existing contents.
Free bytes within allocated images: F367 (frozen), A/B4 each, services134,
WB193, PROGRAM487, CLOCK31, FLASH/MAINT1559. These are not free owner sectors.

## Preservation and corrections

17 system-image erases, three B0:9 test erases, and one native C rotation plus
one D rotation total **22 sector erases; zero F writes or power cuts**. Raw
history was archived before compaction; latest boot/wear state remains on chip.
Full-board backup/checksum campaigns were not repeated. Operation-level target
readback and owner-RAM restoration checks remained in place.

Final journal: sequence1065, 20 valid records, default B/generationA, mask0F,
four $8000 entries. Counts C54/D34/E29/F24; B0:9 is18. Prior wear is unverified.

The first loader used clobbered X for CRC page counts and called ROM F while
B2 was mapped. Two golden-F recoveries restored owner RAM. The corrected RAM
CRC path and both apps passed RAM trials before repair. HOST's prompt lifecycle
required a separate RAM-qualified correction. A copy-test host assertion also
expected B3 after a correct retained-B0 return; its fix changed no firmware.

## Remaining shipping gates

- Positive CLOCK SET/ACK/trim/policy writes in an admitted measurement segment.
- Targeted new 65C816 physical paths, not another duplicate full suite/soak.
- Complete b35 BATCH combinations and independent large PROGRAM load/handoff.
- Live factory WDC restoration; the host preparer/procedure are plan-only.
- Review of the new extracted candidate's release workflow.

ASM/DBG follow this increment. These gaps are explicit; a help screen does not
establish feature completion. No other board was accessed by these trials.
