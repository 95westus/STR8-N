# Candidate3 live and physical-key acceptance on2512

November2,2026, America/Chicago. The extracted g10 candidate3 passed on2512,
Windows/FT245/65C02. This closes the physical Shift-key and live extracted-kit
checks for this exact candidate. It does not qualify a fresh migration/install.

Archive:`STR8N-MON-g00000010-candidate3.zip` from
`BUILD/unified-g10-candidate3-20261101-r3/`.
SHA-256:`6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789`.
The archive, extracted payloads and published downloads were not changed.
Its embedded pending flags/docs record packaging time; this later receipt
supplements them without repacking or modifying the candidate.

| Check | Result |
| --- | --- |
|19 utility targets | Every extracted component matched the live board; no replacement needed |
| Shift+F2 | Physical key and native file picker selected the exact extracted S19 example |
| Initial S19 cancellation | Physical F12 sent exactly Ctrl-C before payload and returned to MON |
| Shift+F3 | Physical key sent one accepted S19 transfer; no autorun; independent D verified RAM3500-3503=`KEYS` |
| SEND BIN cancellation | Physical F12 sent exactly Ctrl-C before payload and returned to REC |
| Normal BIN | Physical F2/file picker and F4 loaded the extracted DEMO; arithmetic, CPU02, key echo and software return to recovery passed |
| Connect/disconnect | Production buttons worked; this is not a current-version physical F10 claim |
| Owner preservation | Fresh RAM0200-66FF and ZP00-DF restored and read back exactly |

The complete GUI TX stream matched the exact610 expected bytes: the permitted
RAM-loader commands, two Ctrl-C bytes, the exact S19/DEMO payloads, readback
and DEMO return keys. It contained no flash/settings command. No generated
test keys were used. Shift+F2 was recorded twice before completed selection;
only the verified selected file was sent. The console correctly does not
claim independent board readback; the qualification harness performed it.

Two earlier harness attempts ended before F10 and restored owner RAM/ZP.
The successful third harness allowed ordinary buttons, observed physical
keys regardless of app-widget focus, and added copy-path controls. These
were host-test changes; the extracted console0.1.2 remained unchanged.

The full B3 bank matched its preimage exactly, including frozen F, MON A/B,
settings, metadata and boot/wear journal. There were zero flash erases,
journal/settings/RTC/trim/ACK/SPI writes, physical resets or power cuts.
DEMO used its documented public software boot return once; that was not a
physical RESET. seq1177/20 rows and C/D/E/F57/38/37/24 remain unchanged.
Other boards were not accessed. No firmware build or CPU simulation ran.

Final REC>, COM4 released, restore/worker guards clear. RTC host eligibility
passed without another board connection or collector/baseline change.

Receipts relative to the workspace root:

- `output/qualification/2512-candidate3-physical-keys-20261102-r3/report.json`
- `output/qualification/2512-candidate3-physical-keys-20261102-r3/completion.json`

The later [2609 full-profile upgrade and targeted816 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md) also passed; it has its own preservation receipts.
No new WDC migration, factory flash, source-only rebuild, publication or
all-board rollout is claimed. ASM/DBG remain follow-on work.
