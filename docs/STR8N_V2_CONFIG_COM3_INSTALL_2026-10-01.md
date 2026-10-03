# COM3: F configuration installation and B3 lower-sector erase

Date: 2026-10-01. W65C02 target, FT245 COM3 at 115200 baud.

The operator requested the new B3:F core, erasure of B3 sectors 8-E, and
preservation of the alpha23 monitor in B2. Initial RAM state showed the
resident monitor was B2, with its exact canonical alpha23 F image. B3:F
matched the archived alpha36 build. All four complete banks were captured
before any flash operation.

After entering B3, alpha36 reported `C 00 03 V 40`. Its validated 16-byte
configuration was read through `C` and the RAM configuration buffer:
`01 00 03 00 00 40 01 00 00 00 00 00 00 00 45 7A`.
These settings were placed at `$FFD0-$FFDF` in the candidate F image.
The EDU EEPROM was not written.

## B3:F installation

A board-specific RAM updater embedded the exact old F, staged new F, and
complete old E as an additional guard. Its worker addresses came from the
matched alpha36 build. Model checks exercised installation, changed-E
refusal, cancellation and failed-write restoration while preserving B0-B2.
This alpha36-specific updater is retained with the board evidence; it is
not the generic alpha24 migration command.

All 12,786 loaded RAM bytes read back exactly before execution. The updater
checked live E/F and reported `B3:F VERIFIED; RESET`. Software reset booted
`STR8-N 2.0a24c1 B3 65C02`. Independent full F readback matched the staged
image, including settings and vectors. `C` still reported `C 00 03 V 40`.

## B3 sectors 8-E

A separate 4,386-byte RAM eraser required B3 residency and compared the
complete configured F image before confirmation. Its only write targets
were B3 sectors `$80,$90,$A0,$B0,$C0,$D0,$E0`. The model checked success,
cancellation, changed-F refusal and stop-on-failure behavior. The complete
RAM load was independently read back before execution.

The eraser reported all seven sectors and `B3 8-E ERASED AND VERIFIED`.
Complete post-operation reads of all four banks proved:

- B3 `$8000-$EFFF` is entirely `$FF`.
- B3:F exactly equals the staged configured candidate.
- B0, B1 and B2 are unchanged byte-for-byte.

| Bank | Final SHA-256 |
| --- | --- |
| B0 | `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8` |
| B1 | `ecc688b1ae4d99f17841682b2f31ff305c72543d2f183fef4d6556ffe18fac55` |
| B2 | `4a38da8080ce5ed7ee9406e99a7d25b90eef72eaf8e2d16b06e1d1ac399c99b8` |
| B3 | `ac5144ba84484190f6dc0d480ded2f96a506e572b46dd9bffd3efc25fbe498fa` |

`T 3` reported `SR unavailable`, as expected with E erased. `J2` booted
`STR8-N 2.0a23 B2 65C02`; `J3` returned to `STR8-N 2.0a24c1 B3 65C02`.
The configuration command and an exact `$FFD0-$FFDF` readback confirmed
preserved settings after these handoffs. COM3 was left at `B3>`.

Evidence, original bank backups, staged images, updater sources, model tests,
serial transcripts and `verification.json` are owner-local under
`BUILD/board/com3-config-pocket/`.

This proves the requested installation, erasure, preservation and software
handoffs. Physical RESET, cold power cycling, on-board `C` rewrite/failure
tests, and a W65C816 installation were not performed in this session.
