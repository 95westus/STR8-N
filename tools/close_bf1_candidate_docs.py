"""Refresh only superseded distribution claims; retain command/ABI source audits."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/bf1'
def write(name,text):(D/name).write_text(text,encoding='utf-8')
def main():
    write('README.md','''# STR8-N 2.0bf1 candidate manuals

Target: **2.0bf1 generation 48, CLOCK 1.11, ASM 0.5, FT245/F30D**.
One firmware set serves 65C02 and 65C816 emulation runtime. The accepted startup
CPU detector briefly enters native mode; applications run with E=1. Native 816
applications/tests, ACIA and crypto remain deferred.

- [Installed-board quick start: name, time, offset and first programs](QUICK_START.md)
- [Migration overview](QUICK_START_MIGRATION.md)
- [Windows migration commands](QUICK_START_WINDOWS.md)
- [Linux migration commands](QUICK_START_LINUX.md)
- [Migration and recovery](MIGRATION_RECOVERY.md)
- [User guide](USER_GUIDE.md)
- [Operator guide](OPERATOR_GUIDE.md)
- [ASM 0.5 manual](ASM_GUIDE.md)
- [Program and command reference](COMMAND_REFERENCE.md)
- [Technical manual and Mermaid diagrams](TECHNICAL_MANUAL.md)
- [Public ABI reference](ABI_REFERENCE.md)
- [Firmware contents and programmer mapping](FIRMWARE_CONTENTS.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Tested candidate scope

The empty-bank full-system RAM tools were exercised on physical 2609 (original
65C816 WDCMONV2 in B3) and 2604 (published beta4 in B3). B0/B1/B2 were erased
before each migration. Both completed all 22 device-verified transfers, booted
bf1, discovered/executed UCHESS and passed BATCH checks. These are bounded route
proofs, not arbitrary vendor/legacy or occupied-bank upgrade acceptance.

The portable launchers acquire the exact B3 source twice, archive application
RAM, derive a bound plan and use the same tested transport/worker. All four
bank preimages are checked on-device before any erase. Extra host RAM readbacks
can be skipped explicitly; an acknowledged RAM reload is then not host verification.
The live WDC route in this candidate admits the tested SXB6 65C816 source only;
SXB2 recognition/planning remains available offline. Both CPUs use the same target.

## Limits and release status

These are local candidate tools/manuals. Publication and full release acceptance
remain held. Longer soak/RTC gates are not waived by owner-stopped workloads.
Linux extracted scripts are tested on Linux; a Linux physical serial migration
has not been performed. An earlier WDC trial lost RTC continuity; the corrected
empty-bank trial retained a running valid RTC, but the earlier cause and broad
RTC-preservation qualification remain open. No migration tool issues clock,
trim or offset setters. Keep clocks and power evidence under observation.

Early factory-WDC interruptions without a valid bf1 fallback/journal may need an
external programmer and the original private backup. No WDC or intermediate
beta4 image is distributed. Retain the exact kit and all private recovery files.
''')
    write('QUICK_START_MIGRATION.md','''# Windows and Linux full-system migration quick start

Use the [Windows commands](QUICK_START_WINDOWS.md) or [Linux commands](QUICK_START_LINUX.md).
Both packages carry identical bf1 firmware, including UCHESS, CLOCK, ASM,
utilities/providers, MON A/MON B, recovery/core and S/R/T.

## Source and storage admission

The live WDC route admits the exact original SXB6 65C816 WDCMONV2 profile;
the beta4 route admits the exact published generation-13 profile. **B0/B1/B2
must already be erased.** The public migration does not erase occupied user
banks or stage legacy source firmware. Do not erase a working board merely to
make a refused upgrade pass. Back up and obtain a separate provisioning plan.
The SXB2 65C02 WDC profile is recognized for offline preparation, not admitted
for live use by this candidate's hardware qualification.

1. Extract the entire matching host package and run `bf1 verify` through its
   `.cmd` or `.sh` wrapper. Install Python 3.10+ and pyserial 3.5.
2. Close other terminal/debugger sessions. Select the actual port, exact USB
   serial number and a private board label. Unrelated ports are never opened.
3. Choose a new private output directory outside the extracted kit. The tool
   captures B3 twice and application RAM once. B0/B1/B2 are explicitly recorded
   as erased assumptions, not fabricated readbacks; the RAM worker checks every
   byte of all four source banks before any flash mutation.
4. Use stable power and retain the RTC battery. WDC requires an initial RESET
   while its debugger is armed. Type `INSTALL BF1` only after source admission.
5. After all device verification passes, follow the physical RESET prompt once.
   The tool confirms bf1/U CHESS discovery and reloads saved application RAM.
   With `--no-host-readback`, loader acknowledgment does not prove host readback.

The tool never SETs time/trim/offset, acknowledges power events, or programs
EEPROM/external retained SRAM. A prior WDC trial lost RTC continuity, so broad
RTC preservation remains unqualified; see [scope and limits](README.md).

## Failure and recovery

Keep the exact kit, capture, plan, transfers and logs together. Never substitute
another board's metadata or wear counts. Use [bounded recovery](MIGRATION_RECOVERY.md).
An unexplained partially programmed state refuses. Early WDC cuts without a
working bf1 fallback may require an external programmer. Do not repeatedly reset
or force a different installer. Original vendor backups stay private.

## Programmer image

The 96 KiB STR8-N-only `.bin` includes every supported application and UCHESS.
It covers B1/B2/B3; file offset zero is full-device offset `$8000`. It is a
fresh-provisioning image with defaults, not a preserving upgrade or board dump.
See [firmware mapping](FIRMWARE_CONTENTS.md). No WDC/beta4 binaries are included.
'''.replace('U CHESS','UCHESS'))
    write('MIGRATION_RECOVERY.md','''# bf1 migration and bounded recovery

The platform quick starts document the live empty-bank routes. `--capture`
also supports file-only planning without opening a serial port. Keep the exact
original kit: plans are bound to its manifest and are not interchangeable with
a revised package. Integrity hashes do not authenticate an untrusted download.

## Capture and admission

`bf1 capture --port ... --usb-serial ... --board ... --out ...` captures a
working STR8-N monitor: all four flash banks independently twice and application
RAM once. It writes only private host files. A schema-1 capture records actual
repeated bank data, sizes and SHA-256 hashes. All files are checked on intake.

The live empty-bank migration uses schema 2: only B3 is independently repeated;
B0/B1/B2 are explicitly *assumed erased*. It archives RAM before borrowing it,
does not restore into the WDC debugger's live stack, and requires complete
on-device source-preimage checks before the first flash mutation. Unknown
profiles, changed input files and occupied assumed-empty banks refuse.

Board labels contain 1–64 ASCII letters/digits, period, underscore or hyphen,
starting with a letter/digit. They are operator labels. Live commands additionally
require an explicit matching port/USB serial number. Keep backups outside the kit;
captures, serial logs and vendor bytes must never be uploaded with a release.

## Planning and preservation

`beta4-to-bf1 --capture ... --out ...` recognizes the published generation-13
MAINT/MON A/MON B/E/F component hashes and valid configuration/wear journal.
`wdcmonv2-to-bf1 --capture ... --out ... --accept-unknown-wear-history` derives
the direct factory conversion. Offline recognition covers the exact SXB2/SXB6
profiles; the enabled live WDC hardware scope is SXB6. Source images are not
distributed. No intermediate beta4 image is required by WDC conversion.

Unknown historical wear starts a new tracked baseline only after explicit
acknowledgment; zero does **not** mean zero lifetime erases. Optional `--history`
and `--metadata-escrow` are board-specific private inputs, never borrowed from
another board. No private laboratory escrow is required for factory conversion.
Public live routes require empty B0/B1/B2; general occupied-bank upgrades remain
outside this candidate's live qualification. UCHESS is included in each full target.

`bf1 verify-plan --plan ...` re-derives the source CPU, target, transaction,
installer/template and every transfer from the original capture and exact kit.
Changed inputs refuse before port access. Do not manually execute a file named
`installer-model-only.s19`; the launcher performs the required admission first.

## Forward recovery

1. Keep the original plan/output directory unchanged.
2. If a STR8-N fallback monitor works, use `bf1 capture` to make a fresh private
   current-state capture from the same board/USB identity.
3. Run `bf1-recovery forward --plan ORIGINAL/plan --capture CURRENT --out NEW`
   to prepare and inspect the admitted recovery. Add the explicit port, USB
   serial and board options to execute; type `RECOVER BF1` when prompted.
4. Follow the verified installer RESET prompt and retain its device/RAM receipts.

Only replayable complete, erased or precommit boundaries are admitted. Exact
completed targets produce a no-write receipt from the supplied capture, with
no port opened; this is not a fresh live observation. Factory-WDC forward
recovery additionally requires a valid bf1 fallback and tracked wear journal.
An earlier WDC interruption may need a programmer and the original private
source backup. Unknown partial programming refuses guessed recovery.

## Beta4 restoration

`bf1-recovery restore-beta4 --plan ORIGINAL/plan --capture CURRENT --out NEW`
requires the fully completed bf1 target of that beta4-origin plan. It restores
the captured original payload while retaining newer conservative erase counts.
It does not reset wear history or provide vendor restoration. A WDC-origin
plan cannot be used with `restore-beta4`. App-complete forward cuts and beta4
restoration are executed in the CPU/flash model; broader physical power-cut
coverage remains outside this candidate's claims.

## Verification limits

The common RAM worker and transfer engine completed both physical empty-bank
routes. Linux wrappers are tested on Linux without physical serial hardware.
Extra RAM readbacks are on by default; `--no-host-readback` retains source
acquisition, protocol acknowledgments and full on-device flash checks. Saved
RAM reload then has loader acknowledgment only. No tool issues clock/trim or
offset setters. Earlier RTC continuity failure evidence remains open; see the
[candidate scope](README.md). Native 816 applications, ACIA and crypto are deferred.
''')
    for name in ('QUICK_START_WINDOWS.md','QUICK_START_LINUX.md'):
        p=D/name;text=p.read_text();text=text.replace('one exact admitted WDCMONV2 or','the exact SXB6 65C816 WDCMONV2 or');write(name,text)
    p=D/'QUICK_START.md';text=p.read_text().replace('This guide is under distribution review; publication remains held.','This local candidate guide does not waive release qualification; publication remains held.')
    text=text.replace('the same pinned firmware bytes and include recovery. The direct factory-WDC\nlauncher and complete portable transport/recovery qualification are still\npending. There is no approved public live command to substitute here yet.','the same pinned firmware bytes and include bounded recovery. The current live\nsource/empty-bank scope and known limits are documented in the platform guides.')
    write(p.name,text)
    for name in ('USER_GUIDE.md','ASM_GUIDE.md','COMMAND_REFERENCE.md','TECHNICAL_MANUAL.md','OPERATOR_GUIDE.md'):
        p=D/name;text=p.read_text().replace(' — draft for bf1',' — bf1 candidate').replace(' — draft',' — candidate').replace(' — distribution review',' — candidate')
        text=text.replace('This prerelease draft passed','This candidate guide passed').replace('This draft','This guide').replace('this draft','this guide').replace('A small draft program','A small example program')
        if name=='TECHNICAL_MANUAL.md':
            start=text.index('## Complete application-image audit')
            text=text[:start]+'''## Complete application image and migration scope

The 96 KiB STR8-N-only app image contains CLOCK/ASM, providers/utilities,
MON A/MON B and recovery/core. S/R/T is assembled at B3:`$E800` inside E.
UCHESS has a 1,439-byte executable plus a 24-byte stored-program header at
B1:`$8000`; `T 1` discovers it and `R 1 UCHESS` runs it. Full source and original
license/credits accompany the image. Empty-bank RAM migrations install the same
applications; physical WDC/65C816 and beta4/65C02 checks passed. Unused image
padding is not permission to overwrite user storage. Public live routes require
erased B0/B1/B2 and refuse unknown sources; see the migration guides.
'''
        write(name,text)
    p=D/'FIRMWARE_CONTENTS.md';text=p.read_text().replace('The new candidate passed actual','The application image passed actual')
    text=text.replace('No board was flashed for these\nchecks. Preserving upgrade placement/conflict handling, extracted Windows/Linux\npackages and complete migration/recovery qualification remain open.','The full-system RAM migrations also installed providers and UCHESS on physical\n2609 from original WDC and 2604 from beta4 with empty B0/B1/B2. Both completed\n22 transfers, bf1 boot and UCHESS/BATCH checks. General occupied-bank upgrades,\nLinux physical serial migration and broad RTC preservation remain outside the\ncurrent candidate qualification.')
    write(p.name,text)
    print('PASS updated 14-document candidate set; retained ABI/command tables and scope limits')
if __name__=='__main__':main()
