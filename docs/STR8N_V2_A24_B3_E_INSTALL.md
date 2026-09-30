# Alpha24 guarded Bank 3 E installation

The optional B3:E sector holds the binary SAVE/RESTORE/TABLE extension. The
WDCMONv2 migration script installs B3:F only. This guide builds a separate
RAM-resident `.s19` installer for **one exact B3:E/F readback**. The builder
does not contact the board. It needs Python 3 and the extracted alpha24 ZIP;
it does not need the WDC assembler or linker.

## Prepare the exact board image

First install and verify the alpha24 B3:F monitor. Obtain a byte-exact 8192-byte
binary of that same board's B3 `$E000-$FFFF`, with E as the first 4096 bytes and
F as the next 4096 bytes. A full 128 KiB T48 chip read can supply it: extract
offsets `$1E000-$1FFFF` inclusive. Retain the full-chip backup and its hash.
Do not use a generic E/F image, an image from another board, or a text dump as
the readback. The builder checks that the F half equals the packaged alpha24 F.

From the extracted ZIP directory, run:

```powershell
python .\TOOLS\BUILD-B3-E-UPDATER.py .\my-board-b3-ef.bin --out .\my-board-e-install
```

The tool produces `str8n-v2-alpha24-b3-e-guarded-install-2000.s19`, a staged
E-page BIN, and `b3-e-installer-manifest.json`. It preserves the exact input
bytes at `$E000-$E7FF` and `$EF00-$EFFF` and replaces only `$E800-$EEFF` with
the alpha24 S/R code. It refuses an input with the wrong length, a different F
image, or an E sector that already contains the same code. It never writes
the board. Keep the readback and manifest with the generated installer.

## Install on the same board

Confirm that B3:F still matches the alpha24 F BIN and that the live B3:E still
matches the readback used to build the installer. Select B3, load the generated
S19 with monitor `L`, then execute its S9 entry using `G 2000`. The RAM updater
checks the **entire live B3:E** against the embedded old image before it offers
`B3:E exact; TYPE Y to repair>`. Only enter `Y` after that exact-match prompt
and when board power is stable. Do not reset or remove power during the erase
and program. Wait for `B3:E VERIFIED; RESET`, then press physical RESET.

Read back B3:E/F and compare E to the staged BIN and F to the packaged F BIN.
Check that `T 3` no longer reports `SR unavailable`, then perform a bounded
S/R save, table, and restore in a deliberately chosen erased flash span. The
installer itself does not allocate S/R storage. Normal monitor
`I E000 EFFF` remains protected for resident B3.

The updater refuses a changed E preimage before any flash write and attempts
to restore the old E image if new-image verification fails. A failed erase or
power interruption can still require external-programmer recovery. Its
blank-E and patterned-E paths, changed-preimage refusal, cancellation, and
B0/B2/F preservation pass the CPU/flash model. Board 2609's earlier
exact-preimage E updater was installed and read back on physical hardware;
the new per-board builder has not yet been run on another physical board.
