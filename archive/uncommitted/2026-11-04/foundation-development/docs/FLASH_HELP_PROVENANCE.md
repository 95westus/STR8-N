# FLASH DELAY help closeout

November1,2026. The full `board-tool.asm` help source now identifies DELAY as
a stored legacy byte0A-FF, with Foundation's chooser fixed3s. Earlier closeout
text incorrectly assumed the full help paragraph was present in the installed
compact FLASH image and therefore proposed an unnecessary help-only install.

The current B2 image, pinned by2512's authoritative physical-image marker,
contains `BOOT B/C/OFF/RUN/DELAY; B/C/W/?` and no `hex-ticks` or `(0.1s)`
claim. The dense FLASH builder replaces the entire full-source help region
with this compact menu. Reversing only the source correction reproduced the
exact original source hash from the accepted build. Replacing the help region
by the actual builder rule then made the corrected and original staged
sources byte-identical. The archived linked source contains the same compact
menu. The operator manual already states the fixed3s/legacy-byte distinction.

**No help-only rebuild, installation or erase is needed.** No board port was
opened, no CPU simulation ran, and F/downloads were untouched. This is artifact
provenance, not a new physical board test. The compact menu remains terse;
additional in-tool explanations can be considered in a future functional build.

Receipt relative to the workspace root:
`output/qualification/2512-FLASH-help-provenance-20261101-r1/report.json`.
