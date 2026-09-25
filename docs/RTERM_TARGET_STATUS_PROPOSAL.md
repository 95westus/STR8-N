# RTERM optional target status API proposal

Status: proposed 2026-09-25; display location confirmed as the status area.
No firmware, RTERM implementation, or wire contract changes are made here.

RTERM should offer an optional target-supplied text field beside its existing
system-name field in the bottom status area. The target chooses its meaning:

```text
... | SYS LAB6502 | BANK 3 | ...
... | SYS OTHER01 | TASK EDIT | ...
... | SYS OTHER01 | ...
```

An empty field occupies no space and adds no separator or placeholder. Systems
without banks need no bank-related code. Systems with their own banking code
can publish their own bank or partition description. RTERM treats the field
as display text and does not interpret bank numbers or reserve a BANK label.

## Proposed API and wire boundary

Use one replaceable text slot per terminal session initially. Proposed logical
operations, not yet exported functions or assigned ABI entry points:

```text
status_supported() -> boolean
status_set(text, length) -> queued | unsupported | invalid | busy
status_clear() -> queued | unsupported | busy
```

`status_set` replaces the entire field; length zero is equivalent to clear.
Propose a maximum of 32 printable ASCII bytes (`$20`-`$7E`) for the first
version. Length is explicit; a terminator is not transmitted. Reject oversized
or invalid text without altering the previous field. The sending API copies
accepted text before returning, so callers can reuse their buffer. `queued`
means accepted for transmission, not confirmation that it has been displayed.
Calls must not block waiting for terminal presence; callers decide whether to
retry `busy`, and unsupported terminals require no fallback output.

Define an optional, negotiated RMP/1 extension with the RTERM and target
projects before assigning a capability bit, channel/type, or payload bytes.
The wire operation replaces the field with a bounded length-prefixed string;
zero length clears it. Accept updates only for the active negotiated session.
Preserve existing peers and silent legacy startup. Do not overload the
board-name ACCEPT suffix or MESSAGE records, which have different semantics.

A target library can expose this API to applications. A 6502 implementation
may wrap it with a pointer/length calling convention, but register use,
clobbers, return codes, RAM ownership, entry addresses, and discovery/version
rules must be agreed separately in the owning firmware project. No new STR8-N
resident entry point is implied. Independent firmware may implement the wire
contract directly without any STR8-N ABI dependency.

## Ownership, lifecycle, and display

The target application or supervisor owns the text and must update it when
its meaning changes. A supervisor arbitrates multiple local producers; the
first version has no host-side provider registry. Clear before handing off
to code that will not maintain the field. Clear the receiver's cached text
on reset, disconnect, reconnect, rejection, session close, or lease expiry;
discard queued updates from the old session. A new session starts empty and
the target republishes if desired. An undetectable handoff within a live
session cannot be inferred by RTERM and remains the producer's responsibility.

RTERM renders the text literally inside the designated field, with no escape
processing, target-selected styling, or control over the surrounding status
area. Host connection, error, and transfer indications take priority when
space is limited; clip or omit the optional field. Provide a host preference
to hide it entirely. Targets that never publish leave it absent.

Fonts and appearance presets are local user preferences, described in the
[appearance proposal](RTERM_APPEARANCE_PROPOSAL.md). This API does not select
fonts, presets, or terminal personalities.

RTERM already implements a separate target-writable DEC status line in its
VT525 subset. That is an existing option for a whole target-controlled row.
This proposal concerns a compact field within RTERM's own bottom status area;
it does not change the DEC status line or grant access to the rest of the OIA.

## STR8-N bank use case

A STR8-N-aware producer could publish `BANK 3` after a completed bank selection,
and clear it or choose `BANK ?` when uncertain. That label, range validation,
and source of truth belong to the producer. RTERM must not infer bank state
from typed commands, prompts, the board name, or a previous boot. Another
banking implementation could publish `BANK 12`, `PART WORK`, or nothing through
exactly the same API. Temporary maintenance selections and handoffs need an
explicit producer policy so the text accurately describes the intended state.

## Implementation and validation

- RTERM: retain bounded session text and render it in normal and transfer
  layouts; check 80-column and narrow windows, clipping, and the hide setting.
- Target library: provide optional set/clear/support operations and document
  ownership, copying, nonblocking behavior, and handoff responsibilities.
- Protocol: document negotiation, payload, lifecycle, and compatibility;
  add fixed vectors and malformed-message tests.
- Host checks: cover arbitrary valid text, empty/clear, maximum length,
  invalid/control bytes, unsupported peers, updates, stale sessions,
  reset/reconnect, expiry, and independent DEC status-line behavior.
- Board proof: exercise a bank producer and a non-bank producer, then handoff
  to code without support. Host tests alone do not establish hardware correctness.

Related: [board-name proposal](BOARD_NAME_RMP1_PROPOSAL.md) and
[RTERM protocol](../../RTERM/PROTOCOL.md) and
[terminal coverage](../../RTERM/TERMINAL.md).
