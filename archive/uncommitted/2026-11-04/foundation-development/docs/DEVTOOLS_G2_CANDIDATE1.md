# Developer tools g2 candidate1

Historical candidate1 preparation. Its live trial caught an origin/staging
mistake in the example before execution. The corrected candidate2 subsequently
[passed2512 extracted RAM acceptance](DEVTOOLS_G2_EXTRACTED_2512_ACCEPTANCE.md)
with identical firmware/terminal bytes. The candidate1 archive is retained.
This is an optional developer add-on above the existing Foundation/MON
environment, not a new unified system release or automatic installer.

Workspace ZIP:
`BUILD/devtools-g2-candidate1-20261102-r1/STR8N-DEVTOOLS-g2-candidate1.zip`.
It contains the accepted ASM/SF source increment and DBG g2 RAM/AP/02
payloads, Python serial terminal0.1.2, operator manual, commented example,
reference source, build pins and a file-set/hash verifier. No private board
capture, owner RAM, journal, RTC data or vendor WDC firmware is included.

The packaging receipt verifies exact installed2512 flash-image pairing,
extraction, every file hash, private provider identity and terminal --help.
There was no firmware build or device access. This does not constitute
live serial/keyboard acceptance from the new extracted kit.

## Original trial plan (superseded by corrected candidate2)

Use only files from the fresh extraction. Acquire the shared serial lease
after RTC collection and require a safe time window. Preserve fresh owner
RAM0200-66FF, ZP00-DF, cache6B00-77FF and BRK/HOLD hooks. Read/verify current
flash bank hashes before and after. Keep F and all images/settings/history
exact. No flash/journal, SPI-data, RTC-setting, reset or power-cut operation
is included. Do not access2609,2205 or2604.

1. Verify the extracted kit and open the included terminal's help. File
   selection/transfer checks must use this copy, not workspace payloads.
2. Load the exact extracted ASM-RAM.bin. Enter the numbered HELLO example,
   assemble, list symbols/output and verify A9 23 20 6D 7E 4C 67 7E. The
   corrected example uses ORG0200, matching physical staging at0200.
   QUIT; run0200; require # and a clean HOLD return.
3. Load the exact extracted DBG-RAM.bin. Check its seed stop, enter the same
   fixture with debugger M, set PC0200, then verify R/U/S/N/C and return.
   Repeat X cleanup, BC and cancellation with unchanged hooks.
4. Recheck the installed AP/02 R ASM/R DBG front doors against the packaged
   image hashes without writing them. Do not test source SAVE here: it
   would need a new explicit storage fixture allowance.
5. Verify all banks unchanged; restore/read back fresh owner RAM/ZP/full
   cache and hooks. Finish REC>, release COM4 and leave RTC eligible.

No flashing is needed for this gate. An816 emulation trial needs a separately
admitted2609 RAM scope; native816 developer operation remains excluded.
An extracted source-only rebuild is not qualified by packaging or these
operator tests. Published Foundation and Candidate3 downloads stay unchanged.
