# 2512 WDC B0 debugger handoff acceptance: passed

October 30, 2026, 65C02 / FT245. The
[RAM-only scope](2512_WDC_B0_HANDOFF_SCOPE.md) passed. See the
[sanitized device receipt](../monitors/validation/2512-wdc-b0-handoff.json).
No flash, journal, boot-setting, SPI SRAM or RTC-setting write occurred.
Owner RAM/ZP were restored and COM4 was released at MON B / B3>.

## Actual chain

1. Native MON captured fresh owner RAM 0200–66FF and ZP 00–DF twice. Both
   captures agreed. BASE1 READBACK read all four complete banks twice and
   matched the post-backup-copy checkpoint, including the pinned WDC B0:F.
2. A readback-checked 21-byte RAM bridge at 3000 selected B0, called its
   vendor FT245 serial initializer at F800 and entered debugger Main at F8A6.
3. The real WDC debugger returned identity `535842322c010000c8000000`
   (SXB2). Two independent 32768-byte WDC reads matched the preserved B0.
   Its existing FLASH example at B0:8 remained untouched and was not executed.
4. WDC uploaded an 8192-byte RAM packet at 2000–3FFF containing an 18-byte
   return bridge. Every 256-byte chunk and the whole packet were read back
   before execution. The bridge selected B3 and used public Foundation F007
   HOLD, returning to MON B g00000008 / CPU $02.
5. BASE1 independently read all four banks twice again: every byte matched
   the originals, including all 24 journal records. Original owner RAM/ZP
   were restored/read back through BASE1 and checked again by native Dump.

The journal remains sequence **1037**, 24 records, saved default B with MON
generation 00000008. Counts remain B0:8=8, B0:9=14, C=53, D=33, E=28, F=24.
All boot fields and raw records are unchanged. Frozen F retains its exact
release hash. No reset, power cut, assembler or CPU simulation ran.

## What this establishes

For this pinned vendor image, the binary WDC debugger can run from the existing
**B0:F sector** alongside owner code/data in the rest of B0, then hand control
back to the Foundation monitor. A complete dedicated 32 KiB WDC bank is not
needed for this admitted debugger-entry mode. A clean optional layout can
budget one 4 KiB sector for it; full original-bank host backups remain required.
This case did not reclaim or erase any owner sector.

## Remaining boundaries

The bridge bypassed F818 reset, its lamp/CS sweep, EDU VIA DDRB write and
application timeout. **Physical WDC reset and Foundation default-booting WDC
remain unqualified.** The vendor Main address is private to the exact admitted
65C02 ROM, not a portable WDC ABI. No vendor flash/erase or execute-application
command was sent. NFM2 factory migration, other vendor versions and 65C816
remain separate gates.

The existing `MON-G8-NATIVE-TIME` admission remains valid. The sampler, clock
settings, trim, power-fail flags, schedule and baselines were unchanged. Other
boards remained outside this trial. Source commits stay local and published
downloads remain unchanged.

Private evidence:
`C:\SRC\STR8-N\output\qualification\2512-WDC-B0-handoff-trial-20261030-r1`.

Pinned WDC B0:F SHA-256:
`ce5415f4e5032e44a19a2ab801ca9090fd81434355421d1913fca86a62f5a44b`.
