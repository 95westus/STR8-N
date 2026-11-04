# BASE1 build and freeze policy

`python tools/verify_base1.py` checks existing files only. It does not assemble,
emulate, open a port or flash a device. Historical CPU reports are not current
BASE1 qualification.

The identity build compiled F once and built affected CONFIG, OPAQUE, DEMO,
MAP and READBACK against it. Worker/vector images were unchanged; NFM1/NFA1
were reused. No reproduction build or CPU model ran.

F_FREEZE.json now locks F. For a later source change requiring RAM assembly:

```text
python tools/build_base1.py --only map --out build/new-map
```

Selections: config, opaque, demo, map, readback. Use a fresh output directory.
Unselected payloads and frozen F are reused with hashes checked. Inspect the
output manifest before promoting changed RAM files. WDC tools are required
only for actual assembly; no installation or publication is automatic.

Old F/full-system builder paths are retired or redirect to the canonical RAM
builder. Initial-F mode is already consumed. A future boot defect needs a new,
reviewed F generation and reference proof, not an override of this lock.

The release kit also carries Serial Console 0.1.0, its pinned pyserial
requirement and [operator guide](SERIAL_CONSOLE.md). Host-only console changes
need no assembly. For a changed console, run `python -m unittest tests.test_console`
and `python tests/console_tk_smoke.py` (Tk display required, fake worker). Record those checks
separately from firmware qualification; do not rerun unrelated CPU suites.
Package the existing files once with
`python tools/package_base1.py --out dist/fresh-candidate-directory`.
This checks frozen inputs and copies files without rebuilding firmware.
The kit includes the scoped 2512 BASE1, native-console, WDC, programmer-F,
opaque and C/D recovery receipts. Packaging
refuses a receipt whose tested console hashes no longer match; raw captures and
backups are never included. Inspect the ZIP's console/dependency/guide, evidence
and MANIFEST hashes. The reviewed 2512 cases passed. Before public release,
complete the [pending migration test from the extracted ZIP](RELEASE_WORKFLOW.md).
Other platforms/layouts retain their separate qualification limits. No automatic
flashing, publication or 2205 access is part of packaging.
