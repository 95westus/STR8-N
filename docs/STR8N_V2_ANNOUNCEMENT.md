# STR8-N v2 RC1: A guarded monitor for WDC W65C02SXB

STR8-N v2 is a 4 KB resident monitor for WDC W65C02SXB boards. It gives the operator
console access, RAM and S19 loading, bank selection, guarded flash editing, and
boot handoff. It grew from the v1.3x line with a simpler role: you decide what
each bank holds and when to run an image. Applications such as HIMON, ASM-F2,
and AP live in a separate guest layer.

The first release candidate is **STR8-N 2.0a21 RC1**. On W65C02SXB board 2512,
its Bank 3 top sector was installed and read back byte for byte. Reset, cold
USB reconnect, and configured guest handoff were exercised on that board. RC1
is scoped to board management through an enumerated USB FT245 host with stable
power. The earlier alpha19 functional board checks support this candidate;
they were not all repeated on alpha21.

The v2 branch includes a getting-started guide and a printable, fillable
qualification record for incoming W65C816SXB boards, with or without the
matching EDU board. Those board combinations have not yet been physically
qualified. The stock WDCMONv2 migration path has host checks and also awaits a
factory-board run. The ACIA fallback console remains under investigation.
There is no interruption-recovery claim for an active flash or configuration
change; an interrupted change can require external reflashing.

The prepared RC1 package contains STR8-N BIN/S19 images, project-authored
RAM installation and update tools, two public R-YORS ASM-F2 `.a` carriers, and
the guides. It contains no WDCMONv2 firmware or source, stock-bank dump, or
R-YORS guest firmware. The RC1 archive has not yet been attached to a GitHub
release; this announcement covers the v2 branch and its RC1 qualification
status.

- [Start with the v2 README](https://github.com/95westus/STR8-N/tree/v2#str8-n-v2)
- [Read the RC1 scope and evidence](https://github.com/95westus/STR8-N/blob/v2/docs/STR8N_V2_RC1_2026-09-24.md)
- [Read the W65C816SXB/EDU getting-started guide](https://github.com/95westus/STR8-N/blob/v2/docs/STR8N_V2_RC1_GETTING_STARTED_816.md)
- [Review the RC1 package contents](https://github.com/95westus/STR8-N/blob/v2/docs/STR8N_V2_RC1_PACKAGE_README.md)

Comments and questions are welcome in the
[announcement discussion](https://github.com/95westus/STR8-N/discussions/2).
Please use
[GitHub Issues](https://github.com/95westus/STR8-N/issues) for reproducible
defects or a specific qualification result. Include the board type, firmware
banner, host and cable, steps, and observed output; avoid posting private
stock-bank images or copyrighted WDCMONv2 code.
