> Historical release-work checkpoint. Current v2.0rc1 firmware is installed

> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.

> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.

> Operating instructions below describe their recorded historical stage.



# Issue: beta35 A-slot extension cannot hand BATCH input to native utilities



ID: STR8N-007 (qualification finding QA35-004)



Status: **Open in frozen beta35; fixed and hardware-checked in bf1/rc1**



Opened: 2026-10-17



Resume condition: none for offline investigation; physical testing waits for

the protected RTC campaign to end.



## Impact



The separately assembled beta35 generation-47 A-slot experiment cannot yet

support a full-feature inactive-slot upgrade from active B. The sealed beta35

review kit contains the B-slot target only and remains unchanged. This finding

does not establish a failure of the B-slot firmware running on 2512.



## Reproduction and evidence



`tools/build_beta35_monitor_slots.py` assembles the sealed readable sources in

a new directory. Its B image must match the frozen payload byte for byte.

The A experiment changes only the image page and linker origin. Owner-local

build evidence is `tmp/a35-0521/build-report.json`.



In the serial-disabled W65C02 model, select A35 with retained B34 and run:



```

BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q

```



Expected: the four utilities run and return, followed by `BATCH done`.

Observed: MAINT opens and waits at `BM> ` with the queued commands unconsumed.

The original failed assertion and output are retained in

`output/qualification/beta35-prerelease-2026-10-17/a-slot-model-0521/failure.json`.

Follow-up model transcripts and results use the separate `a-slot-model-0530`

directory. No hardware port is opened by either test.



## Findings



The frozen `release/beta35/source/xip/utilities.asm` routines `B29_LINE_1`

through `B29_LINE_4` require `BOOT_ACTIVE` at $7D30 to equal $B0 before entering

the batch gate. An active A monitor therefore uses each utility's normal

interactive reader. Error/cancel hooks and application checks have similar

page checks. CLOCK's `B29_CLOCK_VALID` also requires $B0. Standalone CLOCK

STATUS/STATS/TRIM/OFFSET queries worked in the follow-up A model; this does not

qualify CLOCK's BATCH integration under A.



Monitor-only `BATCH APPS;VERSION` completes under A, and BATCH correctly refuses

ASM. The native-utility handoff is the reproduced failure. The independent

full B-slot control completed MAINT/SRAM/WORK/EDU and `BATCH done`, with unchanged

persistent state. All 12 follow-up diagnostic scenarios passed, including

corrupt/uncommitted/ABI fallback and fixed-F return to A/B. This diagnostic

pass includes reproducing the known A failure; A35 remains unqualified.



## Next action



Keep A35 unqualified. The B-slot control and boot/fallback diagnostics are saved.

The target-owned migration planner must explicitly refuse routes requiring a

qualified beta35 A target. Continue qualifying supported B-target routes and

the remaining offline documentation work. A slot-independent BATCH change

would require separately identified payloads and fresh qualification; do not

edit the sealed candidate or disguise modified utilities as its payloads.



## Close criteria



Either explicitly scope the release to qualified B-target routes and document

the A limitation, or qualify a separately identified corrected payload set.

For a correction, test both active slots with native/CLOCK BATCH success,

error/cancel handling, mixed versions, recovery, and full persistent-state

preservation. Physical acceptance remains a separate gate.



## Resolution



Open; no firmware change or installation performed.



### Separate candidate implementation



The owner subsequently authorized an offline-only separate candidate for this

defect. `release/candidates/batchfix-r1` identifies experimental display 2.0bf1,

generation 48 and CLOCK 1.11. Beta35 remains sealed and B-target scoped.



The candidate introduces a versioned checked provider/capability handshake,

slot-neutral native/CLOCK predicates and exact CLOCK launch admission. It

preserves legacy guards and private entry addresses. Initial evidence passes

25 scenario checks (18 explicit completed-case reuses, seven fresh continuation

cases) and 26 linked admission checks, with independent 27-link builds producing

19 identical artifacts. Prior implementation/harness failures are retained.



This is an initial model fix in a separate candidate, not a beta35 repair or

hardware acceptance. The issue remains open for candidate regression/review

and physical qualification. See `docs/STR8N_V2_BATCHFIX_R1.md` and owner-local

`output/qualification/batchfix-r1-current.json`. No live board was accessed and

no firmware installed by the candidate work.





## Owner-approved B-target scope



The owner selected bounded proven B-target maintenance routes for beta35 and

deferred broader upgrades to a separately identified candidate. This resolves

the route-scope decision; it does not qualify hardware or permit installation.

FT245/F30D, exact target E/F, registered source/profile, protected destinations,

verified full backups/current preimages, validated A fallback and all journal/

sequence/count refusals remain required. The archived path retains B28 A while

replacing B34 B, not the previously active B34 as an inactive-slot-only upgrade.



Stock/legacy/core/private-ABI converters and A35-dependent routes are outside

beta35 scope. STR8N-007 remains an excluded A35 defect, deferred for a separate

candidate; it is not fixed by this decision. Native and CLOCK BATCH hooks need

validated slot-independent capability checks, with signature/version/fallback

guards and success/error/cancel paths qualified together. The frozen B-target

payloads stay unchanged; no A35 repair is introduced into beta35.



The scoped acceptance plan is `docs/STR8N_V2_BETA35_SCOPED_ACCEPTANCE.md` and

the machine-readable policy is `release/beta35-prerelease/beta35-route-scope.json`.

The reservation-enabled composed installer remains model-only, pending physical

acceptance; the old template is not promoted. Physical/native/electrical gates

and long-term observations remain open, with no release/installation permission.

The 2512 soak/drift campaign continues; the other boards remain off and all

real clocks/trims/settings unchanged. ACIA and crypto remain deferred.

