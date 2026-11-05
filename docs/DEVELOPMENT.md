# Source and release policy

`main` integrates STR8-N F / MON / UTIL / DEV and their PC tools/docs.
See [component/source/releases](COMPONENT_GUIDE.md), [file formats](FILE_FORMATS.md)
and the [current build recipe](CONSOLIDATION_SOURCE_REVIEW.md).
Release tags pin exact source checkpoints; tags and
published artifacts are not moved or silently replaced by later source edits.
The public 0.3.0 release is pinned independently of later main updates.
See the [release closeout](RELEASE_CLOSEOUT.md).

Use short `codex/...` feature branches and pull requests into `main` for new
work. A permanent development branch is not needed for the present project.
MON, UTIL, DEV and PC-host work can evolve independently above the frozen
Foundation. This policy does not create or reserve additional branches now.

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
