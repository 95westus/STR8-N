# STR8-N rc1 user guide — candidate

Release scope and limitations: [rc1 qualification](README.md#rc1-qualification).

Target: **2.0rc1 generation 49**, CLOCK **1.11**, ASM **0.5**, FT245 console.
This candidate guide passed the bounded offline example/manual audit. General installation and
full recovery qualification remain open; ACIA and crypto are deferred.

## Recognize the console context

The monitor normally returns a bank prompt such as `B3> `. Programs have their
own prompts: `CLOCK>`, `ASM>`, `BM>`, `SRAM>`, `WORK>` and `EDU>`. A command's
meaning depends on its prompt. For example, monitor `S` stores a program in
flash, while CLOCK `S` is a status query. Use each program's help before a
write. Program loading and execution can replace application RAM.

At an idle monitor, `?` displays help. `VERSION` reports version information;
`APPS` lists available programs. `TIME` gives the time display. The utility
aliases `MAINT`, `SRAM`, `WORK`, and `EDU` also have `R name` forms. Named
programs such as `CLOCK` use `R name`; availability depends on the stored
program table. Launch the ROM assembler with the dedicated `ASM` command.
`Q` or `QUIT` returns from programs that advertise it.

For first-use board naming, confirmed UTC clock setting and fixed local-offset
setup, follow the [installed-board quick start](QUICK_START.md). Its examples
are setup actions for an idle board, not instructions to change an active
measurement campaign. A soak, snapshot or installer may own application RAM
and the serial port; these examples do not authorize competing with it.

## Read time and outage evidence

Enter `R CLOCK` in an authorized idle session. The opening display identifies
the board, UTC and fixed-offset local time, clock flags and remembered/device
identity. `TIME`, `STATUS`, `EUI`, `HISTORY`, and `SHOW n` inspect clock/history
information. `HELP` lists commands; `Q` returns. A stopped oscillator, invalid
calendar or identity mismatch needs investigation before treating a displayed
time as continuous trustworthy time.

`OFFSET` changes the display offset; it is not automatic daylight saving.
`SET` changes the RTC calendar and `TRIM` changes its rate correction. `ACK`
acknowledges power-fail evidence; history clearing and identity acceptance also
change persistent state. These commands are outside the current campaign.
Preserve raw captures and the baseline before any future authorized change.

rc1 retains beta35’s **estimated outage duration**, in days/hours/minutes, to
supported power-fail displays. Hardware down/up stamps lack a year and seconds.
The calculation anchors the up-event year to a trustworthy capture/calendar
year and infers the prior year for a wrapping down-event. It cannot prove
multi-year outages, second-level duration or lifetime availability. Invalid or
unanchored pairs must remain unknown; an estimate is not a measured precision.
PF/STATS output must be read with those limits.

## Work with programs and storage

The monitor's `D address [end]` displays memory, `G address` executes RAM code,
and `L` receives S-record input. `M` edits allowed RAM; `F` patches a selected
flash sector after preview and confirmation. It is not a RAM fill command.
Do not use either to probe I/O. Monitor `S`, flash installation, format,
repair, and configuration save are write operations. A matching address in
another selected flash bank names different storage.

The SRAM manager keeps named external-SRAM objects. WORK manages its workspace
allocation; its format/repair/upgrade operations are separate from listing
capacity. External SRAM is not directly mapped into CPU RAM. Firmware-owned
flash, C/D configuration/wear journals and retained user data have distinct
roles. A backup must include identity, hashes and the exact relevant contents;
a file named “backup” alone is not sufficient evidence of compatibility.

## Use BATCH with the correct expectations

`BATCH cmd;cmd` feeds a bounded list through supported monitor/utility readers.
The inline text budget is 34 bytes. Escape cancels; a failed or unsupported
command stops the batch. It is not a general scripting language or a safe way
to bypass confirmation. With coherent rc1 monitors and UX/3/42 providers,
validated active A0 and B0 both support native utility and CLOCK handoffs.
Only exact `R CLOCK` and `R 1 CLOCK` forms are admitted for CLOCK in BATCH;
the registered BT/1/1 header must also validate. Wrong banks, longer names,
arguments and arbitrary applications remain unsupported. `BATCH ASM;VERSION`
stops at ASM. A mixed old/new provider set does not acquire the rc1 capability.
The frozen beta35 A-slot issue remains separate; rc1 does not alter beta35.

Read-only examples, verified offline in both rc1 slots:

- `BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q`
- `BATCH R CLOCK;STATUS;Q`
- `BATCH R 1 CLOCK;TIME;Q`


## Recovery and the protected campaign

The fixed F recovery core is separate from monitor A/B. Entering it, resetting,
or installing firmware interrupts normal operation and is not part of this
campaign. Offline interruption models do not establish electrical recovery.
If an installer reports failure, retain its transcript and full images: a late
error can occur after a valid target commit. Inspect durable state before any
retry; a failure message does not establish that the previous version remains
selected. Wear-aware restoration writes new count-preserving journal records,
rather than replaying old backup counters.

The current baseline is immutable. Periodic 2604/2609 samples compare RTC against
NIST with timing uncertainty; 2205/2512 remain powered off. Historical 2512
observations are retained, not current samples. A single
offset is not a drift rate, and an interval spanning zero is not evidence for a
trim correction. Power-off drift requires another capture after an owner
reports power return. No campaign clock/trim/settings changes are authorized.

## Source and evidence

- CLOCK command text and implementation (repository reference: `release/candidates/rc1/source/clock/clock.asm`)
- Outage year inference (repository reference: `release/candidates/rc1/source/clock/outage-duration.inc`)
- Monitor help, aliases and BATCH (repository reference: `release/candidates/rc1/source/xip/utilities.asm`)
- Migration support boundaries (repository reference: `STR8N_RC1_2604_INSTALL_RECOVERY.md`)
- [ASM guide](ASM_GUIDE.md) and [command reference](COMMAND_REFERENCE.md)

The same firmware supports 65C02 and 65C816 emulation-mode runtime. Native
816 applications/testing, ACIA and crypto remain deferred. The existing startup
CPU detector briefly enters native mode before restoring emulation; this
startup exception was explicitly accepted by the owner.
