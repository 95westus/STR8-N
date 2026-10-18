> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Eight-character board name candidate

The isolated beta24 generation 33 candidate adds a flash-backed board name,
managed by MAINT 2.0 and displayed at cold boot. Initial qualification used
isolated software models without board access. On October 14, 2604 and 2609
were updated and physically tested; see the qualification results below.

At the MAINT prompt:

```text
NAME
NAME 2609
YES
NAME LAB-2609
YES
NAME CLEAR
YES
```

`NAME` shows the current name or `Board: unnamed`. Setting accepts one through
eight non-space printable ASCII characters, canonicalized to uppercase by the
existing maintenance console. `CLEAR` is reserved for clearing the name. Set
and clear require exact `YES`; setting the current value does not write flash.

A named board prints `Board: LAB-2609` at cold boot with EDU ON or OFF. An
unnamed board omits that line. Clearing and renaming take effect at the next
boot without changing RTC identity, UTC, trim, timezone, or the EDU profile.
Ordinary monitor returns remain quiet. Names are labels, not unique hardware
identifiers, and do not depend on a connected RTC.

Names use a new `BN`, version 1 record in the existing shared
B3:$9C00–$9FFF append-only tail. Each 32-byte record contains a little-endian
32-bit sequence, a length byte at offset 8, eight zero-padded name bytes at
9–16, CRC-16/CCITT over bytes 0–27 at 28–29 (little endian), and a zero commit
byte at 31. Length zero records clear the name. The latest valid sequence wins;
bad versions, bad checksums, invalid lengths/characters/padding and incomplete
records are ignored. Occupied invalid slots are never reused.

The writer checks the existing journal format, refuses a full tail or exhausted
sequence, verifies all staged bytes before programming the final commit, then
reads back the selected name. It uses the existing trusted RAM byte worker,
preserving worker zero page, bank selection, LED and NMI hold. It never erases.
EI, TZ and BN records share the same 32 slots; explicit reclamation remains a
separate operation. Firmware maintenance must preserve this tail.

The local display asset grows from 1536 to 1792 bytes within the already
reserved B2:E sector, and borrows $6700–$6DFF instead of $6800–$6DFF. Its loader
continues to preserve the full journal scratch page at $6B00–$6BFF. The common
status asset still fits B2:$C800–$D1FF and $6E00–$77FF. No permanent application
RAM reservation is added. Fixed recovery F, the existing E loader, RTC/SPI
components, journal code and the flash worker remain unchanged.

Build and separate qualification (WDC tools on PATH):

```text
python tools/build_v2_board_name.py
python tools/test_v2_board_name.py
```

Candidate artifacts and machine-readable results live in `BUILD/v2-board-name`.
The focused linked-model suite checks EDU ON/OFF cold boot, command bounds,
confirmation, repeat writes, clear/reset persistence, malformed records, full
tail, sequence exhaustion, incompatible journal, flash timeout, preservation
and a power cut after every programmed byte. Existing compact-boot and MAINT
storage-copy tests run against this candidate separately.

Separate qualification passed: the NAME suite covers all 20 interrupted-write
checkpoints; compact boot and MAINT's flash/SRAM storage-copy regressions pass;
the existing timezone suite passes, including 21 calendar/offset cases and all
13 interrupted TZ appends. Generated fixed recovery F, E, RTC/SPI component,
journal sector and configuration-journal image match the frozen beta23 hashes.

Physical set/change/clear, A/B J3 startup, named EDU ON/OFF, complete flash
readback, SRAM power retention and original-state restoration passed on
2604/2609 on October 14. Power-on output exposed a missing newline before the
board label when a power-fail message precedes it (STR8N-006). APPS retains
its preexisting STR8N-004 exception. STR8N-006 was subsequently repaired in
an isolated sealed-helper update and closed after both boards passed physical
power-on and retention retests; see the
[fix report](STR8N_V2_FIX006_RETEST_2026-10-14.md). See the
[physical qualification report](STR8N_V2_BETA24_QUALIFICATION_2026-10-14.md)
for evidence, limitations and the open formatting defect. This scoped change
does not require a new extended soak, and no new extended-soak completion is
claimed.

2604 and 2609 subsequently received beta24 generation 34 with startup-key
shortcuts and passed physical RESET, A/B/RAM-edit, recovery and complete
retained-memory retests. See the
[startup-key deployment report](STR8N_V2_STARTUP_KEYS_2026-10-14.md).
