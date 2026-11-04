# 2512 upgrade and preserving BASE1 acceptance: passed

Subsequent, separately authorized [B0 write/boot and power-loss tests](2512_B0_POWERCUT_ACCEPTANCE.md)
also passed. Figures below describe the earlier preserving upgrade case;
the newer receipt records its additional reservations.

Local date October 28, 2026; physical trials recorded October 29 UTC.
Board 2512, 65C02, COM4/FT245, Windows host. The user explicitly authorized
one journal reservation append and the frozen 4K F replacement, followed by
the preserving BASE1 trial. CONFIG/opaque writes and power-cut tests remained
excluded. No other board was opened; 2205 was untouched.

The [sanitized result](../validation/2512-upgrade-base1-acceptance.json) binds
the tested source/template hashes and private evidence digests. Complete
captures, phases, raw logs and before/after RAM/images remain private at:

```text
C:\SRC\STR8-N\output\qualification\2512-closeout-20261028-r1\
```

## Journal/F upgrade

Two fresh read-only inventories agreed on every flash bank and original owner
RAM/ZP before any helper upload. The fresh plan matched the reviewed reference.
The physical old-F reset was caught, NFU1 passed its self/plan/all-source/chip
checks, and the device reported a committed reservation before F payload delivery.

| Item | Actual result |
| --- | --- |
| Target F | Exactly frozen STR8N-F 0.3.0 g00000001 / BASE1 / PR05 |
| F SHA-256 | 8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1 |
| Reservation / commit | D300 / D3FF=00, commit last |
| Journal records | All 19 old records retained byte-for-byte; 20 total |
| Sequence | 951 to 952 |
| F attempt count | 21 to 22; one F sector erase |
| C/D erases | Zero; all other counters/history mask preserved |
| Saved policy | B, enabled mask 0F, all entries 8000; unchanged |
| Owner images | B0-B2 and B3:8/9/A/B/E unchanged, including B0:8 FLASH and erased B0:9 |

Independent full-bank reads matched the planned postimages. A byte audit
confirmed that only the approved D300-D3FF page and F000-FFFF sector changed.
The new F identity descriptor parsed correctly with ABI major 2 and PR05.
Original RAM 0200-66FF and ZP 00-DF were restored and independently read back.

## BASE1 and console

- Two physical BASE1 reset entries showed the exact name/version/generation and
  profile, were intercepted with S, and reached recovery. Repeated reset did
  not change the journal, settings, counts or images.
- The operator exercised real F1-F12 keys, native help/file/log dialogs,
  connect/disconnect, local clear and logging. These were not synthetic-key
  substitutes. F12 cancelled SEND BIN before payload; F3/F4 loaded the matching
  BASE1 DEMO, which reported CPU 02, calculated 1235 and returned key K as 4B.
- MAP M1/M2/M3 passed. B0:F showed W+ for its known WDC resident bytes; this
  does not qualify the whole bank or booting it. BASE1 displayed SNBT sequence
  000003B8 and preserved policy.
- CONFIG B/C/W inspection matched the original policy and expected counters.
  OPAQUE loaded and Q returned to recovery. No setting-changing forms, I,
  install frames or sector writes were sent.
- The surviving immutable DEMO bytes were independently compared through the
  resident readback service. The 0200-0202 trampoline overlay was recorded;
  those three original code bytes are not claimed as independent readback.
- Disconnect was requested through the production Session API after its first
  payload chunk over real COM4. It deferred close, delivered the exact BIN,
  allowed the demo to run and completed the idle/drain interval. Native F10
  connect/disconnect was separately exercised at idle.
- Every later flash read still matched the upgrade postimages. Original full
  owner RAM/ZP restoration was verified after each acceptance group; the native
  trial also saved two complete restored RAM/ZP readbacks.

Final state: REC>, COM4 released, no pending RAM restore/reset/worker. The saved
default is still B. Retained b15 MON A/B and FLASH images have not been executed
under BASE1 and are not declared private-ABI compatible. Do not let a later
reset timeout into old MON B when a recovery entry is intended.

## Limits and remaining release work

This closes the known-b15 happy-path upgrade and preserving 2512 BASE1 case,
not all supported-platform or destructive acceptance. CONFIG save/persistence,
opaque programming/boot, power/interrupted-F repair, 816/ACIA coverage,
legacy-image execution compatibility and WDC migration remain separate.
All console button aliases were not individually clicked.

Both recorded BASE1 physical entries had one leading FF byte before WAIT.
The saved pre-upgrade b15 physical entry has the same leading FF, so this
observation predates the upgrade. Raw bytes were retained; the cause is not
established. Exact following
identity/recovery, binary transfer, CRC and complete-bank/RAM checks passed.
No F change was made to address a reset-prefix observation.

F and its source lock remain frozen. No firmware build or CPU simulation was
run during the trial. Existing candidate/source ZIPs and the direct 4K kit BIN
were hash-checked unchanged. No kit update or publication occurred. Source
release manifests remain the previous package snapshot; this local acceptance
receipt is not yet integrated into those archives.

Closing the remaining write/migrator gates requires a separately approved
scratch/fixture with an exact preservation/wear plan. Erased B0:9 is not an
implicit scratch allocation; 2205 remains excluded. Power-cut trials require an
admitted repair/programmer procedure before execution.
