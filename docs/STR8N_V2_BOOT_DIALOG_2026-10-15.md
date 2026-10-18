> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta25 boot dialog candidate — October 15, 2026

Build with `tools/build_v2_boot_dialog.py`. The separate output is
`BUILD/v2-boot-dialog`; the existing beta25 package is preserved. This builder
and its instruction-model tests do not open ports or flash boards.

Cold boot now prints firmware/ABI, the saved board name when present, then a
compact RAM/EDU/SSRAM block. The optional power-fail report follows storage
status, then the current local RTCC time and the monitor prompt. Blank lines
separate these blocks. EDU and SSRAM values remain dynamic. EDU OFF still
omits device status and time, preserves reclaimed RAM, and performs no device
I/O. Ordinary monitor returns remain quiet.

Power-fail timestamps remain the RTC's recorded UTC values. The report header
is ` [power-fail UTC]`; no fixed offset is applied to historical timestamps.
The current RTCC line retains its explicit saved UTC offset.

The candidate changes the B2 status/local display assets and the sealed B3
RTC banner sector. Recovery/monitor images, services, CLOCK and MAINT retain
their existing binaries. SPI helper addresses remain fixed. To fit the UTC
label without moving those helpers, the failure message is shortened from
`RTCC: PF logging failed.` to `RTCC: PF log failed.` Its behavior is unchanged:
failed logging retains the latched event. Local code uses 1781/1790 bytes;
status code uses 2556/2558 bytes. CRCs and artifact hashes are regenerated.

`tools/test_v2_boot_dialog.py` checks actual boot ordering, named/unnamed boots,
dynamic SSRAM states, EDU OFF, quiet return, UTC outage output, successful
journal/ACK and failed logging with evidence retained. Existing
`test_v2_compact_boot.py` and `test_v2_time_local.py` run against this candidate
using `STR8_RTC_BUILD=BUILD/v2-boot-dialog`. Receipts and boot previews are saved
in the candidate directory. Hardware testing is excluded.

## Board 2609 installation

The owner authorized flashing 2609 after the offline qualification. The USB
serial A10MPQXCA identifies it on COM8. A complete 131,072-byte backup was read
twice and compared before preparing the update. The exact backup-bound RAM
installer passed instruction-model rehearsal, including stale-preimage and
corrupt-payload refusals, before hardware execution.

The installed plan updates B3:C (configuration/wear journal), B2:C/D/E
(display assets), then B3:8 (RTC banner). The saved configuration values are
retained; only wear counts and journal sequence advance. Both monitor slots,
F/E recovery, identity/timezone records, saved programs and the other sectors
are preserved. Each sector passed the device installer's verification. The
installer then halted awaiting physical RESET.

Backup, exact plan, model receipt and install transcript:
`output/qualification/boot-dialog-2609-2026-10-15/`.
After the owner pressed physical RESET, all four banks (131,072 bytes) matched
the expected installed image exactly. A subsequent J3 cold boot displayed the
new Board/RAM/EDU/SSRAM/local-time/prompt order on the 65C816, with MON A
generation 35 and MON B generation 37 preserved. The observed status was EDU
ON and SSRAM allocation uninitialized. No new outage was present in this boot;
the UTC power-fail block was verified in the instruction-model qualification.
The successful post-reset report and boot transcript are in `upgrade/` under
the installation evidence directory. COM8 was closed and released.
