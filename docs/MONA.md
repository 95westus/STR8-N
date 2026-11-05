# STR8-N MON — optional monitors above Foundation

The optional monitor family is **STR8-N MON**, with A/B identifying slots.
Earlier planning/source used Mona; existing source identifiers are preserved.
Current source and the preserved MON preview are linked from the
[component guide](COMPONENT_GUIDE.md). Foundation 0.3.0 itself needs no monitor.

F remains the frozen 4096-byte boot/recovery platform, BASE1 / PR05. MON owns
its own version/generation, board/service display and interactive commands.
`REC> A` or `REC> B` launches the matching installed monitor; a `B3>` prompt
then identifies the selected data bank. CONFIG `C B` saves MON B as default.
An opaque bank entry has a different launch contract.

MON A/B require matching headers, CRC and PR05 compatibility. Ordinary opaque
images boot through configured bank entries; arbitrary bytes do not become a
monitor by occupying slot A/B. Historical g0034 or b15 full-system monitors
retain their own ABI/provider requirements.

Use the [MON/UTIL manual](NATIVE_UTILITIES_MANUAL.md), [file formats](FILE_FORMATS.md)
and current manifests for commands, RAM packets and installed sector images.
Optional hardware/services must be admitted separately. Proposed features in
older plans do not extend F's frozen ABI. The current named MON/UTIL/DEV kit
remains a development candidate with [scoped qualification](QUALIFICATION_SCOPE.md).
