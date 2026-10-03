# Unified WDCMONv2 to STR8-N 2.0a24c1 installer

Build with `make v2-config-wdcmon`; check the linked installer with
`make v2-config-wdcmon-check`. Output is under
`BUILD/v2-a24c1-wdcmon-ram`:

- `str8n-v2-a24c1-wdcmonv2-install-2000.s19`: RAM installer at $2000.
- `str8n-v2-a24c1-f000-ffff.bin`: exact 4096-byte F-sector transfer.
- `manifest.json`: image and installer hashes.

The same S19 uses SEC / $FB / SEI on both processors. $FB forces emulation
mode on the 816 and is a one-byte NOP on the W65C02S. The installer retains
the alpha24 flash/console engine, with a24c1 image checks and a selectable
backup policy.

Use the COM-port launcher from the repository root or extracted release kit:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\INSTALL-A24C1.ps1
```

Enter the board COM port. At the physical RESET gate, press and release RESET,
wait two seconds, then press Enter in PowerShell. Confirm the physical label
with uppercase `W65C02SXB` or `W65C816SXB`. Let the bridge load and verify RAM;
do not reset during loading. Permission applies to this PowerShell process.

Cyan means information; yellow means input, RESET or write activity; green
means success; red means refusal, cancellation or failure. Colors are added
by the bridge and are not part of the firmware bytes or raw transcript.

At `BANK>`, type only `0`, `1`, `2`, or `NONE`, then Enter. At `SECTORS 8-F>`,
type a single sector such as `F` or an ascending range such as `8-F`, then Enter.
The backup uses those same sectors in the selected bank. Inspect the plan,
then type `BACKUP B3` to copy an erased range. An identical copy is reused;
occupied different data is refused. Other sectors remain unchanged.

`NONE` requires both `NO BACKUP` and `INSTALL WITHOUT BACKUP` exactly,
followed by the version-specific installation confirmation after BIN transfer.
Wrong confirmation cancels before installation.

Once backup policy is satisfied, press Ctrl-U to send the supplied raw BIN
at its transfer prompt, and finally enter
`INSTALL STR8-N 2.0A24C1`. After verified completion it waits in RAM for a
physical reset. The old alpha24 migration wrapper pins alpha24 hashes;
use the generic bridge above for these artifacts.

The installer requires stock WDCMON residency in B3. It replaces only B3:F.
A selected backup range must be completely erased or byte-identical to the
original B3 range; an occupied different range is refused before any write.
Bank 3 cannot be selected as the backup destination. Unselected banks,
sectors outside the backup range, and the rest of B3 are preserved. The installer
checks that B3 still matches its original whole-bank hash before installing.
The factory F configuration pocket at
$FFD0-$FFDF is erased.

This stock-board installer is not the updater for an already installed
STR8-N board. Use the separately documented guarded updater for installed boards. COM ports
and bank contents change between sessions; determine the connected board's
current firmware before choosing stock migration or an installed-board update.

The failure prompt offers `R` to retry installing the intact candidate in
RAM. `O` restores the original F from the selected backup only if that
verified range includes F. With `NONE`, or a range ending before F, `O`
does not write flash. Backing up only `F` provides recovery for the sector
this installer replaces; `8-F` saves the complete original bank.

Validation covers linked RAM layout, unified entry bytes, image identity,
checksums, bridge S19 validation, and C02 model execution. The C02 checks
include selected-bank/range copying, preservation of neighboring sectors,
identical-range reuse, refusal of occupied ranges, both no-backup
confirmations, unified-entry migration, image/source guards, backup failure,
and refusal to restore F without an F backup. Physical C02 and 816 qualification of
this a24c1 installer remains pending; alpha24's board results are prior
evidence for the shared engine.
