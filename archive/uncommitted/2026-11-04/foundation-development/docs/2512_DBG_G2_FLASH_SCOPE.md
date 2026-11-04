# 2512 DBG g2: flash-scope review

November 2, 2026. **Reviewed scope, subsequently approved and executed.** See
the [installed acceptance](DBG_G2_2512_INSTALLED_ACCEPTANCE.md). The original
review below was completed without flash writes. The other
2512 utility-retirement and legacy-reclamation operations have closed.
The [17-group real-CPU RAM acceptance](DBG_BROAD_2512_RAM.md) qualifies the
g2 fixes; installed DBG was g1 at the time of this review.

| Operation | Reviewed limit |
| --- | --- |
| Replace DBG | Two 4 KiB erases/programs: B0:C and B0:D |
| Reserve wear | Two append-only records: B3:CA00/seq1200, CB00/seq1201 |
| C/D journal erases | Zero |
| F, MON A/B, ASM and extension writes | Zero |
| SPI-data or RTC-setting writes | Zero |
| Resets / power cuts / other boards | Zero |

The fresh capture has 26 valid journal records at sequence 1199. All 26
remain byte-for-byte at their original addresses and are archived on the
host. The planned result has 28 records at sequence 1201. B0:C and B0:D
tracked erase counts each advance from 2 to 3; B3:C/D/E/F remain
58/38/39/24. There is no history replacement or boot-policy change.

The B0:D800–DFFF SF/1 source provider is included unchanged in the target
sector. Preserve ASM, MON A/B g10, saved default B and its generation,
board metadata, unrelated images and reclaimed sectors. The update adds
no occupied sectors. FLASH and MAINT remain host-loaded RAM utilities;
this update does not reinstall their retired flash copies.

Fresh owner RAM/ZP and the full $6B00–$77FF provider cache were restored
and verified after the read-only capture. The board is at REC> and COM4
is released. No flash writes were made for this review. RTC collection
retains priority; no other board was accessed.

Before installation, acquire the shared serial lease in an RTC window,
capture fresh owner RAM/ZP/cache, and recheck exact bank hashes, target
preimages and journal room. Changed preimages or a required rotation
invalidate this scope; stop rather than expand it.

Installed acceptance should cover R DBG launch/cancellation, X/HOLD ZP and
patch cleanup, BC, invalid-call guards, representative callbacks and public
N calls, plus unchanged ASM/source-provider admission. Independently read
back all banks and journal, restore/verify owner RAM/ZP/cache, and finish
at REC> with COM4 released. Published downloads remain unchanged.

Workspace evidence (private captures, not release payloads):

- `BUILD/dbg-base1-g2-r1/manifest.json`
- `output/qualification/2512-DBG-broad-RAM-20261102-r1/report.json`
- `output/qualification/2512-DBG-g2-fresh-preflight-20261102-r1/report.json`
- `output/qualification/2512-DBG-g2-install-scope-20261102-r1/plan.json`
- `output/qualification/2512-DBG-g2-install-scope-20261102-r1/review-document.md`
