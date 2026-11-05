# STR8-N worked examples

These optional examples run above frozen Foundation 0.3.0 / BASE1 / PR05.
They do not install automatically or assign owner storage on a board.

- [Microchess](microchess/README.md): real DEV ASM source parts, embedded
  Peter Jennings and port copyright notices, RAM/S19 save/restore and an
  AP/02 UCHESS image for B1:$8000.
- [OSI BASIC](osi-basic/README.md): a source-built OSI configuration of
  Microsoft 6502 BASIC with public Foundation console calls; an opaque B0
  image using only sectors $8000/$9000, entry $8000.

In a combined kit, generated images are in `examples/payload/`, source is in
these subdirectories, and `examples/tools/example_images.py` joins ASM S19
exports or makes a RAM-copy AP/02 sector offline. The repository entry point
for that helper is `tools/example_images.py`. EXAMPLES-MANIFEST.json inventories
the exact source, binaries, notices and model results carried in the kit.

See [formats](../docs/FILE_FORMATS.md), [DEV guide](../docs/DEVELOPER_MANUAL.md)
and [qualification scope](../docs/QUALIFICATION_SCOPE.md). The model tests use
the actual DEV assembler and example instructions with modeled public RAM
ABI endpoints. They are not a physical-board installation trial or a claim
that arbitrary edits remain compatible.
