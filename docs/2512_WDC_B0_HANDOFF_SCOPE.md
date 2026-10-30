# 2512 WDC B0 debugger handoff: RAM-only scope

Prepared and completed October 30, 2026; see the
[acceptance result](2512_WDC_B0_HANDOFF_ACCEPTANCE.md). Follow-up to the preserving
[B0 backup-copy acceptance](2512_WDC_BACKUP_COPY_ACCEPTANCE.md). This step
tests the retained WDC debugger without an erase, journal append or boot-policy
change. F stays golden. No other board, release download or remote Git state
is changed.

## Reviewed entry and return

The retained 65C02 WDC monitor occupies B0:F800–FFFF within the existing 4 KiB
B0:F sector. Its complete sector SHA-256 is
`ce5415f4e5032e44a19a2ab801ca9090fd81434355421d1913fca86a62f5a44b`.
The local original source archive and actual ROM bytes agree on the FT245
serial header at F800 and the debugger `Main` entry at F8A6. These addresses
are private to this pinned vendor image, not a general WDC ABI.

1. Save fresh native owner RAM 0200–66FF and ZP 00–DF twice. Read all four
   complete banks twice through frozen BASE1 READBACK and match the reviewed
   post-copy-trial hashes: sequence 1037, 24 records, original B0 restored.
2. Restore owner RAM before writing/readback-checking a 21-byte project RAM
   bridge at 3000. It selects B0 through PCR, calls the vendor FT245 serial
   initializer and jumps directly to F8A6. Native MON `G 3000` starts it.
3. Observe the exact twelve-byte SXB2 identity and independently read visible
   B0 twice through the WDC debugger. Permit identity/read commands only here.
4. Upload an 8192-byte RAM packet at 2000–3FFF, containing an 18-byte return
   bridge. Use WDC RAM writes only, read back every chunk and the whole packet,
   then execute the verified 2000 entry. It selects B3 and calls public F007
   HOLD to the active MON B. No vendor flash or execute-application command
   is permitted.
5. Independently read all four banks twice again. Require exact equality to
   the originals, including every journal byte. Restore and read back owner
   RAM/ZP, confirm native MON B / B3>, and release COM4.

The shims are explicitly encoded project instructions with commented source;
no assembler, F build or CPU simulation is needed. Their only I/O accesses are
bank selection through USB VIA PCR and the vendor FT245 initializer/protocol.
They do not use the EDU VIA, SPI SRAM, RTC, PIA lamps or the CS0–3 sweep.

## Qualification boundary

**F818 reset is not executed.** The vendor reset path runs a lamp/CS sweep,
writes the EDU VIA DDRB and has a timeout which can jump to the application at
8000. Entering `Main` directly bypasses all three; the debugger loop has no
application timeout. This keeps the existing FLASH example at B0:8 from being
entered as an unreviewed vendor application.

Success qualifies this pinned 65C02 B0 debugger entry, WDC RAM upload/readback
and Foundation HOLD return. It does not qualify physical reset into WDC,
Foundation default-booting WDC, other vendor versions/CPUs or NFM2 factory
migration. Bank-selector or persistent-default changes require their own scope.

The shared serial lease yields to RTC collection. No time, trim, power-fail,
PROGRAM/WORKSPACE or persistent setting write is included. If the handoff fails,
keep power and the original escrow. Do not send recovery text blindly into an
unknown WDC command state; physical RESET recovery to golden F is the separate
fallback if needed. No reset or power cut is planned.

Private plan:
`C:\SRC\STR8-N\output\qualification\2512-WDC-B0-handoff-scope-20261030-r1\plan.json`

Plan SHA-256:
`767d09a0aa7381e4c9969a8f6090e8fc29e20b36448b2cd980259f63e94f1bad`.
