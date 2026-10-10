# Beta17 storage installation and hardware checks

The owner authorized flashing all boards and excluding DEMO/DEMO2. Beta17
(monitor generation $0000001A), WORK 1.2, SRAM 1.2, MAINT 1.8 and EDU 1.2 were
installed. CLOCK remains 1.5. No time synchronization, trim change, RTC ACK,
SRAM format, commit or push was performed.

| Board | Port / CPU | Active EDU / user RAM | Result |
| --- | --- | --- | --- |
| 2512 | COM4 / W65C02S | OFF / $0200–$66FF | Flash, both slots, utilities, absent-service/free-RAM, ABI/IRQ pass |
| 2205 | COM3 / W65C02S | ON / $0200–$64FF | Flash, both slots, preserving loader, utilities, ABI/IRQ and retained devices pass |
| 2609 | COM8 / W65C816 emulation | ON / $0200–$64FF | Same checks pass after guarded inactive-VIA-flag acknowledgment; unattended SPI startup limitation remains |

Each board's entire 131,072-byte flash was read twice and matched before
installation. The prior RTC/EEPROM state was archived read-only; each EDU's
complete SRAM array was independently read twice. The RAM-only installer was
modeled against each exact backup, including real hash opcodes, full-image
results, stale preimage/corrupt payload refusal, and four verified final record
commits. Its 12-sector plans preserved bank 0, recovery F, identity slots,
CLOCK and other user records.

MAINT's third sector was verified erased before allocation. The longer SRAM
record uses B2:A000–AEF9. WORK now loads at $5000 and is stored B2:B000–C4A2.
EDU moved to C580–C7FE, and the shared sealed asset occupies C800–CFFF. Existing
SDEMO was preserved at AF80. DEMO/DEMO2 were excluded; 2609's existing DEMO2
record at C540 was backed up and omitted from its new sector image. No test
DEMO/DEMO2 records were installed in flash or SPI SRAM.

After installer verification, the owner pressed each main SXB S2/RESB button
with main power retained. All four banks then matched the expected images
exactly. A/B/A cold software RESET checked both monitor slots, selected display,
EDU mode and RAM limits. EDU/WORK/MAINT startup and return passed. On the EDU
boards, a patterned RAM image spanning $3F00–$503F remained exact across named
R SRAM entry/exit; its prior RAM bytes were restored. 2512's R SRAM refusal
preserved every reclaimed $6500–$66FF byte. Actual RAM ABI and BRK/VIA1 IRQ
probes restored vectors, registers and stack.

UTC continued forward; oscillator/backup remained enabled, trim/control bytes
matched the archived values, and weekday matched Monday=1 through Sunday=7.
Remembered/factory EUI, all 128 EEPROM journal bytes and factory/status bytes
remained exact. Both entire SRAM arrays matched the pre-flash archives after
all tests. WORK's query/resize/session initialization was deliberately not used
in these preserving smoke checks. AUTO/MAINT transfer fault/commit behavior
remains covered by the local linked-code models; destructive physical transfer
and interrupted-power tests were not performed in this installation.

[STR8N-003](issues/SPI_2609_DISABLED_CB_FLAGS.md) records 2609's recurring
disabled VIA CB flags after RESET, which can make the boot SSRAM line unavailable.
Verified idle-port acknowledgment enabled the final SRAM comparisons; the
driver's conservative ownership policy is unchanged.

Raw backups/readbacks and logs remain ignored in
`output/qualification/storage-beta17-2026-10-08`; the aggregate
`hardware-acceptance.json` binds exact board hashes and explicitly records the
startup limitation. `tools/audit_v2_storage_hardware.py` checks these results.
The Git/history/release audit remains free of board backups.
