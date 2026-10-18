# bf1 local review kit

This local, unpublished kit targets **2.0bf1 / generation 48 / CLOCK 1.11**,
with **W65C02, FT245/F30D** acceptance scope. Native 816, ACIA and crypto are
deferred. General installation, publication and release permission remain false.

Read the [manuals](docs/bf1/README.md), [scope](release/bf1-prerelease/acceptance-scope.json),
[remaining gates](REMAINING_GATES.md) and [evidence summary](review-evidence-summary.json).
The original candidate README and metadata preserve their earlier development
authorization and architectural profile; the scope above and acceptance policy
define current acceptance. No native 816 qualification is claimed by those
historical source comments or metadata.

Run from an extracted copy, with Python available:

```text
python -B verify_review.py .
python -B release/candidates/batchfix-r1/build.py --out C:\tmp\bf1build
python -B build_helper.py --out C:\tmp\bf1helper
```

Choose fresh, short output paths outside the extraction. Source builds need
separately installed WDC02AS and WDCLN on PATH. The verifier needs only Python
stdlib; no serial, network, Git checkout, vendor firmware or original BUILD tree
is required. Firmware reproduction performs 27 links and must match all 19
artifact hashes in `reference-build.json`. Helper reproduction must match the
separate 585-byte hash in `helper-reference.json`.

The helper source is provided for review and independent reproduction. It is
not a complete installation or recovery launcher. Exact board preimages and
authorized hardware procedures remain necessary for any later device action.
No hardware launcher, complete flash bank, backup, measurement transcript,
emulator/runtime dependency or unrelated v2.1 source belongs in this kit.

The manifest detects corruption relative to its contents; it is not a digital
signature. Check the ZIP SHA-256 against the separately retained review receipt
before trusting an extraction. The review receipt records the fresh extracted
source builds and package refusal tests. Their completion is not a release.

2604's preserving soak and RTC snapshots on 2512/2604 continue independently.
2205/2609 stay off; clocks, trims, settings and the original baseline are preserved.
