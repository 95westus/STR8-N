# STR8-N issue tracker

This repository tracks unresolved defects and hardware investigations in
[`docs/issues/`](docs/issues/). This index is the source of truth for issue
status. `TASKS.md` remains the broader project backlog.

| ID | Issue | Status | Resume condition |
| --- | --- | --- | --- |
| STR8N-001 | [W65C51N ACIA receive absent on boards 2205 and 2512](docs/issues/ACIA_RX_2512_2205.md) | Deferred | Meter, logic probe, or scope available for receive-path measurements |
| STR8N-002 | [2609 RESET-button cold-path observation](docs/issues/RESET_2609_COLD_PATH.md) | Closed | Correct S2/RESB captured; latch cleared, saved image retained, old handle rejected |
| STR8N-003 | [2609 disabled VIA CB flags block SPI after RESET](docs/issues/SPI_2609_DISABLED_CB_FLAGS.md) | Closed | Beta22: repeated physical/software cold starts and preservation passed; active-owner refusals retained |

## How to maintain this tracker

1. Copy [the issue template](docs/issues/TEMPLATE.md) into a new Markdown
   file in `docs/issues/`. Assign the next `STR8N-###` ID and add one row here.
2. Use **Open** for actionable work, **Deferred** when a named dependency is
   missing, and **Closed** only after the issue's close criteria are met.
3. Keep reproduction steps, board and firmware identities, evidence links,
   current findings, and close criteria in the issue file. Record each new
   result there instead of replacing earlier observations.
4. On closure, record the resolution and evidence in the issue file and
   change the status here to **Closed**. Leave the row for history.

Do not store owner-local serial captures, firmware backups, or other large
evidence files in this tracker. Link to their tracked reports and record
their hashes where needed.
