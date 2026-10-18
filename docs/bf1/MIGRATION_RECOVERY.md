> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# bf1 migration and bounded recovery

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
