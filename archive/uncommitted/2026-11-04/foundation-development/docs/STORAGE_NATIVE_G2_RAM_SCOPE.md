# Native SRAM/WORK route RAM trial

November 1, 2026. Continue toward installed `R SRAM` and `R WORK` on
2512/2609. No flash writes are part of this RAM trial. Keep F golden and
2205/2604 outside this work; NIST/RTCC retains serial priority.

Candidates: SRAM/WORK g2, WB2 gD, services gC and the five-entry native
loader. Reuse existing MON gD, PROGRAM, CLOCK, FLASH and BANK MAINT bytes.
The storage library is 10,370 bytes ($2000–$4881); its sealed native image
fits three sectors. Its Q invalidates the WB cache at $4800, which also ends
this library instance: reload it before another invocation. The request/data
window remains $0200–$1FFF; this does not close wide Store staging.

The raw bootstrap initializes its route. Test caller variants seed native
SRAM/WORK selection while keeping the linked library byte-identical. Each
named tool has Q directly to MON and `!` for shared controls. The combined
raw tool retains S/W submenu selection and submenu Q to STORAGE. UNLOCK,
live YES, LOCK and PREP are exercised without a mutating storage operation.
Interactive storage entry is refused in BATCH before changing its parent.

Capture fresh owner CPU RAM/ZP and current B3. Compare the 2 KiB SPI metadata
before/after. Run actual Table/capacity queries and selected-bank returns.
The new WB must refuse the old loader's three-entry header. The RAM loader
probes must refuse the existing non-native B1:B–D contents before app copy;
these probes read those occupied sectors and never replace them.

Restore/read back owner RAM $0200–$66FF and ZP $00–$DF on every borrowed-RAM
exit. Independently verify B3 unchanged, preserve incoming EDU selection and
prompt context, release the port. No flash/journal/SRAM-data/RTC-setting
writes, resets or power cuts. Qualified underlying positive SRAM/WORK API
results remain the prior g1 receipts; do not repeat their mutation matrix
for these entry/control changes.

Successful RAM trials precede an exact occupied-image and boot/wear-history
review for installation. No existing published kit or download is changed.
