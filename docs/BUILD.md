# STR8-N build and Foundation freeze policy

Use the [current source build/verification recipe](CONSOLIDATION_SOURCE_REVIEW.md)
for the F / MON / UTIL / DEV kit. [Build helpers](BUILD_HELPERS.md) identifies
current entry points and historical scripts. The [component guide](COMPONENT_GUIDE.md)
links source/releases; [file formats](FILE_FORMATS.md) distinguishes PC files,
RAM executables, S-records and installed sectors.

```powershell
python -B tools/verify_base1.py
python -B tools/verify_component_inputs.py
python -B tools/build_named_components.py --out build/components
```

Use a new output directory. WDC02AS/WDCLN are needed for non-F assembly.
The current recipe reconstructs all 32 non-F inputs and emits 34 payloads;
F is reused unchanged. COMPONENTS.json records component identity, size and
SHA-256. NATIVE-COMPONENTS.json records sector/CPU targets. Neither file
installs anything or assigns owner space on a board.

## Frozen Foundation

`tools/verify_base1.py` checks files only. It does not assemble, emulate,
open a port or flash. F_FREEZE.json pins F 0.3.0 g00000001 / BASE1 / PR05,
its 4096-byte image and protected source. Current documentation, host tools,
MON, UTIL and DEV work keeps those bytes and the ABI unchanged.

A selected RAM-helper development build can use, for example:

```powershell
python -B tools/build_base1.py --only map --out build/new-map
```

Selections are config, opaque, demo, map and readback. Unselected helpers and
F are reused with hashes checked. This produces helper-development outputs,
not a complete current named kit. Never invoke initial-F mode or bypass the
freeze lock for an ordinary component/documentation change.

A concrete Foundation defect or contract requirement would need a separately
reviewed successor generation, a compatibility decision and relevant physical
boot/recovery/update qualification. Preserve the 0.3.0 tag, image and lock.
There is no scheduled unfreeze.

## Check and package

Run the checks in the [source recipe](CONSOLIDATION_SOURCE_REVIEW.md), then
package those verified outputs with `tools/package_named_components.py`.
Packaging reads existing payloads and receipts; it does not rebuild F, connect
to a board or publish a release. The current named kit remains a development
candidate; [qualification limits](QUALIFICATION_SCOPE.md) stay explicit.

The preserved Foundation 0.3.0 ZIP uses its own original build/packaging files,
filenames and receipts. Its release commands are not a replacement for the
current named-kit recipe. Keep generated BUILD/output files, private captures
and board profiles out of source commits.
