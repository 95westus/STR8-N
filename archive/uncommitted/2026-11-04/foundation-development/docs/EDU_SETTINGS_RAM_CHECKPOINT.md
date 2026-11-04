# Saved EDU development checkpoint

November 1, 2026. Installed EDU selection is still session-only. No persistent
EDU record has been written and no new MON image has been flashed.

The proposed ED/1 record shares the existing board-metadata arena at B3:9C00–9FFF
with name/offset/battery records, separately from the C/D boot/wear journal.
Each32-byte record carries a sequence, ON/OFF mode, reserved bytes, CRC16 and
commit byte. No valid record defaults to ON for compatibility. An equal newest
sequence with conflicting modes is refused rather than choosing arbitrarily.
This format is a development proposal until the confirmed writer is qualified.

## Accepted RAM reader

The220-byte helper passed seven synthetic CPU-RAM cases on2512: no record,
saved OFF, newest ON, ignored uncommitted/reserved records, conflicting newest
records, a newer conflict-resolving record, and ignored zero-sequence/invalid-mode
records. No flash, SPI data, RTC settings or boot/wear records were written.
Full B3 remained unchanged; fresh owner RAM/ZP were restored and read back.

Evidence: `output/qualification/2512-EDU-settings-RAM-20261101-r1/report.json`.
Build: `BUILD/edu-settings-g1-ram-r1/manifest.json`.

## Integrated startup/help accepted in RAM

The gE RAM monitor passed nine live2512 cases: cold default ON, saved OFF,
newest ON, conflicting newest records, corrupt-container refusal, wrong-helper
identity refusal, absent-helper fallback, warm session OFF and warm session ON.
VERSION retains the admitted session mode. Shared help appears only when the
complete helper container CRC and identity pass; otherwise minimal help remains.
The setup stub restores the exact linked entry before entering cold/warm MON.

Synthetic records stayed in CPU RAM5000-53FF; the sealed helper/help container
was copied from4000 to7000 before MON startup. No actual metadata record was
written. Full B3 remained unchanged, owner RAM/ZP and original EDU session were
restored/read back, and2512 finished at REC> with COM4 released.

Evidence: `output/qualification/2512-EDU-startup-RAM-20261101-r2/report.json`.
Build: `BUILD/mon-gE-settings-RAM-integration-r1/manifest.json`.
The first harness packet exceeded the host loader's size limit and was rejected
before transmission. Its failure and verified owner-restoration receipt remain
under `2512-EDU-startup-RAM-20261101-r1`; the admitted BIN limit was not raised.

## Installed ROM; confirmed save and reset checks accepted

The subsequent [named-copy/EDU candidate](NAMED_EDU_2512_SCOPE.md) adds the
confirmed writer to BANK MAINT. Live CPU-RAM fixtures passed exact OFF/ON
publication, no-op/cancel, full/incompatible arena and pre-commit backend-failure
cases. The owner approved the12-erase scope, and gE plus both packed utilities
are installed on2512. Actual ROM decompression and MAINT-to-SRAM-to-MAINT
handoff passed. Both approved ED/1 records are now written and independently
verified: OFF at9D80/seq1, then ON at9DA0/seq2. Repeated saves added no record.
After the owner's reported first reset, MON B gE was observed with EDU OFF;
the original receiver had expired, so its startup banner was not captured.
Exact B3 and pre-reset owner RAM/ZP restoration passed. The final physical
ON/default-B startup was captured in full and passed; final saved mode is ON.
The [acceptance checkpoint](NAMED_EDU_2512_ACCEPTANCE.md) records scope and limits.
Final family evidence: `output/qualification/2512-named-EDU-RAM-20261101-r5/report.json`.

MON gE has a cold-start hook to apply the admitted helper before automatic
status reads, preserving session selection on warm returns. Shared help and
the reader are intended to fit within the existing native-loader image padding
at8E90 and8F80. A full-image CRC and helper identity guard precede execution;
an absent helper leaves the default mode and minimal help available.

The single gE build succeeded: each ROM body is3954 bytes, leaving14 bytes
of its3968-byte body budget. The RAM variant is3945 bytes. This is build
evidence for size. The reader/help ROM padding is now installed and independently
verified; confirmed metadata writing and reset checks have passed. The RAM variant's
`--settings-ram` option uses synthetic settings/helper addresses; its isolated
integration trial passed as described above, not as ROM installation evidence.

Build: `BUILD/mon-gE-settings-r1/manifest.json`.
Foundation0.3.0 g1 BASE1/PR05 and its frozen sources remain unchanged.
Installation receipt: `output/qualification/2512-named-EDU-installed-20261101-r1/report.json`.
The unchanged LED sampler passed gE qualification with exact RAM/LED restoration.
Two native TIME/NIST bursts encountered intermittent `RTCC error $04`; their
failure receipts remain intact, and native TIME readmission stays open.
