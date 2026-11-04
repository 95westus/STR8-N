# Golden-F recovery scope and 2512 B3 review

Owner direction on October 28, 2026: "stay in rec>" and "we assume f is golden."
This supersedes the proposal to deliberately interrupt F on 2512. No F fault
engine was built or run, no port was opened, and no board command was sent for
this scope decision. The release kit and board 2205 remain untouched.

## Recovery contract

Installed and independently verified F is the trusted BASE1 recovery anchor:
STR8N-F 0.3.0 g00000001 / BASE1 / PR05, exactly 4096 bytes, SHA-256
`8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
Its source and binary remain frozen. This is an operating assumption and write
policy; it adds no hardware write protection.

REC> executes from F. The matching RAM readback service also calls F for CRC
operations. These facilities require valid F. They are suitable for recovering
from interrupted RAM loads and inspecting/recovering user images or C/D; they
cannot supply a promised boot path after F itself becomes unreadable.

Runtime recovery qualification therefore leaves F intact. The proposed erased-F
and half-programmed-F cases are **NOT RUN / outside the golden-F runtime
contract**. This closes that runtime gate by scope, not as a passed fault test.
It does not qualify flash-pulse brownout or an interrupted initial F install.

## Exact B3 scope for this decision

| Region | Action now | Future runtime recovery boundary |
| --- | --- | --- |
| B3:F000-FFFF | No erase, program or fault injection | Golden F remains intact; enter REC> |
| B3:C000-DFFF | No append, erase or policy change | RAM journal tools only; exact append/erase budget reviewed before a live fault test |
| B3:8/9/A/B/E | No change | Owner images; preserve or explicitly admit a scratch target |
| B0-B2 | No change | Owner images; no implicit recovery backup allocation |
| Owner RAM/ZP | No helper load or change | Escrow before RAM tools; restore and verify afterward |

Total now: **zero flash erases, zero journal appends, zero board commands**.
No reset, power cut, chip removal or external programming is requested.

The last verified 2512 checkpoint remains the
[completed WDC trial](2512_WDC_MIGRATION_ACCEPTANCE.md): REC>, COM4 released,
sequence 965, three committed records, default B, mask 0F, all entries 8000,
C/D/F tracked counts 49/29/24. Original images, policy and owner RAM were
verified restored. These are prior verified values, not a fresh device read.

## Installation and remaining qualification

The programmer and WDC routes first establish the golden anchor. They must
verify its exact bytes and observe recovery before claiming installed BASE1.
The existing 2512 WDC happy path passed. Recovery after a failed initial F
install or an explicit F upgrade remains a separate, unqualified maintenance
case. This decision does not turn that failure case into a pass or remove the
WDC installation deliverable.

Still distinguish the already passed chip-idle B0 incomplete-image power loss
from unrun torn C/D commit, journal-rotation interruption and flash-pulse cases.
The live C/D provisioning entry after programmer-installed F also retains its
own hardware gate. Other supported CPUs/adapters and future kit integration
remain separate. No remaining gate is silently recorded as passed here.
