# WB2 g6: STORE / TABLE / RESTORE command increment

Built once; the unchanged validated loader was reused. Complete command
words normalize to S/T/R without changing arguments or record formats.
BATCH validates the same normalization, so TABLE joins the existing returning
subset. STORE/RESTORE have not been added to that subset. Existing backend,
AREA, AUTO, confirmation and CRC behavior remains the implementation target.

Help text uses the full command names and removes duplicate wording. The
module retains its 4800-63FF code and 6400-66FF state bounds, with 29 bytes free.
Full b35 CLOCK/CONFIG and other shipping gaps are still open.

Build-only, not execution-qualified or installed. F and published downloads
are unchanged. No CPU model or hardware test was run for this increment.
