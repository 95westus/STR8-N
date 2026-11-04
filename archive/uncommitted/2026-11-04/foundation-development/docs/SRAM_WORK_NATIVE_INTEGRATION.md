# SRAM/WORK native integration after RAM qualification

November 1, 2026. Historical design notes. The later g2 implementation is
[installed and accepted on both boards](STORAGE_NATIVE_ACCEPTANCE.md).
The planning figures below describe g1; final g2 uses 10,370 library bytes
and leaves 1,884 bytes in its three-sector slot. Interactive BATCH entry is
currently refused. The occupied CLOCK replacement and 2512 D rotation were
separately reviewed and approved; these notes themselves authorize no write.

Reuse one combined SRAM/WORK library rather than duplicate its mount, SPI,
CRC and layout code in two applications. The qualified RAM candidate is
10,231 bytes. A 32-byte native header plus a whole-image CRC fits three
4 KiB sectors, leaving 2,023 bytes. Store the compact $2000 library, not the
raw BIN's padding between its $0200 bootstrap and $2000 entry.

The existing native loader at B3:$8C00 already saves ZP/MON state to
$5C00/$5D00 and loads native overlays at $2000. Extend its admitted kind
table and length checks for the shared storage library. The library retains
its own quiet MON return. Its resident WORK API is private to the loaded
tool and does not change Foundation's frozen ABI.

Expose `R SRAM` and `R WORK` as distinct console entry selections into that
one payload. Keep bare SRAM/WORK queries available without forcing a full
tool load. APPS must distinguish the manager from a query alias. Update help
only when the routes actually exist. Use a separate entry-selection byte:
`SW_MODE` already holds the SPI mode returned by RDMR and cannot double as
the console route. A raw BIN must clear/initialize its route explicitly.
Named-tool Q should return directly to MON; the combined RAM prototype's
submenu Q currently returns to STORAGE.

The loader currently seals `NL,1,3,PR05` and supports three native kinds.
Update both that admission header and the WB expectation when extending
the kind table. SRAM and WORK can map to one physical image kind rather
than duplicate the payload. The new WB must safely refuse the old loader;
the old WB must safely refuse the new loader during a staged installation.
Changing WB's generation/seal also requires the matching service seal.

BATCH needs an explicit rule before these routes ship: entering an
interactive manager must stop/refuse the queued handoff cleanly, or use the
existing checked parent/continuation contract. A quiet MON return by itself
does not prove BATCH continuation. Exercise Q, cancelled confirmation,
failed admission and selected-bank return on both CPU profiles.

Space is tight in both the workbench and B3:E dispatcher. Reuse native-name
dispatch and remove superseded query-alias glue; do not create another
resident SPI implementation. Review actual linker sizes once the changes
are ready, and build only the changed modules.

B1:B–D is a possible three-sector placement because native R CLOCK already
uses the current B2 CLOCK. Those B1 sectors contain a retained legacy CLOCK
record and are occupied owner/history data. They are not free scratch.
Review and archive the exact current record and obtain the required occupied
image replacement decision before using them. Alternatives must be compared
against the goal of retaining B0 for owner environments. F and C/D are never
payload storage options.

Native integration does not solve large Store sources: the manager currently
protects its $2000–$47F6 code by restricting CPU copy buffers to $0200–$1FFF.
Keep the existing independent wide PROGRAM loader, and finish a staged Store
path before claiming the full b35 storage workflow.
