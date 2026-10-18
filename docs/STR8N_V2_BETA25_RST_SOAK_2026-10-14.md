> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Overnight beta25 RST soak

At approximately 23:33 CDT, the user requested stopping 2604. Its in-flight transaction was allowed to finish and clean up; final preservation checks precede release. `excluded-boards.json` excludes 2604 from resumed soak workers, final collection and hourly drift snapshots. The remaining three boards continue to the original deadline.

The first hourly measurements passed on all three active boards at 00:09–00:10 CDT. The collector then failed deleting its request marker because Windows returned sharing violation 32; the soak yielded to that stale request. At the user's request, cleanup now marks requests released before deleting them, retries sharing violations, and treats a released marker as inactive if deletion remains blocked. Three host regression tests passed, including a real Windows delete-sharing conflict, retained-marker/lease/environment cleanup, and propagation of unrelated errors. The completed first-hour summary was recovered from its original per-board reports. Resume preserves the baseline files and trims, continues the original hourly schedule, and keeps 2604 excluded.

At 01:58 CDT the soak stopped between phases when Windows denied replacement of `status.json` (error 5). All three latest transaction reports verified blank scratch and preserved firmware/settings. The user authorized another fix and resume at approximately 03:22 CDT. JSON publication now uses unique staging files and bounded retries for Windows errors 5/32/33, retaining atomic replacement and the previous document on persistent failure. Three additional host tests passed: real reader blocking replacement, concurrent publishers, and timeout preserving the previous document. Resume verifies all three boards again, retains the same baseline and trims, takes one current drift snapshot, records the missed scheduled slot, then returns to the original hourly cadence. No replacement readings are presented as measurements from the missed time.

Boards 2205, 2512, 2604 and 2609 run as four parallel serial workers. The deadline is October 15, 2026, 08:59 CDT (13:59 UTC). New write units stop five minutes early to allow cleanup and final verification.

Evidence: `output/qualification/beta25-rst-soak-2026-10-14/`. The authoritative live files are `status.json` and `drift/status.json`; per-board transaction reports and serial logs retain the actual coverage.

Each board uses only initially erased B2 sectors 8 and 9 as scratch. Existing B3 C/D wear-journal accounting continues normally. Original firmware and saved program images are compared after each transaction. Scratch is erased and verified between records. Any failure stops new transactions and preserves evidence.

The cycle exercises TABLE, RESTORE and SAVE with MAINT, CLOCK, SRAM, WORK and EDU. Read-only foreground commands test the original programs. Large MAINT and CLOCK bodies are covered in successive chunks of at most 8,168 bytes; partial program records are restored load-only. Tests overwrite the destination RAM before restoring, compare every byte, check occupied-save refusal and missing-record refusal, and reconcile erase counts. SRAM uses the explicit bank/address load-only route because its named loader deliberately rejects load-only arguments.

The fresh NTP baseline passed on all four boards at approximately 23:09 CDT October 14. Current calibrated trims were retained, with no clock SET. Follow-up drift captures are due hourly at approximately :09, with measurement uncertainty preserved. A shared serial lease gives those captures priority between soak phases.

During preflight, 2604's I2C bus was held low. A bounded, modeled bus-clear procedure released it. RTC control was then observed as C3 and restored to its saved 00 value with a separately modeled register-only helper. Trim, history and identity were verified; the subsequent fresh NTP baseline passed. Details are in `2604/bus-clear-report.json`. No automatic bus-clear recovery is performed during the soak.

The app heartbeat `four-board-overnight-rst-soak` checks every 15 minutes and stays quiet while healthy. Native workers enforce the deadline. Keep all four boards powered and their terminal sessions disconnected.
