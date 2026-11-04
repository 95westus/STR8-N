# Source, integrity and packaging

The source tree is independent of the parent STR8-N project and private captures.
Python 3.11+ is enough to check or package the existing payloads:

```text
python tools/verify_system.py
python tools/make_release.py --out dist/release
```

These are file/source/manifest checks and ZIP creation, not firmware builds or
CPU simulations. The operator kit has a standalone `python verify_package.py`.
The source package retains all optional modules; see the
[unified source guide](UNIFIED_SYSTEM.md).

## Rebuild only when required

A firmware source change requires WDC wdc02as and wdcln on PATH. Those proprietary
tools are not redistributed. Use a fresh output directory:

```text
python tools/build_system.py --out build/changed-source
```

This builds all 18 payloads. `tools/build.py` is the shared four-component
F/CONFIG/OPAQUE/DEMO builder used by the system build. Neither builder requires
parent-tree inputs. Baselines deliberately refuse changed firmware bytes until
that change is explicitly versioned and its affected evidence updated.

Do not make a routine second build or run CPU models for documentation/packaging.
Existing results are retained in validation/. For a concrete defect requiring
execution checks, the CPU suites can be selected explicitly; CI does not run
those suites on ordinary pushes. Reproduction is an explicit investigation or
release requirement when firmware bytes change, not an automatic extra step.

The 0.2.0 release reuses already built payloads and earlier source reproduction.
F and unchanged optional components keep their earlier hashes. CONFIG has a
same-length generic banner; MAINT/EDU-client generic text and CRC changes are
recorded in their baselines. No new assembly build or simulation is claimed.
