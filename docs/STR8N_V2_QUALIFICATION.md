# STR8-N v2-alpha19 qualification freeze

Candidate frozen on 2026-09-24: `2.0a19`, branch `v2`, source commit
`994ffc9` (full commit and SHA-256 identities in
[the freeze manifest](STR8N_V2_ALPHA19_FREEZE.json)). This is a qualification
candidate, not a completed release qualification.

The later [alpha20 freeze](STR8N_V2_ALPHA20_FREEZE.md) has a different
firmware identity. The hardware results below remain alpha19 results until
alpha20 is installed and tested separately.

## Current release scope decision

The [2.0 RC1 decision](STR8N_V2_RC1_2026-09-24.md) accepts the frozen alpha21
image for a scoped W65C02SXB/FT245 release candidate. This matrix preserves
the earlier alpha19 evidence and does not relabel it as alpha21 board testing.

For a W65C02SXB release claim, require a USB FT245 data host connected and
enumerated at startup and stable 5 V board power during operation. The
[alpha21 board session](STR8N_V2_ALPHA21_2512_INSTALL_2026-09-24.md)
demonstrated the cold USB reconnect banner and configured Bank 1 handoff on
board 2512. Users must keep the USB cable connected and avoid RESET, NMI, and
power interruption during transfers and flash mutation. Power-loss recovery
and automatic rollback are outside this operating claim; interruption can
leave a partial image. Normal power-off after a completed monitor or ASM/HIMON
session is allowed. Deliberate FT245/VIA cable, host, power, and active-flash
fault injection are excluded from this release gate. No interruption-recovery
claim is made: an interrupted write or configuration change can leave an
incomplete image or an unbootable board, and external reflashing may be needed.
V2 has no persistent transaction record or automatic rollback, and the
interrupted states have not been qualified. Previously tested rejection and
cancellation paths retain only their recorded scope.

V2 is the board management layer. Application displays, LED patterns, and
sounds belong to separately installed 8-xxx guests and are outside this
release claim.

ACIA receive and automatic fallback are outside the FT245-only console claim
and remain deferred under [STR8N-001](issues/ACIA_RX_2512_2205.md). This
scope decision does not qualify ACIA or close its issue. W65C816 and EDU LED
claims require their separate hardware evidence before they can be advertised.

Freeze the firmware, public ABI, memory map, command behavior, and build inputs
at these identities. Documentation and qualification evidence may be added.
A firmware fix requires a new candidate identity, fresh host checks, and a
review of affected hardware tests; do not silently replace the frozen images.
The three pre-existing documentation edits describing validation limits are
included in the local snapshot and recorded separately from committed source.

## Evidence retention

The owner-local snapshot is `output/qualification/v2-alpha19-2026-09-24/`.
It retains the pre-check build and board evidence in `before/`, the checked
artifacts in `candidate/`, source in `source/`, and `host-check.log`.
This ignored directory must be retained separately from disposable `BUILD/`.
The tracked manifest records file hashes so subsequent runs can establish
whether they tested the same candidate. Local board captures are not a public
firmware distribution.

Existing alpha19 evidence accepts guarded top update/readback, backup/readback,
vector autostart, physical-reset hold cancellation, and disabled autostart on
board 2205. See [the board report](STR8N_V2_ALPHA19_VECTOR_BOARD_TEST_2026-09-24.md).
Earlier alpha reports are supporting history, not complete alpha19 acceptance.

The [2512 qualification session](STR8N_V2_ALPHA19_2512_BOARD_TEST_2026-09-24.md)
adds exact installation/readback, FTDI, RAM ABI, BRK/IRQ/NMI, F/I, and autostart
evidence. Direct ACIA TX passed, but RX did not; the matrix remains incomplete.
ACIA receive and fallback-console qualification are deferred.

The [frozen artifact identity and image checks](STR8N_V2_ALPHA19_ARTIFACT_IDENTITY_2026-09-24.md)
passed for all 103 candidate files, the dense E-F and full-bank S19 files, and
the Bank 1 board 2512 install/readback.

An earlier [preflight of the board marked 2512](STR8N_V2_ATTACHED_BOARD_B0_READBACK_2026-09-24.md)
found Bank 0 matched the retained WDCMONv2 image. Bank 1 then held a rebuild
outside the frozen alpha19 identity, so tests of that installation did not
qualify the frozen candidate.

The later [four-bank layout session](STR8N_V2_2512_BANK_LAYOUT_2026-09-24.md)
installed the frozen alpha19 image in Bank 3, with exact full-bank readback and
startup observed. Bank 1 now holds v1.35 with HIMON and ASM-F2, and Bank 2 is
erased. This establishes a new live candidate location; the remaining behavior
gates are still open.

The [no-EDU reset and cold-power session](STR8N_V2_2512_NO_EDU_RESET_2026-09-24.md)
confirmed Bank 3 alpha19 startup, active Bank 1 vector autostart, timed `S`
cancellation, FT245 selection, CPU identity, and ROM signature. A later full
power cycle reached Bank 1 HIMON; early Bank 3 boot bytes were missed during
COM4 re-enumeration. The ACIA adapter was absent.

## Qualification matrix

Record board identity, CPU, console, candidate hashes, initial configuration,
commands, expected and actual results, transcript path/hash, and final readback
for each hardware session. Mark a gate passed only when evidence supports it.

| Gate | Status / required evidence |
| --- | --- |
| Rebuild and all eight `make v2-check` host suites | See freeze manifest and retained log |
| Alpha19 identity on board 2205 | Existing exact B3:F readback in linked report; re-establish live identity before further tests |
| Recovery preparation | 2512: verified four-bank backups, B1 authorized disposable, B3 recovery retained |
| Cold power-on, physical/software reset, HOLD | 2512: physical recovery reset, software restart, HOLD and guest relaunch passed; no-EDU B3 physical reset, Bank 1 autostart and timed S cancellation passed; cold power cycle reached Bank 1 HIMON, with early B3 bytes missed during COM4 re-enumeration |
| B/D/M/G/J and input rejection | 2512: four-bank dumps, RAM edit/restore, guarded rejection and handoffs passed; broader boundaries pending |
| L transfers | 2512: frozen probes loaded/read back exactly and executed with G; deliberate malformed/cancel/transfer-tail stress cases remain unqualified and are excluded from the stable-host release gate |
| F and I flash operations | 2512 B1:E: direct program, erase/rewrite, dense install, full-sector readback and restoration passed; deliberate interruption/fault injection excluded. Broader resident self-edit behavior remains unqualified and must not be claimed without separate evidence |
| Configuration and autostart | 2512: fixed-address HOLD, vector B3 handoff, S cancellation, disabled restart and config restoration passed; invalid config/vector and broader timing matrix pending |
| Public ROM and cross-bank RAM ABI | 2512 cross-bank RAM ABI probe and HOLD return passed; broader public entry coverage pending |
| W65C02 interrupts | 2512 physical NMI, VIA1 timer IRQ, BRK, register/stack/RTI probes passed |
| FT245 console and operation LEDs | 2512 command/transfer/load/flash/handoff passed; no-EDU FT245 selection read back as $00; visual EDU LED observations pending |
| W65C51N backup console | Deferred under the [ACIA RX issue](issues/ACIA_RX_2512_2205.md) until meter/probe/scope measurements are available: 2512 direct timed TX passed; RX and Q return failed to demonstrate reception ($70 status). Cause, fallback selection and transfer tests remain open |
| W65C816 | Pending board availability, detection, emulation and native interrupt/RAM ABI probe execution |
| Failure and recovery | Deliberate cable/host/power and active-flash fault injection excluded from the stable FT245 operating claim; no interruption-recovery or automatic-rollback claim. Existing guard/cancellation evidence is limited to the linked board tests |
| RC1 package | Frozen alpha21 artifact identities, exact board 2512 Bank 3 F match, and ZIP file hashes verified; scoped RC decision recorded. Public final-release disposition remains separate |

Start hardware qualification with live identity and backup collection, then
reset/console and read-only monitor checks. Establish scratch ranges and recovery
before flash tests. Keep unsupported or unavailable hardware gates explicitly
pending, or narrow the eventual release claim with a documented disposition.

Whole-image boot validation, installation atomicity, and automatic rollback are
not implemented; qualification must preserve the documented
[validation limits](STR8N_V2.md#validation-limits-and-operator-responsibility).
