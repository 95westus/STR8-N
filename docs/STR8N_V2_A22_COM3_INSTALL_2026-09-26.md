# STR8-N 2.0a22 S/R/T installation on COM3

Date: 2026-09-26. The user made COM3 available and authorized Bank 2 as the
recovery destination, noting that its BSO2 contents can be reinstalled later.
This report records a scoped W65C02 board installation and S/R/T check. It is
not a full cold-boot or release qualification.

## Preflight and host backup

COM3 returned `B3>` at 115200 baud. A complete Bank 3 E/F dump had 512 ordered
16-byte rows. Bank 3 F matched the freshly rebuilt, source-built alpha21 F
image byte for byte, SHA-256
`0ddaa218bc49817aca4d44f4793140c901ac2963333fd8fa190bfcf01db7f4d5`.
This differs from the frozen RC1 alpha21 F image previously tested on another
board. `$E800-$EEFF` was erased; the configuration page included 16 non-`$FF`
bytes. The E staging tool preserved all read-back bytes outside `$E800-$EEFF`.

All 32 KiB of Bank 2 were read back before the update and saved at
`output/qualification/board-com3-a22-sr-2026-09-26/bank2-before-8000-ffff.bin`,
SHA-256 `0ef666998e191ffb6dfd90b29378fd22a75bfa1157e3f2e7390becb9283b46c2`.
The pre-install Bank 2 F slice had the frozen RC1 alpha21 F hash
`3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49`.

## Installation

1. While alpha21 remained in F, `I E000 EFFF` accepted the staged full E-sector
   S19 and reported `Done`. A complete E/F readback then proved E byte-exact
   against the staged image and F unchanged from the preflight image.
2. Alpha21 `L` loaded the a22 RAM updater at `$2000-$5FFF`. Its embedded
   `$5000-$5FFF` old-top image had to match the live Bank 3 F byte for byte
   before it offered either confirmation. `G 2000` showed the a22 install
   prompt. The operator-approved `BACKUP B2F` step reported `BACKUP VERIFIED`
   and old-top sum `$8255`.
3. The exact `STR8-N 2.0A22` confirmation installed Bank 3 F. The updater
   reported `STR8-N 2.0a22 VERIFIED; RESET`, entered the new reset vector, and
   reached `STR8-N 2.0a22 B3 65C02` and `B3>`.

The final full Bank 3 E/F readback matched both the preserved staged E image
and the assembled a22 F image byte for byte. Its E/F SHA-256 is
`9b58c3a177ce80b39eeff3d6f9c1fe88886041d7b7ad23c0d54a9e0a31202a67`;
the F slice SHA-256 is
`6c2288de66614e25cd04d75f701fd0d65981354e54a439dcc163fe04b4c29209`.

The final complete Bank 2 readback proved sectors 8-E unchanged from the
pre-install archive and B2:F byte-identical to the old Bank 3 F image. The
post-install Bank 2 full-bank SHA-256 is
`a8e53579495da810e4567f9a4125d3603e837a3f7cd9b07352244187ac44892b`.
The original complete Bank 2 image remains archived on the host. Bank 2 F
now contains the alpha21 recovery top, so Bank 2 is not byte-identical to its
pre-install BSO2 state.

## S/R/T board check

The Bank 3 `$8FE0-$902F` region read back erased before the test. `M` wrote
`12 34 56 78` to RAM `$2000-$2003`; `D` confirmed the bytes. Then:

```text
S 3 8FF0 2000 2003 TEST
Done
T 3
8FF0 2000-2003 0004 C TEST
```

The record crosses the `$8FFF/$9000` sector boundary. After `M` changed the
source RAM to four zero bytes, `R 3 8FF0` reported `Done` and `D 2000 2003`
again showed `12 34 56 78`. A second `S` at the occupied `$8FF0` returned
`SR error 02`. A readback showed the complete header/payload at `$8FF0-$900B`
and neighboring bytes still `$FF`. `J3` reentered a22 through its reset vector;
`T 3` still listed the complete record. The test record remains in Bank 3.

Host flash-model checks also covered the direct S/R ABI, 16-character labels,
pending records, malformed ranges, Bank 3 E protection, and configuration
updates preserving the E extension. The exact-image updater model covered
B2:F backup, installation, rollback, and rejection of a mismatched old F.

## Remaining limits of the initial installation

The initial board check used `J3` reset-vector entry. The ROM and record format do not
include a payload checksum, so later payload corruption is not detected by
`R` or `T`. Name lookup and automatic placement remain future work. Other
CPU, console, and board combinations are not qualified by this COM3 run.

The append-only serial transcripts and before/after BINs are under
`output/qualification/board-com3-a22-sr-2026-09-26/`.

## Cold USB follow-up and correction

The operator subsequently powered off USB. On reconnection, the board did not
respond until physical RESET was pressed. This fails the cold-start gate for
the initially installed a22 F image. The exact F image on that board was
`6c2288de66614e25cd04d75f701fd0d65981354e54a439dcc163fe04b4c29209`.

Code review identified a regression from commit `2898ffd` after the frozen
alpha21 RC1: progress dots moved `CON_INIT` before the reset delay. That
samples FT245 PWE# while the USB host can still be configuring the device;
the console choice is then latched. The user observation is consistent with
this cause, though no serial trace of the silent interval exists. The repaired
a22 image separates enabled autostart from monitor startup. After validating
an enabled configuration, it enters the configured hold countdown without a
USB wait, banner, dots, or other console writes. If FT245 is already ready,
`S` or Ctrl-C can hold the monitor during that window. If FT245 is absent,
it neither initializes nor polls the unqualified ACIA; the countdown and
guest handoff continue headlessly. The host model measured the minimum
configured window within 8.0–8.9 million cycles at the nominal 8 MHz clock
on both headless and FT245 paths. If autostart is disabled or invalid, monitor
boot probes FT245 readiness during 160 short wait intervals and prints dots
once FT245 is ready. Software prompt entry skips that wait. The E extension
and S/R/T interface are unchanged.

The corrected a22 F image is
`b1cdbc62db9429571a356b566931b6fdefb3c7fa991a4370a60226df380c6880`.
The exact-old-F repair updater was built from the retained full E/F readback;
its S19 SHA-256 is
`4ea3a5765da3eb2680c0baa0dff81b69fb572aff8dc4f35b64ef810e415ed1b2`.
The host model passed headless Bank 1 autostart with USB absent and with FT245
transmit blocked, the configured countdown, an available-FT245 `S` hold,
monitor dots, S/R/T, exact old-image preflight, B2:F backup, installation,
rollback, and mismatch rejection.

## Matched E/F repair

The exact-old-F updater backed up the first a22 F image in B2:F, then installed
the corrected F image in B3:F. The RAM updater verified the target and entered
the monitor, which printed 160 progress dots and returned `B3>`. Full readback
confirmed F SHA-256
`b1cdbc62db9429571a356b566931b6fdefb3c7fa991a4370a60226df380c6880`.
A following `T 3` stalled; physical RESET restored the `B3>` prompt. The
cause was a build linkage error: E calls private monitor addresses, which
changed when F was relinked. The repaired F and old E were incompatible.

A second RAM-only updater checked the entire live B3:E sector against the
retained pre-repair readback before offering confirmation. It replaced only
`$E800-$EEFF`, preserving the rest of E including configuration, and used the
existing RAM flash worker for erase, program, and verify. On failure it would
restore the old E image. B3:E reported `VERIFIED`; a complete E/F readback
matched the new paired images exactly. The E SHA-256 is
`265a28a5129296f674301d6759d3790727264232f7e8ed30730b41022ee94d51`;
the complete E/F SHA-256 is
`a08f31b9d36c366b01f2e1ff8de7361b53fca9b5af6c578e5a807cfc45c9c1c4`.
`T 3` then listed `8FF0 2000-2003 0004 C TEST`, and `R 3 8FF0` reported
`Done`; RAM readback showed `12 34 56 78`.

The F repair builder now requires an explicit paired-E flag when relinking F
changes E. Future installations must treat E and F as a matched pair; the
extension's published entry addresses remain fixed, but its internal monitor
calls are private.

## Bank 1 autostart configuration

At the user's direction, `C 1 1 V 0A` enabled Bank 1 RESET-vector autostart
with the configured 1-second hold. The board reported `Done`. Full E/F
readback showed exactly three changed bytes from the repaired pair: `$EFF1`
`00` to `01`, and the configuration integrity bytes `$EFFE-$EFFF` from
`0D 7C` to `0E 89`. The S/R/T extension and F image were unchanged. The
new configuration bytes are `01 01 01 00 00 0A 01 00 00 00 00 00 00 00 0E 89`;
the complete E/F SHA-256 is
`30d1a3be171fd2fa412096a002fcc2ec10bc0daf5157e9b4f9fc3da589c4bcb7`.
Bank 1's RESET vector read back `$F000`, and its code header contained
`SR 02 03`.

A 180-second receive-only COM3 capture was armed before the operator cycled
USB power off and on without pressing RESET. The capture received 74 bytes:
`RST H`, `STR8-N 1.35`, `BOOT WARM`, and `HIMON V 00.0915(2324)`, ending at
the Bank 1 `>` prompt. The operator confirmed that no RESET was pressed.
This passes the scoped cold USB power-on check: enabled autostart reached
Bank 1 without manual intervention. Serial capture after USB enumeration
cannot measure the headless 1-second hold directly; the host timing model
covers that interval. The raw capture is
`output/qualification/board-com3-a22-cold-start-repair-2026-09-26/cold-power-autostart-b1.raw`.

## Source refinement after the board check

The operator asked for progress dots during enabled autostart as well as
monitor startup. The installed COM3 F image does not print dots in its enabled
autostart hold window. The source now probes FT245 once per tenth and sends a
dot only when the transmit FIFO is ready. It continues the countdown without
USB, and also begins dots if USB becomes ready partway through the window.
The build fits exactly through `$FFDF`, with no byte free before vectors.
The host model passed headless handoff, late USB readiness and dots, an
available-FT245 `S` hold, and blocked-transmit handoff. This is a source-only
refinement: F SHA-256
`1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439`
and matching E extension code SHA-256
`fcb0a253fa802c5e44ce48bba22c4b004a49b6dfe8b6563a9d8891ea75875401`
had not yet been installed at this point. The previously observed cold-start
pass applies to the earlier repaired image, not this revised pair.

## Paired dot update on COM3

The operator made COM3 available for the update. A fresh full B3:E/F readback
matched the repaired F image and E extension exactly outside the operator's
configuration changes. Its E/F SHA-256 was
`a121f6c87dc47a5d58c61023c61bea40bcc0b6e460f79a5b4112b240cab08377`.
The configuration was enabled Bank 0 RESET-vector autostart with delay `$99`
(`01 01 00 00 00 99 01 00 00 00 00 00 00 00 9C 84`). A complete B2 bank
readback was archived before any write, SHA-256
`6403260611c3c50864b7e269bf6ccb78ea9526a76f32cb4952ef72287389d5a1`.

The paired updaters were built from those live bytes and passed flash-model
checks for exact old-image preflight, E rollback, F backup/recovery, and
mismatch/cancel rejection. E was installed first through a RAM-only updater,
which reported `B3:E VERIFIED; RESET`. Full E/F readback matched the staged
new E sector exactly, with F and configuration unchanged. The F updater then
verified the B2:F backup and reported `STR8-N 2.0a22 VERIFIED; RESET`.
Its restart printed 49 dots before `S` held the monitor at `B3>`.

Final full E/F readback matched both candidate sectors byte for byte. The E
SHA-256 is `db2479f3c8c2c7138f0148eeb4b4d99755d4bdefefcd5abfc30133d1dd973273`,
F is `1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439`,
and complete E/F is
`e0f33009b5f39f3be7c85bfb9900166ef3ef6ee1ce2076fa4ced2edad61ba3fc`.
The preserved configuration read back unchanged. Full B2 readback proved
sectors 8-E unchanged and B2:F byte-identical to the old B3:F image; B2 full
SHA-256 is `d1a6d02d50fa6817fa65563225f62b1080ecc27d9fb33737159cb7973350526d`.
`T 3` listed `8FF0 2000-2003 0004 C TEST`; `R 3 8FF0` reported `Done`
and RAM readback showed `12 34 56 78`.

The update artifacts and append-only COM3 transcripts are under
`BUILD/v2-alpha22-dot-update/` and
`output/qualification/board-com3-a22-dots-2026-09-26/`. A receive-only COM3
capture of the subsequent startup recorded 148 leading dots followed by the
Bank 0 EDU Kit banner and `>` prompt. The 701-byte raw capture has SHA-256
`5170ade8000d7a0fc9e8468690386e1eba9ee1a45e6ad765c63f5a1da9abb50b`.
The operator confirmed USB power was turned off and back on without pressing
RESET. This passes the scoped cold USB power-on check for the dot-enabled
E/F pair: the enabled `$99` hold printed dots after FT245 became ready, then
launched the configured Bank 0 guest without manual intervention.

The subsequent [COM3 regression sweep](STR8N_V2_A22_REGRESSION_2026-09-26.md)
rechecked the installed pair, monitor and extension behavior, RAM ABI,
BRK/IRQ/NMI, and physical RESET after the operator changed configuration to
disabled Bank 0 delay `$0A`.
