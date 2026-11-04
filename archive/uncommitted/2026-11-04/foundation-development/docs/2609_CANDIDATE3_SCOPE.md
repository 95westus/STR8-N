# 2609 Candidate3 scope: completed

The owner approved the reviewed16-erase upgrade/tests. Installation, targeted
816 runtime, one physical saved-B reset, full owner-RAM restoration and RTC
readmission passed on November2. All16 erases and17 appends are consumed;
no retry allowance remains. F and published/Candidate3 archives are unchanged.
See [final acceptance and limits](CANDIDATE3_2609_LIVE_ACCEPTANCE.md).

The proposal below records the pre-approval state; its pending wording is
historical. The sealed private proposal, approval and receipts are retained.

## Original proposal


November2,2026.2609's earlier RTC/loader hold has been cleared. The
owner-reset recovery receipt verifies its saved owner RAM/ZP restoration;
the subsequent62-second RTC/LED qualification passed with current trim0E
and control80. No new reset, recovery command or port access was performed
by this preparation. The older hold statements describe the earlier incident.

The exact2512-qualified Candidate3 components are ready for2609. This is a
system-component upgrade, not a copy of2512's board data. Keep2609's name,
offset, battery/EDU metadata, boot policy, RTC calibration/history, SPI data
and fresh owner RAM. B0 and B1:E/F remain outside the image replacement scope.

The new review requires15 utility-sector erases plus one native B3:C journal
rotation:16 total,17 journal appends. Archive26 old records; replace16 old C
rows on chip and retain10 old D rows. Final seq1089/27 rows, C/D/E/F80/49/49/31.
Saved default B remains B, rebound from MON gD to g10. Four identical targets,
including CLOCK and all B3:9 code/metadata, are skipped. B3:F stays golden;
B2:F is a utility sector and is one of the reviewed replacements.

The private review contains every exact target/preimage, predicted journal,
preservation rules, targeted816 checks and2609-only RTC-reader candidates:
`output/qualification/2609-candidate3-scope-20261102-r1/review-document.md`.
**Review ready, not approved or installed.** Fresh live preimages must match
before writing. The old unused four-erase transfer scope is not combined with
this new scope. One physical RESET for saved-B startup is included; no power
cut, positive flash/SPI fixture, F write or RTC setting write is included.

RTC collection retains priority. New2609 g10 native TIME/LED readers must be
qualified and registered before collection resumes on that changed profile;
old instruments, baselines and other-board routing remain intact.2512,
2205/2604 and published/Candidate3 archives are untouched by this preparation.
