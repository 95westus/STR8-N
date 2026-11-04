# Extended b14 RAM CONFIG: opaque default boot

For the complete current reference, use the
[consolidated b14 boot, recovery and configuration guide](../../docs/STR8N_B14_BOOT_AND_RECOVERY_GUIDE.md).
It includes boot-sector operation, record format, recovery, the examples and
hardware results below, related tools, and implemented-versus-planned status.
This narrower document is retained as the original CONFIG-specific record.

The same extended CONFIG BIN was subsequently loaded, executed and independently
read back during the preserving b15 installation on 2512. Its shared service
entries remain unchanged. See the consolidated guide's b15 hardware result.

The standalone extended CONFIG enables a bank, sets its entry address, and
saves an opaque-image boot default using the existing SNBT C/D journal. It
loads through b14 F `L` at `$0200` and starts after three seconds without
incoming data. F, MON A/B, the opaque installer, and the record format are
unchanged. This is a separate RAM-tool build; the historical b14 builds and
their original CONFIG artifacts remain intact.

At `REC>`, enter `L`, wait for `SEND BIN`, and send
[ram-config-offline.bin](../../BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin)
in binary mode. The 2,602-byte app occupies `$0200-$0C29`; that RAM is disposable
and must be saved separately if it contains owner data. Its prompt is
`RAM CONFIG ? B C I W Q> `. Commands are text followed by Enter; lowercase,
CR, LF and CRLF are accepted.

| Command | Meaning |
|---|---|
| `?` | Complete help |
| `B` or `C` | Show saved default, bank enable states and entry addresses |
| `B bank entry` | Enable bank `0-3` and save its four-digit hex entry, preserving the current default |
| `C target` | Save default `S`, `A`, `B`, or an enabled bank `0-3` |
| `I` | Initialize only when both journal sectors are entirely blank |
| `W` | Show erase counts and unknown-history status |
| `Q` | Software restart through F and the normal countdown |

For an opaque image already installed in B0 at `$8000`:

```text
B 0 8000
C 0
B
Q
```

`B 0 8000` persists the enable bit and entry together in one snapshot; `C 0`
then saves the default. `Q` restarts and boots that bank at countdown expiry.
`S` during the countdown still selects recovery. No MON image is needed for
CONFIG or the opaque handoff. B/C change settings only: install the actual
opaque image separately with the existing installer/recovery kit.

Entries use the existing F contract: `$8000-$E000` in `$1000` steps. B3 cannot
enter `$C000/$D000` (the journal). Its `$A000/$B000` entries remain legal boot
record values but belong to MON slots; ordinary opaque installation still
protects them. B0/B1/B2 are the normal opaque-image locations. Arbitrary byte
addresses and `$F000` require a different F/record contract and are refused.

The RAM-only writer dispatch adds a bank-edit operation to the frozen guarded
writer. It admits the full snapshot CRC and duplicate history before editing,
preserves other boot fields/settings/wear/history/extensions, and retains the
existing rollover, durable erase reservation, readback and final commit rules.
An identical B request makes no flash write. Malformed input, disabled-bank
defaults, damaged/ambiguous journals and exhausted reservations refuse.

Build and offline verification:

```text
python prototypes/boot-record-v2/build_ram_config_b14.py --out BUILD/pr04-b14-ram-config-r1
python prototypes/boot-record-v2/test_ram_config_b14.py --build BUILD/pr04-b14-ram-config-r1 --cpu 65c02
python prototypes/boot-record-v2/test_ram_config_b14.py --build BUILD/pr04-b14-ram-config-r1 --cpu 65c816-e
python prototypes/boot-record-v2/build_ram_config_b14.py --out BUILD/pr04-b14-ram-config-repro
python prototypes/boot-record-v2/qualify_ram_config_b14.py --build BUILD/pr04-b14-ram-config-r1 --repro BUILD/pr04-b14-ram-config-repro
```

Offline qualification: **20 groups passed, zero failures** across 65C02 and
65C816 emulation, FT245 and ACIA. All 26 admitted bank/entry combinations
persisted and booted with MON A/B absent. Every one of 1,860 observed mutation
prefixes in bank/default append and rollover retained an old or new valid
boot tuple; 24 selected interrupted states were reloaded through raw L and
retried (with safe reservation refusal permitted). Owner ZP, application RAM
outside the loaded app, staging RAM, unrelated flash, settings and history
were checked. A second build reproduced the BIN byte-for-byte.

Evidence: [qualification](../../BUILD/pr04-b14-ram-config-r1/ram-config-qualification.json),
[build report](../../BUILD/pr04-b14-ram-config-r1/ram-config-build.json),
[help text](../../BUILD/pr04-b14-ram-config-r1/ram-config-help.txt).
These are CPU/NOR model results; physical power cuts and console electrical
behavior were not tested. Those offline checks loaded or changed no board.

The builder defaults to frozen `BUILD/pr04-b14-raw-r4` services and refuses an
existing output directory. Sources are `ram-config-b14.asm` and
`build_ram_config_b14.py`; the current generic prototype builder still emits
its historical minimal CONFIG. This app is specific to b14; do not use it with
RC1 g0034 or WDCMONv2. Raw L retains its existing unverified-transfer behavior.
No serial port or physical board is accessed by the offline commands above.

## 2512 hardware test and restoration (October 26)

The owner-authorized live trial passed on 2512 (USB `A10MQFLCA`, 65C02).
Fresh repeated full-flash and owner-RAM/ZP captures preceded the test. All
four banks were originally enabled, with entry `$8000` and default MON B.
A separately modeled, capture-bound RAM helper temporarily disabled only B0
so the new CONFIG could exercise an actual OFF-to-ON enable transition.

The qualified 2,602-byte CONFIG loaded through F raw L. `B 0 A000` enabled B0
and saved its new entry; `C 0` saved the default. A software reset through F
was intercepted with S, and two independent full-flash reads matched both CPU
models' saved postimage. No opaque image was executed or installed.

`B 0 8000` and `C B` restored the original settings. Two further complete
flash reads matched both CPU models' restored postimage. All F/MON/opaque
image sectors, legacy configuration, unknown-history flags and extensions
were preserved. The journal advanced from sequence 930 to 936, retaining the
new history and one additional B3:C erase attempt. Original settings were
restored through normal appends, without replaying an old journal.

The complete freshly captured owner RAM `$0200-$64FF` was restored and
compared twice through the RAM service and again independently through MON.
Owner ZP `$00-$DF` was preserved and reread through both paths. The final full
countdown boot selected the restored default MON B, with BOTH consoles. All
pending restoration/worker flags are clear and the shared serial lease is
released. No RTC writes, physical reset or physical power-cut test occurred.

The exact-source rehearsal passed on both CPUs; 15 buffered host checks
passed. Initial port/synchronization stops occurred before settings writes;
their receipts and the corrected prompt-framing check are retained.

Evidence: [audited results](../../output/qualification/ram-config-2512-20261026-r3/audited-results.json),
[hardware report](../../output/qualification/ram-config-2512-20261026-r3/test-results.json),
[saved settings](../../output/qualification/ram-config-2512-20261026-r3/CONFIG-saved.txt),
[restored settings](../../output/qualification/ram-config-2512-20261026-r3/CONFIG-restored.txt).
Live helper: `board_ram_config_2512.py`; exact-source rehearsal:
`test_ram_config_2512_live.py`; final audit: `audit_ram_config_2512.py`.

## Menu interface assessment (October 26)

A menu would make sense for the next RAM CONFIG revision. Keep the present
command-based BIN as the qualified hardware-test artifact. A proposed menu is:

```text
RAM CONFIG
Saved default: B

1  View saved settings
2  Edit a bank (enable/disable and entry)
3  Choose default boot
S  Review and save pending changes
U  Discard pending changes
Q  Exit
```

Edits should remain in a RAM draft until Save. Show the saved and proposed
bank/default/entry values before the single journal transaction, and reject
disabling the selected default unless the same draft chooses another valid
target. Retain the existing F entry limits and full journal admission. Combine
bank edits and default selection in one snapshot, skip identical saves, and
make Quit with unsaved changes explicitly choose Save/Discard/Cancel.

Also provide a read-only erase-count/history page. Blank-journal initialization
should remain a separate, clearly labeled maintenance action. A recovery-menu
return should be the ordinary exit; restarting into the saved image should be
a separate selection. These are interface recommendations, not implemented
commands or a new board-loaded build.
