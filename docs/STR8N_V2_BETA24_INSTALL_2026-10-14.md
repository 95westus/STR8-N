> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# Beta24 installation on 2604 and 2609

Both boards were flashed to beta24 generation 33 with MAINT 2.0 on
October 14, 2026, at the owner's request. Each RAM installer reported
`MIGRATION VERIFIED; PRESS PHYSICAL RESET`. Physical RESET and subsequent
boot/readback qualification were subsequently confirmed on both boards. See
[beta24 qualification](STR8N_V2_BETA24_QUALIFICATION_2026-10-14.md) for test
coverage, results and the remaining physical power-retention checkpoint.

USB identities were checked: 2604 / A10MQGVHA / COM5 and
2609 / A10MPQXCA / COM8. The prior preserving soak had completed and released
its ports. Access used the shared serial lease.

Each board's complete 131072-byte flash was read twice and compared exactly.
Its backup-bound nine-sector update was rehearsed with the linked RAM
installer, checking exact final banks, sector order, MAINT's final commit,
stale-preimage refusal and corrupt-payload refusal. Candidate NAME,
compact-boot, timezone and storage-transfer reports passed and matched the
candidate artifact hashes. All four current banks were compared with the
backup again immediately before installation; the RAM installer was read
back before execution. Device transfer and migration verification passed.

Sector order: B3:C, B1:A, B1:9, B1:8, B2:D, B2:C, B2:E, B3:B, B3:A.
The update preserves B0, saved records outside MAINT, CLOCK, fixed E/F
recovery, RTC/SPI provider, journal code and the complete identity/timezone/
name tail. Configuration selection is retained, with pinned generation
advanced when applicable; wear counters account for the nine erases.
No board name was assigned and no clock, trim, offset or EDU setting was
changed. No SRAM formatting or EEPROM administration was performed.

Owner-local backups, payloads, exact expected bank images, model receipts
and serial transcripts are under
`output/qualification/beta24-install-2026-10-14/{2604,2609}` and are excluded
from Git. Deployment tooling is `tools/update_v2_beta24.py`.
