# Board 2512: bso2 in Bank 2, historical proof

On 2026-09-24, board 2512 ran STR8-N 2.0a21 in Bank 3. Bank 2 initially
contained erased `$8000-$EFFF` and an alpha20 recovery top sector. A complete
32 KiB readback matched that baseline (SHA-256
`4db1ef31a4b94436dfa898493ac24de79ad09c6bc6e746b6890f1cfac349dc9f`).
The owner-local readback preserves the former Bank 2 recovery copy.

The requested [bso2](https://github.com/wlp1963/bso2) source at commit
`5e0498070101bcb0e3979c53b770307f112fadf2` assembled and linked with WDC
tools. The first Bank 2 image was wrong in two ways:

1. The upstream `-HZ` `bso2.bin` is a loader stream with 24-bit address and
   length records. It was initially treated as one flat ROM payload, placing
   record headers into executable code from `$C01B` onward. That image
   flashed and read back exactly but `J2` produced no console response. This
   demonstrates why flash readback alone did not prove a working guest.
2. WDC02AS encoded the source instruction `BIT USB_CTRL_PORT` as zero-page
   `BIT $E0`, although the FT245 status port is `$7FE0`. The owner-local build
   uses explicit `BIT $7FE0`; its listing shows `2C E0 7F`.

The corrected image places all 13 nonempty loader records at their declared
addresses, retains the verified Bank 0 WDC serial ROM routines in Bank 2's top
sector, and points NMI/RESET/IRQ to `$8007/$8004/$800A`. A 65C02/SXB I/O
model reached the `POWER ON` USB output. STR8-N's `B2> I 8000 FFFF` reported
`Done`; the subsequent 2048-row readback covered every address from `$8000` to
`$FFFF` and matched all 32,768 candidate bytes. The Bank 2 SHA-256 is
`969f6b3c9e8c2080a63b0c495228668fb3a0b2b19a0242bf675b02dfc9d776d2`.

On hardware, `J2` reached bso2. The first boot printed `POWER ON`, accepted
`M` at `C/M`, and answered `?` with short help. In the operator's later session,
physical RESET again produced the STR8-N 2.0a21 Bank 3 banner; `J2` then
printed `RESET TRIGGERED` and `C/W/M`. `M` entered the monitor. `IVI` and
`I D` returned usage text; `G 0078` returned `USAGE: G`; `M 78` refused the
protected low-memory range until `!M 78` was used. `I I 1`, `I X`, and
`I O A` returned information. `I M 1` enabled the command panel,
`M` displayed it, and selection `5` completed the guess game. `Q` entered its
documented halt; NMI released it to the monitor. A second NMI captured the
parser and returned to the prompt. The repeated `WANT TO PLAY A GAME?` prompt
corresponds to the observed `$0078=01` flag; the operator accepted that
behavior. No broader command or peripheral qualification is inferred.

The initial failed image, corrected image, build, full before/after readbacks,
and serial logs are retained owner-locally under
`output/qualification/board-2512-bso2-install-2026-09-24/`. The former
alpha20 recovery sector is saved there and is no longer in Bank 2 flash.
