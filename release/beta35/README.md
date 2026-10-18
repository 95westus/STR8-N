# STR8-N 2.0b35 source and payload review kit

Generation 47, CLOCK 1.10, ASM 0.5. FT245 console; W65C02 and W65C816
emulation profile. ACIA and crypto remain deferred. This local review kit is
not an installable or release-qualified distribution. Migration support,
physical qualification and the final manuals remain open gates.

## Build from source

Install Python 3.9 or later and the Western Design Center WDC02AS / WDCLN
tools separately. Put both WDC executables on PATH, then run:

```powershell
python build.py --out C:\tmp\b35build
```

The output directory must be new and its absolute path at most 70 characters.
The legacy WDC tools can crash on long paths. The builder copies source into
that short directory and assembles 26 modules. It uses only Python's standard
library, this kit's source/manifest and those two WDC tools. No historical
BUILD directory, board image, board receipt, Git checkout, emulator, network
connection or serial port is needed. WDC 3.49.1 was used for qualification;
the build report records exact executable hashes.

Every selected output must match its frozen size and SHA256. A mismatch fails
the build. The build report and maps are owner build evidence; they are not
automatically added to the review archive. The packaged payloads are duplicated
build outputs for comparison, never build inputs.

`source-provenance.json` identifies the promoted final readable assembly and
data files. Long-branch expansion and concatenation performed by the historical
builders are retained as explicit assembly. The historical F30D selector
profile is now explicit source, with its original hash and transformation
recorded. Its freshly linked recovery image exactly matches the frozen beta35
image. Derived worker, vector, BATCH, utility gate and work-stub executable
includes are regenerated from assembly on every build. Text is encoded from
readable JSON; initial journal and migration-table data are generated from
declared defaults. No compiled executable blob is used as a source substitute.

## Inspect and verify

```powershell
python verify.py .
```

Run verification from an extracted kit after packaging; the repository source
directory itself has no payload/manifest until a kit is created. Verification
requires an exact file inventory, hashes, current CLOCK record, seals, address
layout and matching overlapping ASM bytes. It rejects missing or extra files.
`layout.json` describes logical owned ranges, including payload slices. It is
not a flash-write plan. The current CLOCK record is B1:B000-DFFF; inherited
full-bank images and CLOCK 1.9 are deliberately absent.

Full-bank dumps, vendor firmware, private evidence, board data, retained
configuration, historical MAINT images and unrelated v2.1 sources are excluded.
The journal payload has a blank mutable tail; the layout only assigns its
immutable 3072-byte prefix. A preserving installer must retain live records,
configuration, wear counts, fallback slots, user programs and unowned bytes.
The source-built provisioning utility and empty migration template are provided
for qualification only. No board-specific plan, serial launcher or ready-to-run
installation command is included. Do not load or execute them on a board as
part of this review.

The four-board RTC baseline and existing board installations are independent
of this kit. Package preparation does not change clocks, trims or settings.

## Licensing

Project source and payloads carry the included MIT LICENSE. The source inventory
covers the project-owned monitor, utilities, drivers, CLOCK and assembler;
opcode JSON describes instruction encodings. No vendor monitor, WDC executable,
py65, Python runtime or other third-party executable/library is bundled. Obtain
WDC tools separately under their vendor terms. `source-provenance.json` retains
repository-relative origin paths as audit metadata, not required build paths.
