# Build entry points and historical helpers

Use tools/build_named_components.py for the current F/MON/UTIL/DEV kit. Build
instructions and test commands are in CONSOLIDATION_SOURCE_REVIEW.md. It verifies
the input lock, rebuilds all 32 non-F binary inputs, then names and packages the
34 qualified payloads. F is reused as a frozen binary; never assemble it here.

Current reconstruction modules are rebuild_component_inputs.py (RAM helpers and
CLOCK), rebuild_mon_services.py (MON and shared services), and
rebuild_util_dev_inputs.py with rebuild_utilities.py, rebuild_storage.py and
rebuild_devtools.py (UTIL/DEV). Their generated assembly, maps and staging belong
under the chosen output directory. package_named_components.py makes the kit.
test_product_names.py and test_memory_tool.py exercise the current payloads.

Older build_*.py, port_*.py and adapter/codec helpers remain for source provenance
and shared algorithms. Some individual historical command-line entry points
refer to old staging layouts or BUILD paths. Their presence does not make them
supported standalone current-kit builders. Current recipes call selected source
preparation, assembly, codec and loader functions explicitly, supplying generated
paths. Do not run all historical scripts to produce a release.

The published historical firmware/payload helper BINs remain for static freeze
checks and provenance. They are not product-build inputs: the guarded extraction
check rejects reads of those helper BINs. Reference source under monitors/reference
is algorithm source, not a saved board image. Licensed CPU emulators under
tests/vendor are used only by offline tests. Keep both vendor license files.

The export intentionally omits board-specific acceptance evidence. That omission
does not rewrite existing releases or repository history. Local source selection
and notice review do not authorize publication or prove ownership independently.


The old package_unified_candidate.py entry point is omitted from this edition:
it packaged owner-private qualification receipts and is not read by the current
guarded product build. Its original source remains in the prior review archive.
Use package_named_components.py for the current kit.
