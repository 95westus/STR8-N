# Source and release policy

`main` is the integration branch for the current released STR8N-F foundation
and its documentation. Release tags pin exact source checkpoints; tags and
published artifacts are not moved or silently replaced by later source edits.
The public 0.3.0 release is pinned independently of later main updates.
See the [release closeout](RELEASE_CLOSEOUT.md).

Use short `codex/...` feature branches and pull requests into `main` for new
work. A permanent development branch is not needed for the present project.
Mona can use a dedicated feature branch when implementation begins. This
policy does not create or reserve additional branches now.

F remains frozen at 0.3.0 g00000001 / BASE1 / PR05. Documentation, RAM tools
and optional images have separate change scopes. Changing F requires a
reviewed generation and appropriate qualification; changing a slogan or README
does not rebuild F. Existing [evidence limits](RELEASE_STATUS.md) stay explicit.

## Public description

Use: **4KB of firmware. One board. Up to four boot environments.**

Keep the explanation beside it: compatible, user-supplied images run one at a
time in selectable banks, sharing the same physical CPU, RAM and peripherals.
The kit supplies the foundation and tools; it does not include four operating
systems or add processors/RAM. Bank capacity and device/service requirements
still constrain each image. This describes the bank architecture, not the
number of physical boards qualified in the receipts.

Earlier archives and acceptance records retain their historical wording.
Current landing pages use the explicit description above. This wording is
technical product documentation, not a legal assurance.
