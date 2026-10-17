# bf1 draft manuals

Current acceptance policy and tonight's prerelease scope: [accepted gates](../STR8N_BF1_ACCEPTANCE_AND_PRERELEASE.md).

Target: **2.0bf1 generation 48, CLOCK 1.11, ASM 0.5, FT245/F30D**.
These separate candidate drafts derive from the reviewed beta35 guides; beta35
manuals and sealed payloads remain unchanged. The bf1 source and candidate
receipts govern its changed BATCH behavior and two-slot route.

- [User guide](USER_GUIDE.md)
- [ASM guide](ASM_GUIDE.md)
- [Program and command reference](COMMAND_REFERENCE.md)
- [Technical manual](TECHNICAL_MANUAL.md)
- [Candidate qualification](../STR8N_V2_BATCHFIX_R1.md)
- [2604 installation and recovery](../STR8N_BF1_2604_INSTALL_RECOVERY.md)
- [2609 installation and emulation checks](../STR8N_BF1_2609_INSTALL_RECOVERY.md)

One pinned firmware set targets 65C02 and 65C816 emulation-mode runtime.
2604 supplies 65C02 hardware evidence; 2609 supplies both-slot 65C816 E=1
hardware evidence. The unchanged startup CPU detector briefly enters native
mode before restoring emulation, as explicitly accepted by the owner.
Native 816 applications/testing, ACIA and crypto remain deferred. Bounded 2609 restoration/power-cut results are recorded; broader electrical
coverage and final candidate acceptance remain open. These drafts do not authorize installation or release.

2604 retains its preserving bf1 soak. 2512 remains powered on for RTC-only
measurements; 2609 now has an owner-authorized six-hour preserving soak, then returns to RTC-only collection. Snapshots
cover all three powered boards against the immutable baseline. 2205 remains off. Clocks and trims remain unchanged; persistent monitor/wear changes belong only to the documented installation/recovery transactions. Examples run
offline; do not compete for campaign RAM or serial ports.


Complete programmer image, bank layout and MON A/MON B naming: [full firmware image](../STR8N_BF1_FULL_FIRMWARE_IMAGE.md).
