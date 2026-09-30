# STR8-N 2.0a24 WDCMONv2 migration artifacts

Build offline with `make v2-a24-migration-kit`. The target rebuilds alpha24,
links the WDCMONv2 RAM installer, builds static bank maintenance in S19 and
ASM-F2 `.a` formats, checks both images, executes the linked installer in a
W65C02 CPU/FT245/flash model, and runs the binary-probe mock.
It opens no serial port and changes no board flash.

| Artifact | Purpose | SHA-256 |
| --- | --- | --- |
| `BUILD/v2-alpha24-wdcmon-ram/str8n-v2-alpha24-wdcmonv2-install-2000.s19` | Unified WDCMONv2 W65C02SXB/W65C816SXB RAM installer at `$2000` | `66bd1030c2f48444826f03562886fc4828d4047f36d4ba42d1e5f8e5396cbebe` |
| `BUILD/v2-alpha24-wdcmon-ram/str8n-v2-alpha24-f000-ffff.bin` | Exact F image supplied separately to installer | `43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a` |
| `tools/v2-apps/str8n-v2-bank-maint-2000.s19` | Bank maintenance, `L` then `G 2000` under STR8-N | `7fad3875a12d0e606ee045b13cd5e5ab7802dc7d206e08fd10e561b4bdc6b06c` |
| `tools/v2-apps/str8n-v2-bank-maint-2000.a` | Exact ASM-F2 `ORG`/`DB` carrier for bank maintenance | `a9254a351df0eab96d06dcb63a4a19441906178c6351ec56b3a2ffd8af40bef3` |

The maintenance machine image is 703 bytes at `$2000-$22BE`, SHA-256
`9dda57fe5a9ab0744c3db40b6ea3507efbc8ad15d2ddb2e66d8a623ad2559736`.
It is byte-identical to the alpha22 maintenance image. The build enforces
that hash, so later monitor changes cannot silently alter this static image.
The `.a` and `.s19` carry the same machine bytes. The host flash model passed
copy, occupied-destination refusal, erase, and B3 protection with S/R
both present and absent.

On board 2609, the published `.s19` loaded into RAM and its read-only `M` map
reported B0/B2/B3 occupied and B1 erased; `Q` returned to alpha24 at `B3>`.
The `.a` carrier was independently decoded as one `$2000` ORG, 703 DB bytes,
and END. Every byte matched the published `.s19` and pinned machine SHA-256.
`make v2-a24-migration-kit` now runs this check. An ASM-F2 guest was not present
on board 2609, so this is carrier-byte qualification plus execution of the
identical `.s19` image, not a live ASM-F2 assembly session.

The installer accepts only WDCMONv2. The host bridge requires a four-byte
`SXB?` board-info signature (`?` is one printable ASCII character), displays
the exact tag and versions, then asks the operator to type the physical board
model, `W65C02SXB` or `W65C816SXB`, **before sending any RAM write**. A blank or
different answer stops the load. An exact tag may still be required explicitly
with `-ExpectedBoardTag`. The installer also requires an expected SST39SF010A
`BF/B5` flash ID and its Bank 0 preservation policy. It copies stock B3 to erased B0 or accepts an exact
existing copy, receives the 4,096-byte alpha24 F BIN, and programs B3:F only
after the exact confirmation. The offline checker verified its `$2000-$299B`
RAM range, S9 entry, candidate F identity, refusal and recovery gate order,
and that B1/B2 are untouched. The unified entry starts `SEC; $FB; SEI`. WDC
documents `$FB` as a one-byte NOP on W65C02S; on W65C816S it is XCE, so the
entry forces emulation mode before the shared 8-bit code. The renamed build
switch produces the same alpha24 S19 SHA-256 above. The
[W65C02SXB board 2205 run](STR8N_V2_A24_2205_NO_EDU_2026-09-30.md) then
qualified this image on physical 65C02 hardware without the EDU board.
The alpha22 installer still builds and validates after the shared source change.

`tools/test_v2_a24_wdcmon_65c02.py` runs the exact linked alpha24 S19 with
WDC's one-byte `$FB` NOP behavior. Its successful case copies B3 to erased
B0, installs the exact F BIN, and checks B1/B2 preservation. Two refusal cases
check occupied B0 and a changed candidate BIN before B3:F mutation. The
machine-readable receipt is packaged as `TESTS/wdcmon-65c02-test.json`.
This is a logical hardware model; the physical 02 result is recorded below.
The 816 evidence is manual board testing, recorded in the package's board
2609 session, inventory, E-install report, and checklist.

Use the [02SXB no-EDU checklist](STR8N_V2_A24_02_NO_EDU_CHECKLIST.md) for
future runs. Do not treat absent EDU peripherals as a migration failure.

The first board 2609 load had exact RAM readback, but execution returned to
the shipped native EDU menu without showing the installer prompt. The revised
816 entry then reached the installer on a later reset. It identified `BF/B5`
flash, printed stock B3 FNV1A `280928EC`, and found B0 erased. With the owner's
authorization, the host sent `COPY B3 TO B0`; the installer reported
`B0 == ORIGINAL B3 VERIFIED` after sector and whole-bank exact comparisons.
The terminal was closed at `SEND STR8-N TOP BIN`. No candidate BIN was sent,
Bank 3:F was not installed in that preservation session, and Bank 2 was not touched. The owner identified
Bank 2 as the virgin W65C02SXB image; its contents were not read during this run.
The raw terminal and event logs are owner-local under
`output/qualification/board-2609-inventory-2026-09-30/`.

In a separate owner-authorized run, the installer again verified B0 against
original B3 and accepted the exact 4,096-byte alpha24 F BIN (SHA-256
`43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a`).
After `INSTALL STR8-N 2.0A24`, it reported `MIGRATION VERIFIED`. A physical
RESET booted `STR8-N 2.0a24 B3 65C816` at `B3>`. The independent
`D F000 FFFF` readback captured all 256 rows and matched that BIN byte for
byte. Bank 2 was not selected or written. A later USB power disconnect/reconnect
also booted the alpha24 core at `B3>`. The separate
[board-specific E installation](STR8N_V2_A24_816_E_INSTALL_2026-09-30.md)
subsequently passed exact E/F readback and post-E cold boot. The
[board inventory](STR8N_V2_2609_INVENTORY_2026-09-30.md) records a bounded B1
S/R save/restore and two matching read-only B2 full-bank captures. EDU-attached
testing remains the next-alpha task.

## Binary identity probe

WDCMONv2 already has a binary board-info command. The launcher sends `$55,$AA`,
expects `$CC`, sends `$0C`, and expects a 12-byte identity. The standalone
`tools/wdcmonv2/probe_wdcmonv2_binary.py` makes one such exchange and records
the exact transmitted and received bytes in JSONL. Its mock checks pass for a
valid `SXB6`, a missing sync, an incomplete reply, and a wrong tag. The 30-second
probe ran on board 2609 and captured the identity below.

Board 2609 boots the native EDU demo/menu and also answers the WDCMONv2 binary
probe as `SXB6`, hardware 3.00, WDCMON 2.00. The first early `$CC` response
gave no board-info payload; the next handshake did. The bridge now accepts
the `SXB?` signature and retries an incomplete armed reply. The later RAM load,
preservation copy, and alpha24 F installation are recorded above.

The measured `SXB6` on this W65C816SXB differs from the earlier `SXB3`
assumption. WDC board/firmware identity tags are changing across boards or
revisions, so the suffix alone is not a reliable CPU-family test. Record the
exact four-byte tag, hardware and monitor versions, and the physical model for
each board; a new suffix does not qualify a migration by itself.

The [WDCMON v2.0 manual](https://www.westerndesigncenter.com/wdc/documentation/WDCMON_User_Manual_v20.pdf)
defines the `$55,$AA` / `$CC` synchronization and `$0C` board-info command.
