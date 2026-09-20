# STR8-N v2-alpha4 flash milestone

Historical milestone. The current build adds
[configuration and autostart](STR8N_V2_CONFIG_MILESTONE.md). Alpha5 also
corrects I's preservation of configuration to the resident bank only.

Adds `F` and `I` to the [alpha3 monitor](STR8N_V2_LOAD_MILESTONE.md).
No directory, enrollment, journal, or HIMON dependency is introduced.
Configuration commands and automatic startup remain pending. This firmware
has not been installed or tested on physical hardware.

## F: edit flash

```text
B1
F 8123 00
```

F accepts hexadecimal addresses `$8000–$FFFF` in every selected bank. One
command may edit multiple consecutive bytes, wholly within one 4 KiB sector.
Before writing, it displays the bank, each address with `old>new`, and
`Program` or `Erase/rewrite`. Confirm with exactly `Y` followed by Enter;
other responses cancel. Invalid input anywhere in the command prevents all
writes. `Crosses sector` rejects an edit spanning sectors or wrapping FFFF.

Unchanged bytes are skipped. Changes containing only 1-to-0 transitions use
byte programming. Any 0-to-1 transition uses a complete sector snapshot,
erase, rewrite, and verification, preserving every unedited byte. Even the
direct-program path verifies the complete resulting sector.

F can edit configuration, vectors, Bank 3 recovery code, and STR8-N itself.
A Bank 3 top-sector preview says `Recovery sector`. A resident-bank top
edit also says `STR8-N self-edit; reset required`. After confirmation, its
entire mutation, verification, result output, and hold execute in RAM. It
prints `Done; reset` or `Flash failed; reset` and never returns to old ROM,
including on a no-op edit. The operator must reset or arrange external
recovery. An edit can make the reset vector or monitor unusable.

## I: install a range

```text
B1
I 8000 EFFF
```

The inclusive range must cover complete sectors: start at `$x000`, end at
`$yFFF`, with start at least `$8000` and end not below start. The preview
identifies the bank/range and says `replace; erase as needed`. After `Y`,
the monitor prints `S19`; begin the transfer then.

I always protects the resident bank's `$F000–$FFFF` and Bank 3's
`$F000–$FFFF`. It permits those addresses in other guest banks. A forbidden
range is rejected before confirmation or mutation; F remains the explicit
way to override top-sector protection.

Send S0/S1/S9 text using the same hex, checksum, and line-ending rules as L.
S1 data must cover the requested range exactly once, in ascending order,
without gaps or overlaps. Records can cross page and sector boundaries.
Each record is validated in full before staging its data. Only complete
sectors are committed; each is programmed directly when possible or erased
and rewritten when needed, then verified. S9 is accepted only after the
entire range has been supplied. Its entry address is not executed.

The stream must include `$EFF0–$EFFF` if it covers sector E, but I preserves
the sixteen existing configuration bytes in that sector in every target
bank. Use F to replace them deliberately. Thus an installed E-sector image
can differ from the incoming data at those sixteen addresses.

`Done` means all requested sectors verified and S9 was accepted. A later
checksum, ordering, transfer, or flash failure leaves previously committed
sectors in place. An incomplete staged sector is discarded on cancellation
or transfer failure. There is no journal, rollback, or all-image atomicity.

## Cancellation and failures

Ctrl-C cancels before mutation or after the active sector's mutation and
verification finish. It never abandons a sector merely because Ctrl-C
arrived during erase/rewrite. A hardware failure can still leave a damaged
or partially programmed sector and is reported as `Flash timeout` or
`Verify failed`. A self-edit always ends at its RAM hold, even if Ctrl-C
arrives while writing.

I retains pending S19 input while polling for cancellation at sector
boundaries. Cancellation is recognized as that input is consumed; a
Ctrl-C behind already buffered transfer bytes is not an out-of-band signal.
Stop the host sender before entering new commands after an error/cancel.
The existing quiet-input drain discards the transfer tail before returning
to the prompt. A sender that resumes later can feed the command prompt.

The worker uses the existing v1 unlock addresses/sequences and bounded
program/erase polling. It checks every erased byte before rewrite and the
complete desired sector afterward. It resets flash read mode and restores
the resident bank before an ordinary return. All-red LEDs indicate the
active flash mutation; the running indication is restored afterward.

IRQ is disabled and RAM NMI dispatch is gated during mutation. This does
not make a CPU's NMI vector fetch safe while flash is busy, nor does it
control another bank's handlers. Flash/NMI behavior, device polling limits,
console flow control, and electrical timing remain hardware qualification
requirements on both boards. The 816 remains in emulation mode.

## Build, size, and tests

Run `make v2-check` for the WDC build and all four execution suites: boot,
monitor, load/cancellation, and flash. Tests use a banked flash model that
enforces unlock command sequences, delayed busy completion, and 1-to-0
programming. They inject program/erase timeouts, erase verification failure,
neighbor corruption, and cancellation during mutation. Self-edit checks
reject ROM execution after mutation starts. These are host checks, not
claims of hardware validation.

The end-to-end installer check programs the actual alpha4 E-F image into a
guest bank using I, boots it with J, and returns to the original monitor.
The separate v1.35 launch/return checks and installer image validation for
Banks 0–2 also pass.

The resident image is 3486 bytes, including the 493-byte RAM worker and
57-byte interrupt image, leaving 578 bytes before hardware vectors at
`$FFE0`. The worker fits the existing `$7900–$7BFF` reservation. The 4 KiB
buffer and application RAM boundaries are unchanged.

Artifacts are under `BUILD/v2-alpha4/`:

- `str8n-v2-alpha4-e000-ffff.s19` and `.bin`
- `build.json`
- `test-results.json`, `monitor-test-results.json`, `load-test-results.json`,
  and `flash-test-results.json`

The E-F image can be installed into a disposable Bank 0–2 using v1.35 I,
then launched through its corresponding J command. Keep v1.35 in Bank 3
for the J3 return path. This image replaces both E and F sectors.

Host validation example:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha4/str8n-v2-alpha4-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha4/validated-bank0.s19
```
