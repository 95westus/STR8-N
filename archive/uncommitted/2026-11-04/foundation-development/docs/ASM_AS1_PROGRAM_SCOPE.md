# 2512 AS/1 PROGRAM source persistence: completed scope

November 2, 2026. The owner approved this320-byte trial and it
[passed with exact restoration](ASM_AS1_PROGRAM_ACCEPTANCE.md).
The review and preparation below describe that completed allowance; they
do not authorize another fixture or flash installation.

After yielding to the scheduled RTC collection, a read-only2512 capture
validated the current SS1 directory and found free slot4 at SPI00140-0017F
and a free payload page00800-008FF. The existing CLK, CLOCK and NFCOPY records
remain intact. Original directory, exact320-byte preimages, owner RAM/ZP and
borrowed cache were captured; owner/cache restoration and B3/F/settings/
history readback passed. Final REC>,COM4 free. No persistent write occurred.

The approved fixture saved AS1TRY through the actual resident ASM command,
then starts a new ASM session, loads its66-byte AS/1 capsule and reproduces
the expected8-byte output. It also checks dirty-load cancellation and one
temporary payload CRC fault/refusal/repair. Restore the original directory
slot and entire256-byte payload page exactly; no record remains after cleanup.

Only320 temporary PROGRAM bytes are in scope. Zero flash/journal/F,
WORKSPACE, EEPROM or RTC time/trim/ACK writes; no reset/power cut or other-board
access. Preserve all old records, settings/history and fresh owner RAM/ZP;
restore the borrowed cache and leave BRK/HOLD hooks unchanged. RTC retains
priority. Refuse changed preimages rather than selecting another target.

The bounded737-byte RAM restorer and executable test are built/prepared for
review, with no board access by the build. No F/MON rebuild or CPU simulation
was required. The exact private review and its hash-pinned code/preimages are
in `output/qualification/2512-AS1-PROGRAM-scope-20261102-r1/` relative to the
workspace root. The owner supplied the new write allowance because the
completed RAM-only scope excluded PROGRAM mutations. Execution and cleanup
subsequently passed; the private proposal/approval remain unchanged.

## Launch integration finding

Existing APPS/APP scanning already admits named AP/02 flash images. This can
provide the developer-tool catalogue without changing F. The current R path
reserves CLOCK/FLASH/MAINT/SRAM/WORK/EDU, then searches stored records; R ASM
and R DBG still need a deliberate route to their compatible tool images.
Select and measure the final shared-code/table layout before building that
increment or reviewing occupied flash sectors. No flash targets have been
chosen or approved by this PROGRAM scope.
