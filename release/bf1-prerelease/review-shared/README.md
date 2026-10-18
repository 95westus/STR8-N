# bf1 shared CPU local review kit

Target: **2.0bf1 generation 48, CLOCK 1.11, FT245/F30D**. One firmware set
runs on 65C02 and 65C816 emulation-mode runtime. Native 816 applications/testing,
ACIA and crypto remain deferred. The owner accepted the unchanged F30D startup
CPU detector briefly entering native mode before returning to emulation.

Read the [manuals](docs/bf1/README.md),
[scope](release/bf1-prerelease/acceptance-scope.json),
[evidence summary](review-evidence-summary.json),
[hardware receipt](evidence/shared-cpu-acceptance.json),
[remaining gates](REMAINING_GATES.md) and [next gate](NEXT_GATE.md).

2609 passed 12 check groups per slot and 14 emulation-runtime observations
across B/A. Checks preserved flash, EEPROM, retained SRAM and application RAM.
The actual final firmware ranges match the earlier 2604 65C02 readbacks and
the pinned payloads. These initial checks are supplemented by original-payload restoration and two
bounded power-cut/recovery cases on 2609, documented in the
[physical evidence index](evidence/physical/index.json). There is no 2609
endurance soak, mid-erase/program loss qualification or 2604 electrical claim. Prior W65C02 model/manual/example
results remain attributed to that model; they are reused with unchanged code.

From a fresh extraction, with Python available:

```text
python -B verify_review.py .
python -B release/candidates/batchfix-r1/build.py --out C:\tmp\bf1build
python -B build_helper.py --out C:\tmp\bf1helper
```

Choose fresh short build paths outside the extraction. Builds require WDC02AS
and WDCLN on PATH. Firmware reproduction must match all 19 artifacts in
`reference-build.json`; helper reproduction must match `helper-reference.json`.
The verifier needs only Python stdlib and opens no board or network connection.
The external package receipt identifies fresh checks and reused build evidence.

Only exact captured 2604/2609 routes are covered. No generic stock, legacy,
core or private-ABI conversion is admitted. This kit contains no hardware
launcher, complete flash bank, EEPROM/SRAM backup or serial transcript. Local
receipts retain those originals; evidence JSONs may reference their local paths.
Check this ZIP's SHA-256 against its separately retained receipt: its internal
manifest is an integrity check, not a digital signature.

2604 keeps its preserving soak. 2512 and 2609 are RTC-only; sampling covers all
three powered boards. 2205 remains off. Clocks, trims and the original
four-board baseline remain unchanged. The physical transactions explicitly
changed monitor selection and conservative wear journals; unrelated configuration
was preserved. General installation, publication and
release permissions remain false. Earlier review ZIPs remain preserved.
