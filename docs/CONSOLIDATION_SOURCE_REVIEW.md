# Build and verification

Main is the Foundation-based STR8-N F / MON / UTIL / DEV source tree. Source
recipes reconstruct all 32 non-F binary inputs and check their accepted hashes.
The intentionally frozen 4096-byte F platform input is reused unchanged.

See [component/source/releases](COMPONENT_GUIDE.md), the
[documentation index](README.md) and [file/transfer formats](FILE_FORMATS.md)
for Foundation, on-board commands and PC tools. Current builds and preserved
release downloads have separate manifests and qualification scopes.

## Build

With Python and the external WDC02AS/WDCLN tools installed, from the repository
root (no other STR8-N clone, private BUILD folder or board capture is required):

```powershell
python -B tools/verify_base1.py
python -B tools/verify_component_inputs.py
python -B tools/build_named_components.py --out build/components
```

The output directory must be new. The five input capsule pins are F, the
original accepted manifest, native catalog and terminal Python sources. The
terminal uses an explicitly recorded sanitized source override; the original
accepted manifest and every firmware expectation remain unchanged. All text
uses the tracked LF policy, including the pinned host source, so Git checkouts
and source archives use the same verified bytes.

## Offline checks and packaging

```powershell
python -B tools/test_product_names.py --build build/components --cpu 65c02 --deps tests/vendor --report build/components/tests-65c02.json
python -B tools/test_product_names.py --build build/components --cpu 65c816-e --deps tests/vendor --deps-816 tests/vendor --report build/components/tests-65c816-e.json
python -B tools/test_memory_tool.py --build build/components/memory-agent-build --cpu 65c02 --deps tests/vendor --report build/components/tests-memory-65c02.json
python -B tools/test_memory_tool.py --build build/components/memory-agent-build --cpu 65c816-e --deps tests/vendor --deps-816 tests/vendor --report build/components/tests-memory-65c816-e.json
python -B tests/test_console.py
python -B tests/test_board_profiles.py
python -B tests/console_tk_smoke.py
python -B tools/package_named_components.py --build build/components --out str8n-components.zip
```

Named kits include `requirements-console.txt` and the placeholder MEMORY
profile at `firmware/memory-agent/profile.example.json`. Real profiles and
captures remain private. Packaging accepts `--label` for a candidate's ZIP
root directory; component versions and frozen F do not change with that label.
If supplied by release preparation, `RELEASE-CANDIDATE.json` and `HOST-TESTS.json`
are included alongside the component/CPU-test manifests.

The CPU suites have 13 naming and 21 MEMORY cases on each CPU. Host unit tests
and hidden fake-worker Tk checks open no serial ports. The vendored py65 and
py65816 copies retain their separate BSD licenses. WDC executables are external
requirements and are not redistributed.

SOURCE-RECONSTRUCTION.json records all 32 exact input comparisons. The MON/
services and UTIL/DEV receipts record detailed source builds. Generated assembly,
maps and staging live under the output directory and are not source inputs.
Assembler/linker `.s19` intermediates are address-bearing text, not alternate
raw BINs; inspect the declared target and record types before any transfer.
Only source reconstruction satisfies the five helper dependencies; the older
published helper BINs remain for static platform checks and historical provenance.

The earlier Git archive build matched all 34 qualified firmware payloads, passed
68 CPU-model executions, 29 host unit tests and hidden Tk. See
QUALIFICATION_SCOPE.md for limits: repository consolidation is not new hardware
acceptance. F sources, bytes and ABI stay frozen.

BUILD_HELPERS.md identifies current entry points and historical scripts.
BOARD_PROFILES.md describes opt-in local labels; no board inventory is embedded.
MEMORY_ACCEPTANCE_SUMMARY.md records earlier supported-region trial scope without
raw captures. Keep local profiles, generated builds and qualification captures
out of commits; /build, /BUILD and /output are ignored.
