# STR8-N v2-alpha19 qualification freeze

Candidate frozen on 2026-09-24: `2.0a19`, branch `v2`, source commit
`994ffc9` (full commit and SHA-256 identities in
[the freeze manifest](STR8N_V2_ALPHA19_FREEZE.json)). This is a qualification
candidate, not a completed release qualification.

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

## Qualification matrix

Record board identity, CPU, console, candidate hashes, initial configuration,
commands, expected and actual results, transcript path/hash, and final readback
for each hardware session. Mark a gate passed only when evidence supports it.

| Gate | Status / required evidence |
| --- | --- |
| Rebuild and all eight `make v2-check` host suites | See freeze manifest and retained log |
| Alpha19 identity on board 2205 | Existing exact B3:F readback in linked report; re-establish live identity before further tests |
| Recovery preparation | Pending: current four-bank backup/readback, recoverable image, selected scratch bank/ranges |
| Cold power-on, physical/software reset, HOLD | Pending full alpha19 run; record configuration and selected bank |
| B/D/M/G/J and input rejection | Pending hardware coverage, boundary behavior, bank restore and handoff |
| L transfers | Pending valid load, checksum/range failures, cancellation, transfer-tail recovery |
| F and I flash operations | Pending scratch-sector program, erase/rewrite, neighbor preservation, protection, cancel/error recovery, exact readback |
| Configuration and autostart | Vector path partially accepted; pending fixed-address, delay/hold, invalid config/vector and persistence matrix |
| Public ROM and cross-bank RAM ABI | Pending alpha19 board probe and return/reset behavior |
| W65C02 interrupts | Pending alpha19 physical NMI/IRQ and BRK evidence |
| FT245 console and operation LEDs | Pending alpha19 transfer/load/flash/handoff observations |
| W65C51N backup console | Pending init, timed TX, RX, selection and transfer tests; earlier 2205 RX remains suspect |
| W65C816 | Pending board availability, detection, emulation and native interrupt/RAM ABI probe execution |
| Failure and recovery | Pending controlled failure cases and demonstrated recovery; host fault injection alone is insufficient |
| Final release | Pending matrix disposition, documentation, final hashes and package verification |

Start hardware qualification with live identity and backup collection, then
reset/console and read-only monitor checks. Establish scratch ranges and recovery
before flash tests. Keep unsupported or unavailable hardware gates explicitly
pending, or narrow the eventual release claim with a documented disposition.

Whole-image boot validation, installation atomicity, and automatic rollback are
not implemented; qualification must preserve the documented
[validation limits](STR8N_V2.md#validation-limits-and-operator-responsibility).
