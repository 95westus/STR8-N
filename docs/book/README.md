# Current-code book

The editorial source is [STR8N_CURRENT_CODE_BOOK.md](STR8N_CURRENT_CODE_BOOK.md).
The generated complete book adds the source catalog, symbol index, numbered
listings, coverage inventory, and vector diagrams of code structure and flow.
It also includes a byte-verified, annotated disassembly of the embedded Bank
Maintenance mutation worker and workflows for all current mutation engines.

- [PDF](../../output/pdf/STR8N-1.35-Current-Code-Book.pdf)
- [Offline HTML](../../output/book/STR8N-1.35-Current-Code-Book.html)
- [Coverage manifest](../../output/book/coverage-manifest.json)
- [Document validation](../../output/book/validation.json)

Generate from the repository root:

```powershell
python tools/build_current_code_book.py
```

The generator requires `reportlab`, `markdown`, and `py65`. `pypdfium2` enables PDF
text checks and rendered review samples. Dependencies may be installed into
`output/book-deps`, which the generator adds to its module search path:

```powershell
python -m pip install --target output/book-deps reportlab markdown pypdfium2 py65==1.2.0
```

The build reads current files, never git history, and never invokes the
firmware toolchain or connects to a board. It checks the selected production
flags before generating. Updating code requires reviewing the editorial
chapters and per-file descriptions as well as regenerating listings.

Source hashes identify complete original files. Listings omit dated assembly
change-log comment lines and inactive assembly branch bodies, with explicit
line-gap markers and machine-readable omission reasons. Shared RAM tool
listings show the union of their current supported profiles. Original source
files are not modified. Generated binary carriers and current test-fixture
payloads are inventoried without duplicating their encoded content.

`output/book-deps` holds disposable third-party dependencies. `tmp/pdfs`
holds disposable document-review images. The deliverables are PDF and searchable
HTML, with JSON validation/coverage records under `output/book` and `output/pdf`.
Markdown is retained only as internal editorial input, not as a generated book.
`code_diagrams.py` defines the shared vector atlas used by both output formats.
`worker_reference.py` extracts the current private worker DB block, disassembles
it as W65C02 at its RAM execution address, checks every instruction round trip,
and compares the complete blob with all three current maintenance S19 images.
It also searches existing `BUILD/v*/local/test-deps` for the pinned py65 package.
Original firmware files and embedded bytes remain unchanged.
