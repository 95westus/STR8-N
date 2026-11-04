"""Reconcile current docs with sealed2609 Candidate3 receipts; no repack/push."""
from pathlib import Path
import install_2609_candidate3 as ins
import rtc_drift_campaign as c
t=ins.t;DOC=t.REPO/'docs'

def replace(path,old,new):
 text=path.read_text(encoding='utf-8');assert text.count(old)==1,(path,old[:70]);path.write_text(text.replace(old,new),encoding='utf-8')

def run():
 done=c.read(ins.Q/'2609-candidate3-closeout-20261102-r1/completion.json');assert done['passed'] and done['RTC_readmitted']
 (DOC/'CANDIDATE3_2609_LIVE_ACCEPTANCE.md').write_text('''# Candidate3 installed acceptance on 2609

November 2, 2026. The approved 2609/COM8 upgrade and targeted 65C816-emulation
checks passed using the exact extracted Candidate3 components already accepted
on 2512/65C02. Both now run the same optional MON/tools profile above frozen
Foundation. Board data and CPU identity remain specific to each board.

Candidate: `STR8N-MON-g00000010-candidate3.zip`, SHA-256
`6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789`.
The archive and published downloads are unchanged. These later receipts
supplement its packaging-time pending flags; no firmware was rebuilt.

| Check | Result |
| --- | --- |
| Installation | 15 image erases plus one native B3:C rotation; all 17 appends verified |
| Common profile | MON A/B g10, WB2 gE, SRAM/WORK g4, PROGRAM g3, current native tools |
| Exact components | All changed targets independently read back; four identical targets skipped, including CLOCK and B3:9 |
| Runtime | 816 emulation, VERSION/TIME, APPS, CLOCK STATUS/HISTORY, BANK MAINT and SRAM/WORK routes passed |
| BATCH | Installed SRAM/WORK Q returns executed the following monitor Dump |
| Loaders | Extracted-console S19 cancellation/load with independent KEYS readback; SEND BIN Ctrl-C and normal RAM BIN/public-HOLD passed |
| RAM execution | G marker/public-HOLD return passed |
| Physical startup | One physical RESET selected saved B g10 automatically; Traditional output, board2609, EDU ON and both SRAM capacities without PREP |
| RTC | Nine native TIME/NIST readings and the unchanged 794-byte/62-second LED sampler passed; current trim0E (-14), control80 retained |
| Owner RAM | Full0200-66FF and ZP00-DF restored and read back after the runtime, reset and RTC checks |

Saved B remains B, rebound from gD to g10; bank enables remain00 and entries
8000. Final journal is seq1089 with27 valid rows; C/D/E/F tracked counts are
80/49/49/31. All26 old rows are archived on the host. The approved rotation
replaced16 old C rows on chip and retained10 old D rows. Tracked attempts
are not a lifetime wear measurement.

B0, B1:E/F, B3:9 provider/metadata, board name/offset/battery/EDU settings,
RTC time/trim/power-fail history, EEPROM and SPI PROGRAM/WORKSPACE are
preserved. Zero F writes, power cuts or RTC setting/trim/ACK writes occurred.
No other board was accessed by this trial. RTC baselines, historical points,
old instruments and other-board routing remain retained.

Two host-side interruptions are recorded rather than hidden. After the first
verified A replacement, an inspector attempted a protected C/D read through
the wrong interface. Owner RAM was restored; canonical READBACK independently
verified A and its append before continuation, without another A erase.
The first LED sampler completed acquisition but compared the entire PIA CRA:
B4 changed to34 while the six control bits and LED value matched. Owner RAM
was restored immediately. The corrected versioned 2609 host reader compares
CRA0-5 and records IRQ flags6/7 separately; a repeated unchanged sampler
passed. Original failure receipts and readers are retained. Reading port A
clears these flags according to the [WDC W65C21 datasheet, p15](https://www.wdc65xx.com/wdc/documentation/w65c21.pdf).
This is not an RTC power-fail ACK or a firmware change.

Private receipts, relative to the workspace root:

- `output/qualification/2609-candidate3-installed-20261102-r2/report.json`
- `output/qualification/2609-candidate3-runtime-20261102-r1/report.json`
- `output/qualification/2609-candidate3-reset-20261102-r1/report.json`
- `output/qualification/2609-candidate3-RTC-readmission-20261102-r2/report.json`
- `output/qualification/2609-candidate3-closeout-20261102-r1/completion.json`

Final REC>, COM8 released, owner/worker/reset guards clear and RTC readmitted.
The16-erase allowance is exhausted. This closes the latest-profile 816 upgrade
gate; it does not repeat every 2512 positive-write fixture on2609. No fresh
WDC migration, live factory restoration, 816 native-mode execution, source-only
rebuild, publication or reference-board rollout is claimed. ASM/DBG follow.
''',encoding='utf-8')
 replace(t.REPO/'README.md','**Current development checkpoint: MON A/B g00000010 on 2512.**','**Current development checkpoint: MON A/B g00000010 on 2512 and 2609.**')
 replace(t.REPO/'README.md',"The latest full profile is qualified on2512/65C02;2609 retains its earlier\ncheckpoint. Its November2 recovery is complete, and the\n[Candidate3 upgrade review](docs/2609_CANDIDATE3_SCOPE.md) is prepared but not\napproved/installed. Older816 evidence does not qualify every latest byte.","The same Candidate3 components are now installed on2512/65C02 and2609/65C816\nemulation. The [2609 upgrade and targeted runtime/startup acceptance](docs/CANDIDATE3_2609_LIVE_ACCEPTANCE.md)\npassed with board settings preserved and RTC collection readmitted. Positive\nwrite fixtures remain documented separately from these targeted CPU checks.")
 replace(t.REPO/'README.md','2512; targeted latest-profile816 coverage remains separate.','2512; targeted latest-profile816 upgrade/runtime/startup coverage now also passes on2609.')
 replace(DOC/'NATIVE_UTILITIES_MANUAL.md','**Current2512 development checkpoint:**','**Current2512/2609 development profile:**')
 replace(DOC/'NATIVE_UTILITIES_MANUAL.md',"2609's separate RTC loader incident was recovered on November2; owner RAM/ZP\nrestoration and RTC/LED readmission passed. It has not received the latest2512\ntransfer/storage increments. Its [Candidate3 upgrade scope](2609_CANDIDATE3_SCOPE.md)\nis prepared but not approved/installed. Do not describe the boards as byte-identical.","2609 now has the same Candidate3 system components after its reviewed16-erase\nupgrade. Targeted816 runtime/storage/BATCH/loader, physical saved-B startup and\nRTC readmission passed; see [2609 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md).\nBoard metadata, owner data and calibration remain distinct. The2512-specific\npositive-write receipts above are not relabeled as2609 write tests.")
 replace(DOC/'UNIFIED_CANDIDATE3_PACKAGE.md',"The latest full profile remains qualified on2512/65C02.2609's November2\nrecovery is complete; its [upgrade scope](2609_CANDIDATE3_SCOPE.md) is now\nprepared but not approved/installed. Older816 receipts are not relabeled as\nqualification of this entire kit.","The same system components are now installed on2609/65C816 emulation. Its\n[reviewed upgrade and targeted live acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md)\npassed, including saved-B physical startup and RTC readmission. The26 old\njournal rows were archived and all counts/settings carried forward; F stayed\ngolden. The latest profile now has2512 and targeted2609 evidence, with no\nclaim that every2512 positive-write fixture was repeated on2609.")
 replace(DOC/'CANDIDATE3_2512_LIVE_ACCEPTANCE.md','Latest full-profile816 acceptance remains separate while2609 is owner-held.','The later [2609 full-profile upgrade and targeted816 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md) also passed; it has its own preservation receipts.')
 scope=DOC/'2609_CANDIDATE3_SCOPE.md'
 text=scope.read_text(encoding='utf-8');scope.write_text('''# 2609 Candidate3 scope: completed

The owner approved the reviewed16-erase upgrade/tests. Installation, targeted
816 runtime, one physical saved-B reset, full owner-RAM restoration and RTC
readmission passed on November2. All16 erases and17 appends are consumed;
no retry allowance remains. F and published/Candidate3 archives are unchanged.
See [final acceptance and limits](CANDIDATE3_2609_LIVE_ACCEPTANCE.md).

The proposal below records the pre-approval state; its pending wording is
historical. The sealed private proposal, approval and receipts are retained.

## Original proposal

'''+text.split('\n',1)[1],encoding='utf-8')
 inv=DOC/'2609_CURRENT_INVENTORY.md';text=inv.read_text(encoding='utf-8')
 inv.write_text('''# 2609 current recorded inventory

November2,2026. W65C816SXB,65C816 emulation/FT245,COM8. The latest
[Candidate3 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md) supersedes the
October31 checkpoint retained below.

| Region | Current content |
| --- | --- |
| B0 | Preserved WDC/SXB6 image; outside this upgrade |
| B1:8-D | Candidate3 BANK MAINT and SRAM/WORK/transfer tools |
| B1:E/F | Retained owner/legacy contents |
| B2:8-A | WB2 gE, PROGRAM g3 and shared STATUS components |
| B2:B-D | Unchanged CLOCK1.10 |
| B2:E/F | Current FLASH/CONFIG/transfer components |
| B3:8/9 | Current RTC/loader; B3:9 code and1024-byte metadata unchanged |
| B3:A/B | Identical-command MON A/B g00000010, BASE1/PR05 |
| B3:C/D | seq1089,27 valid rows; counts C/D/E/F80/49/49/31 |
| B3:E | Candidate3 shared dispatcher/services |
| B3:F | Frozen Foundation0.3.0 g1, BASE1/PR05,4096 bytes |

Saved default B/g10; bank boots disabled, entries8000. Board name2609 and
local display offset-05:00 retained. RTC trim0E (-14), control80 retained;
native TIME and the unchanged62-second LED sampler readmitted. Original
owner RAM0200-66FF and ZP00-DF are restored/read back. Final REC>,COM8 free.
All26 pre-upgrade journal records are archived;10 old D rows remain on chip.
No F write, power cut, SPI/RTC settings write or other-board access occurred.

Current physical bank SHA-256 values:

- B0: `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`
- B1: `de63292f6e867f2d1e15bb861eb4004111e45acdb2842d336fda03a472275795`
- B2: `d221efe027d6407904375ac98ed26a5824342c48d7f5c330784319c6c0151f13`
- B3: `868638f6c9d6192728005ea89393c4bc51e9f284c21eec3edd13138d0c60688c`

The exact prepared targets and independent live readbacks are retained with
the approval/closeout receipts. Their settings and owner data are not part of
the distribution. No automatic flash action remains.

## Historical October31 inventory

The following inventory and hashes describe that older checkpoint.

'''+text.split('\n',1)[1],encoding='utf-8')
 path=DOC/'UNIFIED_ENVIRONMENT_REMAINING.md';text=path.read_text(encoding='utf-8');path.write_text('''# Unified environment: current release checkpoints

November2 update: Candidate3 is installed on2512/65C02 and2609/65C816
emulation. The [2609 reviewed upgrade/runtime/startup/RTC acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md)
passed. The latest-profile rollout to2609 is closed; old hold/pending text
below is checkpoint history, not a current port prohibition. F stays golden.

The selected Traditional presentation,2512 BOOT/CLOCK positives and software
fault cases, physical Shift-key/extracted-kit acceptance and targeted latest
816 runtime are closed within their recorded limits. A new WDC migration or
live factory restoration from this kit has not been qualified. Decide whether
those are supported claims before publication; source-only reproducibility
and the final release/version/tag/download review are still separate work.
ASM/DBG and816 native-mode execution remain deferred. No new fixtures, flash
allowance, publication or2205/2604 rollout is authorized by this closeout.

RTC/NIST retains priority; both current boards are readmitted. Board settings,
calibration and owner contents remain board-specific despite the common profile.

## Earlier checkpoints and their original limits

'''+text.split('\n',1)[1],encoding='utf-8')
 finish_shipping()

def finish_shipping():
 assert c.read(ins.Q/'2609-candidate3-closeout-20261102-r1/completion.json')['passed']
 shipping=DOC/'UNIFIED_SHIPPING_RELEASE.md';text=shipping.read_text(encoding='utf-8');needle='Owner direction, October 30, 2026. **One release and one feature contract.**'
 assert needle in text;text=text.replace(needle,needle+'''
November2 closeout: the same Candidate3 profile is now installed on2512 and
2609, with targeted816 runtime, physical saved-B startup and RTC readmission
accepted. See [2609 acceptance](CANDIDATE3_2609_LIVE_ACCEPTANCE.md). Older held/
2512-only statements below describe earlier checkpoints; positive write
fixtures retain their original board/scope. Published files remain unchanged.
''',1)
 text=text.replace('on2512; the latest utility profile has not been rolled out to the held2609.','on2512; the same latest utility profile is now installed and runtime-tested on2609.')
 text=text.replace('The held2609 has not received these latest bytes','The same latest bytes are installed on2609; its targeted runtime acceptance is separate from2512 positive writes')
 text=text.replace('the newest utility bytes are qualified on2512 only','the newest common utility bytes have2512 acceptance plus targeted2609 runtime/startup acceptance')
 text=text.replace('latest816 and new migration/factory paths are separate','targeted latest816 acceptance also passes; new migration/factory paths are separate')
 shipping.write_text(text,encoding='utf-8')
 print('Updated current Candidate3 acceptance, README, manual, inventory and gate docs; archives unchanged')

if __name__=='__main__':
 import sys
 if '--finish-shipping' in sys.argv:finish_shipping()
 else:run()
