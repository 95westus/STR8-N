# Worked examples above frozen F

[Examples overview](../examples/README.md) links the complete walkthroughs for:

- **Microchess:** Peter Jennings's credited engine, with `(c)` notices in the
  RAM BIN and AP/02 payload. Four real DEV ASM source parts fit the current
  source buffer. Capture their S19 exports on the PC, join/compare the result,
  restore it through MON S19, or wrap the compiled RAM BIN as UCHESS AP/02 at
  B1:$8000. AS/1 SAVE/LOAD SRAM can preserve the source parts separately.
- **OSI BASIC:** a pinned source reconstruction with a public-Foundation
  console adapter. The 8192-byte opaque image occupies B0:$8000–$9FFF, entry
  $8000. Its two sector files leave the current B0:A–D DEV allocation intact.
  LIST/plain-text save and paste restore preserve BASIC source on the PC;
  the historical LOAD/SAVE device hooks are not implemented.

Read each example's copyright/license files and memory/CPU/return contract.
F stays byte-identical at 0.3.0 / BASE1 / PR05. Builds and model tests open no
serial port; neither extraction nor an AP/02 wrapper grants target ownership.
The examples are optional development candidates pending physical acceptance.

## Build and export into a combined kit

Build the named components first using [the source recipe](CONSOLIDATION_SOURCE_REVIEW.md).
With external WDC and cc65 tools installed:

```powershell
python -B tools/build_examples.py --out build/examples --cc65 C:/Tools/cc65
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c02
python -B tools/test_examples.py --build build/examples --kit build/components --cpu 65c816-e
python -B tools/build_examples.py --export-tested build/examples --out build/examples-kit
```

The exported directory is the reviewed `examples/` subtree for a combined kit.
Copy it into the named kit's `examples/` directory, replacing only the matching
example files, then run `package_named_components.py` after the ordinary
component/MEMORY/host checks. EXAMPLES-MANIFEST.json verifies the exact inventory,
licenses, source, payloads and both example CPU reports. Maps, compiler binaries,
private captures and staging files are excluded. Packaging refuses changed
payloads or extra files.

Model checks exercise actual DEV ASM PASTE/ASM/S19, byte agreement with the
readable WDC source, Microchess play/return and AP/02 entry, and BASIC boot,
arithmetic, FOR/NEXT, strings, LIST, Ctrl-C and ESC. Console/return endpoints
are modeled public RAM ABI calls. They do not replace a physical MON scan,
sector installation or serial-adapter trial. See [qualification scope](QUALIFICATION_SCOPE.md).
