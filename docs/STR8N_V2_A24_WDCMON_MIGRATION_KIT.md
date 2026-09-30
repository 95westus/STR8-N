# STR8-N 2.0a24 WDCMONv2 migration artifacts

Build offline with `make v2-a24-migration-kit`. The target rebuilds alpha24,
links the WDCMONv2 RAM installer, builds static bank maintenance in S19 and
ASM-F2 `.a` formats, checks both images, and runs the binary-probe mock.
It opens no serial port and changes no board flash.

| Artifact | Purpose | SHA-256 |
| --- | --- | --- |
| `BUILD/v2-alpha24-wdcmon-ram/str8n-v2-alpha24-wdcmonv2-install-2000.s19` | WDCMONv2 RAM installer at `$2000` | `ec57ea1467438eb28bd3688625574d080ac1b6f556467f2b90b65cd7c8fda4e1` |
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

The installer accepts only WDCMONv2. The host bridge requires a four-byte
`SXB?` board-info signature (`?` is one printable ASCII character), displays
the exact tag and versions, then asks the operator to type the physical board
model, `W65C02SXB` or `W65C816SXB`, **before sending any RAM write**. A blank or
different answer stops the load. An exact tag may still be required explicitly
with `-ExpectedBoardTag`. The installer also requires an expected SST39SF010A
`BF/B5` flash ID and its Bank 0
preservation policy. It copies stock B3 to erased B0 or accepts an exact
existing copy, receives the 4,096-byte alpha24 F BIN, and programs B3:F only
after the exact confirmation. The offline checker verified its `$2000-$2999`
RAM range, S9 entry, candidate F identity, refusal and recovery gate order,
and that B1/B2 are untouched. The alpha22 installer still builds and validates
after the shared source change.

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
the `SXB?` signature and retries an incomplete armed reply. No RAM loading, flash image
readback, or physical migration was performed for this kit.

The measured `SXB6` on this W65C816SXB differs from the earlier `SXB3`
assumption. WDC board/firmware identity tags are changing across boards or
revisions, so the suffix alone is not a reliable CPU-family test. Record the
exact four-byte tag, hardware and monitor versions, and the physical model for
each board; a new suffix does not qualify a migration by itself.

The [WDCMON v2.0 manual](https://www.westerndesigncenter.com/wdc/documentation/WDCMON_User_Manual_v20.pdf)
defines the `$55,$AA` / `$CC` synchronization and `$0C` board-info command.
