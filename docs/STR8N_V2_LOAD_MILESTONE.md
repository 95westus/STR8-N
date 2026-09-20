# STR8-N v2-alpha3 load and cancellation milestone

Historical milestone. The current build adds
[F/I flash editing and installation](STR8N_V2_FLASH_MILESTONE.md).

Adds load-only `L` and safe Ctrl-C to the [B/D/M/G/J monitor](STR8N_V2_MONITOR_MILESTONE.md).
The same binary runs in each bank on either CPU, with the 816 in emulation
mode. F/I, configuration, and autostart remain pending. This build has not
been installed or tested on physical hardware.

## Load RAM

Enter `L`, then send S19 text. S0 headers are checked and ignored. S1 records
load only into `$0200–$68FF`; every record must fit wholly inside that range.
Each record is buffered and checked for structure, count, checksum, line
ending, and permitted addresses before any of its bytes are written. S1
payloads may contain 1–252 bytes. Sparse and overlapping records are accepted;
later accepted bytes replace earlier ones. Uppercase/lowercase hex and CR,
LF, or CRLF endings are accepted; spaces inside records are not.

A valid S9 after at least one S1 ends the transfer and prints `Loaded; entry
hhhh`. It does not execute that address or change the selected bank. Use
`G hhhh` explicitly afterward, subject to G's address rules. The S9 address
is informational and need not be inside the loaded range. Missing input
waits for more data or Ctrl-C; there is no transfer timeout.

Errors report `Bad S19 record`, `Bad S19 checksum`, or `Protected address`.
The current invalid record is discarded. Earlier accepted records remain
in RAM, so an error does not imply that RAM is unchanged.

## Cancel safely

| Operation | Ctrl-C behavior |
| --- | --- |
| Command entry | Discard the line and print `Cancelled`. |
| D | Stop at a row boundary, with the resident bank restored. |
| M | Cancel before committing, or finish the complete edit once its copy starts. |
| L | Discard a partial record; finish any record already being copied. Retain earlier records. |
| B/G/J | Check before changing selection or transferring control. After G/J, input belongs to the launched program. |

Input is also polled while console output is blocked, allowing cancellation
to unwind an active operation. The cancellation message itself waits until
the host accepts output again. A bounded 64-byte typeahead queue preserves
ordinary input while checking for Ctrl-C. Overflow discards input through a
line ending and reports `Bad input`; it cannot execute a truncated edit.

For an L error or cancellation, stop the host sender before entering more
commands. The monitor discards buffered transfer data and waits for 8192
consecutive empty hardware polls before returning to the command prompt.
This is a quiet-input drain, not a protocol acknowledgement or fixed time
guarantee. A continuously sending host delays the return; a sender that
resumes after the quiet interval can supply input to the command prompt.

NMI dispatch is gated during the short RAM copy, as for M's pointer update;
an NMI arriving in that window is acknowledged without replay. IRQ remains
disabled. Future flash commands must finish the active mutation/verification
before cancellation can return safely; cancellation is not rollback.

## Build and evidence

Run `make v2-check`. It builds using WDC02AS/WDCLN and executes the boot,
monitor, and load/cancellation suites with py65. The boot suite also checks
actual v1.35 J0/J1/J2 launches into this image and J3 back to v1.35, using
the existing v1.35 binary/map and bypassing only its long startup delays.

Artifacts are under `BUILD/v2-alpha3/`:

- `str8n-v2-alpha3-e000-ffff.s19` and `.bin`
- `build.json`
- `test-results.json`, `monitor-test-results.json`, `load-test-results.json`

Resident code/data occupy 2205 bytes, including the 105-byte RAM worker and
57-byte interrupt entry image. There are 1859 bytes free before `$FFE0`.
The typeahead queue occupies `$7D40–$7D7F` within the reserved state page;
record buffering uses the existing `$7C00–$7CFF` input page. No application
RAM reservation grew. Older milestone artifacts remain separate.

Tests cover maximum-length records, all byte values, page/range boundaries,
256-record transfers, malformed input, partial records, retained prior writes,
mid-copy cancellation, pre-jump cancellation, long-display cancellation,
blocked output, queue wrap/overflow, and the existing boot/monitor checks.
These model logical execution, not electrical timing or native 816 operation.

## Install using v1.35

Use v1.35 I to install the alpha3 E-F image into a disposable Bank 0–2,
then use the matching J command. Both E and F sectors are replaced. Keep
v1.35 in Bank 3; v2 J3 returns there. No hardware installation was performed
as part of this milestone.

Host validation example (repeat with Bank 1 or 2 as needed):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/compose_str8n_install_s19.ps1 -PayloadS19Path BUILD/v2-alpha3/str8n-v2-alpha3-e000-ffff.s19 -PayloadStart 57344 -PayloadEndExclusive 65536 -Bank 0 -S19Path BUILD/v2-alpha3/validated-bank0.s19
```

The optional `python tools/build_v2.py --full-bank` recovery artifact also
replaces `$8000–$DFFF` with `$FF`. Run all three test scripts after that build
to generate matching receipts.
