# BASE1 RAM map and WDC recognition

The read-only RAM MAP/MAINT tool supplies `M 1`, `M 2` and `M 3` (also `M1`,
`M2`, `M3`); these are
**view numbers, not bank numbers**. `M 1` is the compact grid, `M 2` shows every
sector, and `M 3` adds tracked erase counts. Bare `M` uses view 2. All views cover
B0-B3. F has no image-recognition catalogue or board-status scan.

| Cell | Meaning |
| --- | --- |
| `..` | All 4096 bytes are FF |
| `U+` | Programmed, unidentified contents |
| `W+` | Known WDC resident-monitor fingerprint and reset vector |
| `W?` | WDC-style SXB signature and plausible reset vector only |
| `F+` | The currently running F, already admitted by the RAM tool's F guard |

`W+` and `W?` apply only to the **F800-FFFF resident monitor range** inside
that bank's F sector. They do not identify or validate the complete bank.
A FLASH application or another owner program can occupy lower sectors while
the WDC resident monitor remains intact. The detailed view explicitly keeps
the rest of the bank unclassified.

The current catalogue has two known WDCMONv2 2.00 resident profiles, one for
65C02 and one for 65C816. The RAM check requires the profile's SXB2/SXB6 identity,
reset vector, CRC16 and FNV32 of all 2048 resident bytes. The host catalogue
helper also checks the resident SHA-256. These are byte-recognition results,
not proof of execution, compatibility with the running CPU, or a successful
hardware boot. CPU labels describe the recognized image, not the board doing
the inspection. A possible `W?` match reports version unknown. WDC has no N/F
generation; both kinds report `gen --`.

The catalogue contains fingerprints and compatibility labels only. It carries
no WDC firmware, owner bank images, board IDs or retained application metadata.
Its recognized ranges were derived read-only from existing private archives;
no live board was read or executed to build this catalogue. Updating the RAM
catalogue does not require an F rebuild.

BASE1 policy labels are independent of recognition: B3:C/D are journal storage,
B3:F is recovery, and all other sectors are owner image space. A/B are not
reserved monitor slots; E is not automatically assigned to a provider; B0 is
not presumed to be a WDC backup. Erased or recognized does not mean unowned or
available for overwriting. The tool has no write/erase/format/execute command.

`R`, `D`, `K` and `V` retain their existing read-to-buffer, display, CRC and
comparison meanings. `Q` restarts through F. Mapping does not launch WDC, query
EDU/SPI/RTC devices, or emit an OS status banner. An OS/personality owns its own
name/version/generation and board-status output after handoff.
