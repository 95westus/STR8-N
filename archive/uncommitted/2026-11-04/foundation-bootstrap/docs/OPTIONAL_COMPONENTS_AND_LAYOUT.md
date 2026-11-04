# Optional components and discoverable layout

Design note, 2026-11-02. Scope: N-F / BASE1 and its optional system components;
this is not a change to the separate full-system RC1 layout or an installation
procedure. Relocatable journals and the directory proposed below are not implemented.

The subsequent [host-loaded FLASH/MAINT policy](LOADABLE_FLASH_AND_MAINT.md)
records the requested 2512 removal and the policy for later board migrations.

## The end user chooses what remains in flash

Installing an occasional utility in flash is a convenience, not necessarily a
permanent allocation. If an equivalent compatible RAM image can be loaded from
the host, or retrieved from optional EDU SPI SRAM PROGRAM storage, its flash
allocation can be repurposed. SPI SRAM is volatile storage, not flash; retrieval
still requires an available loader and its dependencies. A recovery-loadable BIN
does not by itself prove compatibility with the named PROGRAM launcher.

The unified build provides CONFIG, OPAQUE, DEMO, read-only MAINT, READBACK,
VERSION-client and EDU/SRAM-client RAM tools. FLASH has both flash placements
and RAM images linked at $0200. READBACK starts at $0200 and installs its worker
at $6800. These tools borrow application RAM; returning does not restore it.
Read-only MAINT is distinct from the full native BANK MAINT editor.

MON A and MON B occupy separate 4 KB sectors, B3:A and B3:B. Keeping one and
repurposing the other reclaims 4 KB; repurposing both reclaims 8 KB. F recovery
can operate without either monitor. Boot selection must remain valid, and
software requiring MON services needs an alternative or an installed monitor.
Removing both is therefore an end-user configuration choice, not equivalent
to transparently moving all MON functionality into a $0200 tool.

Native CLOCK, BANK MAINT and WB2 are also candidates for optional residency,
but their loader, service and return-context contracts must be checked
individually. In particular, the native CLOCK/BANK MAINT builder emits $2000
RAM overlays requiring an admitted native-loader context. A RAM BIN alone is
not evidence of standalone recovery operation. VERSION and EDU/SRAM RAM clients
likewise do not replace their VX1 and ES1 providers.

Reclaim means assigning whole erasable sectors after checking dependencies,
shared allocations and current contents. An unused utility's byte count is not
automatically an independently erasable allocation. F and the active C/D
boot-record/wear journals remain infrastructure in the current design.

## Would a component directory help?

Yes. A small, versioned layout record could describe where components actually
live rather than relying solely on fixed roles or a host-side board profile.
Useful fields include component role, bank/sector range, entry or load address,
length, interface version, generation, integrity check, dependencies and flags
for boot-critical, protected or replaceable content. Physical wear counts belong
to physical sectors even when their component roles change.

Start with an inventory that tools can display and validate. This can explain
which allocations are optional, detect overlaps and make reclamation reviewable.
An inventory record does not itself make any component relocatable: every
consumer must use the resolved location, and code may still require relinking,
a copy-to-RAM wrapper or a stable service interface. Unknown or conflicting
records must not grant permission to erase a sector.

## Journal discovery and wear leveling

Recording the journal locations could support a future pool of journal sectors,
instead of concentrating journal erases in C/D. It is particularly useful for
hot metadata; moving rarely updated utilities offers much less wear benefit.
A directory alone provides no wear leveling. Allocation policy, durable erase
reservations, physical-sector accounting and power-loss-safe rotation are also
required. Reserve capacity for the next committed copy before retiring the old.

There is a bootstrap constraint: F must find the journal before trusting settings
or wear history held in that journal. A pointer stored only inside the journal
cannot solve discovery. Options include a small fixed redundant locator or a
bounded scan of eligible sectors for self-identifying, committed records.
A frequently rewritten fixed locator can become the new wear hotspot; a scan
costs recovery code and startup reads. Both require deterministic generation,
integrity and conflict rules, plus a defined response to missing or corrupt data.

Relocation must preserve the old committed journal until the new copy is
verified and discoverable after reset, retain wear history and interrupted-erase
reservations, and prevent old copies from being mistaken for current authority.
Erases of retired journal sectors must themselves remain durably accounted for.
These rules need reset/interruption qualification across the entire transition.

Recommendation: document optional residency now, add a validated component map
first, then evaluate a bounded discoverable journal pool as a separate firmware
revision. Measure expected journal erase savings and the F code budget before
choosing a locator scheme. Current F bytes and tools assume the existing layout;
moving C/D requires coordinated firmware, tool and migration changes, not merely
editing a directory. Existing frozen-F releases retain their present contract.

## Source references

- [Unified system and RAM-tool contracts](UNIFIED_SYSTEM.md)
- [Component build and explicit RAM/flash placements](../tools/build_system.py)
- [Board component profiles and C/D preservation](../profiles.json)
- [Native overlay builder and loader requirements](../../release/str8nf-v0.2.0/tools/build_native_apps.py)
