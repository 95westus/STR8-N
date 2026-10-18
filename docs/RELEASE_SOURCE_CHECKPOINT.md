# Beta35 through rc1: source checkpoint

The published **v2.0rc1** tag remains immutable. This checkpoint preserves the
earlier beta35/bf1 source, planners, test harnesses and documentation alongside
the published rc1 source; it changes no released firmware or ZIP.

`release/beta35/build.py` is a closed source build: Python stdlib plus separately
installed WDC02AS/WDCLN. It regenerates embedded executable includes and checks
all 18 frozen artifact hashes (97 source files, 26 fresh links). Start with
`release/beta35/README.md`. `release/candidates/batchfix-r1` contains bf1;
`release/candidates/rc1` is generation 49. Release trees retain exact bytes
through Git so source/kit SHA-256 manifests survive checkout on either OS.

Historical prerelease/board harnesses under `tools` require the exact owner-local
fixtures, build caches and receipts named in each script. They are developer
and lab tools, not generic installation launchers or instructions to resume a
campaign. Personal runtime paths were replaced in public copies; original
hash-bound executed copies/receipts remain owner-local and are not relabeled.
The actual user migration/recovery tools are the qualified release ZIP's tools.

No captured banks, vendor/bridge firmware, EEPROM/SRAM images, serial logs,
private receipts or host credentials are committed. The one RAM CPU-observer
assembly file under `tools/qualification` is source and never enters native mode.

Current state: rc1 is installed on 2604 and 2609. Both monitor slots and all
supported apps passed checks; 2609 remained in 65C816 emulation mode. The
original monitor preferences and saved RAM archives were restored (loader
acknowledgment, no additional host readback). Clocks/trims were unchanged.
2205/2512 stay off. Soaks and RTC sampling remain stopped; RTC qualification,
native 816 apps/tests, ACIA and crypto remain deferred. Recorded stopped soak
results are accepted as recorded, not a full endurance pass.

The unrelated v2.1 branch and working files are preserved separately. No v2.1
source is added to this checkpoint. See [current manuals](rc1/README.md),
[beta35 scope](STR8N_V2_BETA35_SCOPED_ACCEPTANCE.md), and
[historical bf1 notes](STR8N_V2_BATCHFIX_R1.md).
