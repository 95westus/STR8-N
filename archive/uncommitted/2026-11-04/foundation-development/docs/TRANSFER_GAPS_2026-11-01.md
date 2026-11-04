# S19, large STORE and factory restoration

Foundation is **still frozen**: the published 4096-byte STR8N-F 0.3.0 g1
BASE1/PR05 image and every frozen source hash remain unchanged. These additions
are monitor services, RAM overlays and host tools. No new public F ABI is used.

## Current evidence

| Feature | State |
|---|---|
| Raw BIN loading | Existing frozen-F `L` stays unchanged |
| S19 RAM loader | Passed on2512/65C02 and2609/65C816 emulation |
| Integrated monitor `S19` command | Installed and accepted on2512: initial Ctrl-C, checked RAM loading through66FF, no auto-run and quiet MON return;2609 installation held |
| Large PROGRAM STORE | Installed2512 Store/Table/load-only Restore passed for8192 bytes at4700-66FF, preserving the source; all8256 temporary SPI bytes restored exactly |
| STORE frontend | Parsing/guards/cancellation passed in RAM; installed2512 explicit9800 positive publication and Restore passed.2609 retains the earlier provider |
| Dense S19 flash stream | Two real sector writes with crossing records passed on2512; exact B0 restoration passed. Corrected installed ROM library, I cancellation and a complete all-FF no-change sector pass also passed |
| Large flash STORE | Actual6400-byte Store/Table/load-only Restore through66FF passed; installed explicit Store/Restore front doors passed. Corrected installed AREA/AUTO retention and cancellation also passed |
| Factory image preparation | F-only and explicit full-B3 scopes implemented; host preservation/rejection tests pass |
| Live factory restoration | Open; deliberately replaces Foundation and is excluded from the golden-F trials |
| Development terminal RAM S19 | 0.1.2 adds Shift+F2/Shift+F3; host protocol and hidden Tk routing passed, live2512 Ctrl-C/load/readback passed. Physical modified keys and complete extracted-kit acceptance remain open; dense flash sending is refused |

The development artifacts are outside published downloads. No candidate ZIP,
tag or release asset changed. ASM/DBG remain deferred.

The earlier PROGRAM/S19 installation consumed four erases and four wear appends on2512,
with zero C/D erases or F writes. All23 old journal records remain intact;
sequence1120 has27 valid records. Fresh owner RAM/ZP and SPI metadata were
restored and independently read back. B1/B2 evidence consists of exact target
sector readbacks with untouched extents protected by the bounded writer;
it does not claim fresh whole-bank captures. B3 was captured in full.

2609 is explicitly owner-held after the separate RTC chat's loader mismatch;
RAM restoration there remains pending. Do not open COM8 or retry/reset it
without new owner recovery instructions. Its four approved installation
erases remain unused. This checkpoint does not close both boards.

## Completed 2512 flash increment

The [dense-S19/large-flash scope](FLASH_TRANSFER_2512_SCOPE.md) was approved
and its ten erases completed. Fresh capture found B0:9 blank but B0:A occupied; the
trial explicitly archives, temporarily erases and exactly restores A. Its
10 erases comprise five fixture/setup/restoration erases, four utility-sector
installs and one C rotation. The latter archived/replaced16 old C rows on chip,
carrying all settings/counts forward. B0, owner RAM/ZP and golden F are verified.
Installed checks caught the missed FA50 STATUS reservation and AUTO's AREA
loss during full cache reload. The separately approved
[three-erase correction](FLASH_STATUS_CORRECTION_2512_SCOPE.md) is now installed
and accepted. Rich STATUS/CPU/TIME/trim, actual ROM fragment loading, dense-I
cancellation, complete all-FF dense intake and AREA/AUTO retention passed.
2512 is at REC>, COM4 released; owner RAM/ZP are restored and read back.
RTC host admission is restored after actual STATUS/CPU proof; this does not
claim that the next scheduled NTP sample has already been accepted.
All21 pre-correction records remain on chip, with three new C500-C700 records,
sequence1133 and24 valid rows. No correction C/D erase or F/MON/B0 write occurred.
See [the acceptance and limits](FLASH_TRANSFER_2512_ACCEPTANCE.md).
F/MON A/B, PROGRAM/WB/CLOCK/SRAM/WORK bodies stay unchanged. The correction
restores the original STATUS details and protects its complete allocations. The new
gate/record code fits existing BANK MAINT padding. Existing native flash
AUTO remains the bounded WB AREA workflow; wide flash Store uses an explicit
address. Large returning BATCH and native MON I remain outside this increment.

## S19 RAM behavior

The disposable raw-BIN launcher is
`BUILD/s19-loader-g1-ram-r2/STR8N-S19-RAM.bin` in the workspace. Load that
RAM BIN through recovery first. At `SEND S19`, send ASCII S-records, not a BIN
and not a filename. F3/F4 remain BIN operations. Development terminal0.1.2 adds
Shift+F2/Shift+F3 specifically for the RAM S19 prompt; checked sending,
cancellation and independent live2512 RAM readback passed. See `SERIAL_CONSOLE.md`.
Physical modified-key and complete extracted-kit acceptance remain required;
the published terminal downloads have not been replaced. This sender refuses
the dense flash prompt, whose terminal workflow remains a separate gate.

S0 headers are accepted and ignored. Each S1 checksum, delimiter and complete
destination range is checked before copying that record to0200-66FF. S9 prints
the entry without executing it. Lowercase S/hex and CR/LF are accepted. Ctrl-C
at startup or mid-record stops the transfer; earlier complete records remain.
Stop the sender after an error. This loader does not roll back prior records.

Error codes:01 format/type,02 checksum,03 cancel,04 destination range. A record
crossing66FF is refused in full. It never writes flash, SRAM or RTC settings.
It uses high code6B00-70FF, state7500 and record buffer7700. The raw launcher
itself borrows0200-08FF; a host trial restores owner RAM/ZP afterward.

The final optional LF is drained before returning, so it cannot create an
extra MON prompt. The native command returns through its ROM caller. Public
HOLD in the standalone launcher follows Foundation's saved monitor policy.

## Large PROGRAM STORE

The source must be read before loading WB over4800-66FF. The new frontend
therefore runs above owner RAM, builds a request at69D0, requires live YES,
and loads the independently CRC-pinned PROGRAM worker above66FF. The worker
copies source bytes directly; it does not format SRAM or borrow WORKSPACE.
The former65C0 request buffer no longer overwrites bytes being saved.

The new provider retains legacy requests and adds op8 Store/op9 preview for
0200-66FF. A legacy op5 still refuses a source overlapping WB. Preview does
not publish a slot or write payload. Successful Store verifies payload and
publishes the committed directory record last.

Monitor syntax, **installed on2512; deferred on2609**:

```text
STORE P AUTO 4700 66FF EXAMPLE
S P 9800 4700 66FF EXAMPLE
```

The new path is interactive, not a returning BATCH command. Existing small
BATCH storage retains its current bounds. The new large flash-backed STORE
path has separate acceptance above; named flash/PROGRAM transfers remain
separate from this PROGRAM backend.

The code fits in existing storage-image padding at B1:D900-DEFF. SRAM/WORK
library g2 code and header remain unchanged; its whole-image CRC is resealed.
The transient provider loader uses MON scratch6A30-6AE8, not owner RAM. Its
caller must be outside6B00-77FF; the RAM trial's corrected caller is6A21.

## Factory scope

`nf_factory_image.py --scope f-only` preserves every byte outside B3:F,
including C/D, and accepts a matched4KiB F or32KiB vendor source. It is
appropriate only for standalone WDC F firmware, not a full factory-state reset.
`--scope b3` requires the full original32KiB bank and makes the broader
replacement explicit. A4KiB source never silently fills8-E with FF.

Both plans archive previous B3/F/C-D on the host. They open no port. A physical
programmer may still require a whole-chip erase; an output image is not an
erase allowance. Existing wear history must be archived/carried forward and
must never be described as zero wear. No actual factory restoration is claimed.

## Private evidence

```text
output/qualification/2512-S19-RAM-20261101-r3/report.json
output/qualification/2609-S19-RAM-20261101-r2/report.json
output/qualification/2512-wide-STORE-preview-20261101-r1/report.json
output/qualification/2512-STORE-front-RO-20261101-r4/report.json
output/qualification/2512-transfer-installed-20261101-r3/report.json
output/qualification/2512-transfer-PROGRAM-positive-20261101-r1/report.json
output/qualification/TRANSFER-checkpoint-20261101-r1/report.json
BUILD/transfer-final-g1-r2/manifest.json
```

Failed/deferred trials are retained. The initial S19 host prompt assumption
and the raw STORE harness return-area collision were corrected; each borrowed
owner escrow was independently restored. The subsequent2512 installation and
positive SPI trial have separate receipts above. No factory execution is claimed.

The completed STATUS text repair also restored live RTC-collector compatibility:
the scheduled2512 catch-up at12:19:15Z was accepted, with no new PF event or trim
recommendation change. Its previous failed attempts remain in campaign history;
no baseline, schedule, reader or RTC-setting rewrite was used to hide the gap.
