# Candidate3: next 2512 acceptance

Completed November2,2026: see
[live acceptance](CANDIDATE3_2512_LIVE_ACCEPTANCE.md). The procedure below
remains the reviewed scope. The successful harness allowed ordinary buttons;
the two Shift shortcuts required physical keys. No physical RESET occurred;
the RAM DEMO used its documented software boot return once.

Scope:2512/COM4 only, the freshly extracted g10 candidate3. No flashing,
journal/metadata/settings writes, RTC administration, SPI data writes, reset
or power cut. F stays golden.2609 remains held;2205/2604 remain excluded.

1. Verify the extracted manifest and exact frozen F pin. The host preparer
   must retain all1024 RTC metadata bytes and C/D history. Compare all19
   targets against admitted bank captures. Identical targets mean no install.
2. Wait for RTC collection to finish. Check its shared lease, due time and
   restoration guards before opening COM4. Start only with a sufficient bounded
   window and an operator ready for the physical keys. Yield before the next
   collection; make no collector/baseline changes.
3. Capture fresh owner RAM0200-66FF and ZP00-DF. The native monitor captures
   the reader's displaced prefix first; then the extracted readback tool
   captures the remainder. Keep this escrow private and durable. Reject a
   changed board identity, F pin, profile or pending restoration state.
4. Verify the live profile against the19 extracted payloads without replacing
   an image. Inspect VERSION/APPS/TABLE and CLOCK read-only status as needed.
   Reprepare/refuse on a changed image or metadata; do not turn a mismatch into
   an automatic installation.
5. Run the extracted terminal0.1.2 with the guarded2512 USB identity. Physically
   press Shift+F2 and choose `examples/KEY-S19-3500.s19`, then Shift+F3 at the
   exact monitor RAM SEND S19 prompt. Verify a single S19 selection/send action,
   no accidental BIN action/autorun, and independent RAM3500-3503=`KEYS`.
   Check initial S19 cancellation separately. Native key events/dialogs are
   required; generated Tk events do not close this gate.
6. Use the indicated ordinary F-key to confirm the BIN path remains separate:
   cancel at SEND BIN before payload, then load the extracted RAM DEMO and
   return to recovery. Never select F.bin as a RAM program. All actual program
   bytes and terminal runtime must come from the extraction; host orchestration
   may supply lease/escrow guards but must not substitute workspace payloads.
7. Compare B3/boot/wear/metadata to its preimage, read back the S19 test bytes,
   and restore/read back the exact fresh owner RAM/ZP even after a failed test.
   Disconnect/release COM4 and clear guards only after restoration succeeds.
   Final REC>, RTC eligible. User delay or a collection request stops the trial
   cleanly rather than starting another transfer.

Host extraction/preparation is separate from live acceptance. The first pass
has proved19 targets identical to the archived2512 profile; it has not connected
to the board. No firmware rebuild is needed. A source-only rebuild from the
extracted snapshot, targeted latest816 coverage and factory restoration remain
separate disclosed limits. Factory restoration cannot run under golden-F scope.
