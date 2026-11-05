# Preserved local branch histories

Local-only branches are published in STR8-N with source/docs history and the exclusions below. Main and all existing public branch/tag targets remain unchanged.

## Branch map

| Original clone / branch | STR8-N branch | History |
| --- | --- | --- |
| str8-n / `codex/beta1-release` | [codex/beta1-release](https://github.com/95westus/STR8-N/tree/codex/beta1-release) | Original commit IDs |
| str8-n / `codex/beta35-rc1-checkpoint` | [codex/beta35-rc1-checkpoint](https://github.com/95westus/STR8-N/tree/codex/beta35-rc1-checkpoint) | Original commit IDs |
| str8-n / `codex/experimental-extensions` | [codex/experimental-extensions](https://github.com/95westus/STR8-N/tree/codex/experimental-extensions) | Filtered source history; new commit IDs |
| str8-n / `codex/flash-recovery` | [codex/flash-recovery](https://github.com/95westus/STR8-N/tree/codex/flash-recovery) | Original commit IDs |
| str8-n / `codex/rc1-main-merge` | [codex/rc1-main-merge](https://github.com/95westus/STR8-N/tree/codex/rc1-main-merge) | Original commit IDs |
| str8-n / `codex/rc1-powerfail-utc` | [codex/rc1-powerfail-utc](https://github.com/95westus/STR8-N/tree/codex/rc1-powerfail-utc) | Original commit IDs |
| str8-n / `codex/v2-beta33-asm` | [codex/v2-beta33-asm](https://github.com/95westus/STR8-N/tree/codex/v2-beta33-asm) | Filtered source history; new commit IDs |
| str8-n / `codex/v2-beta34-asm-summary` | [codex/v2-beta34-asm-summary](https://github.com/95westus/STR8-N/tree/codex/v2-beta34-asm-summary) | Filtered source history; new commit IDs |
| str8-n / `codex/v2-flash-config` | [codex/v2-flash-config](https://github.com/95westus/STR8-N/tree/codex/v2-flash-config) | Original commit IDs |
| str8-n / `codex/v2.1-alpha` | [codex/v2.1-alpha](https://github.com/95westus/STR8-N/tree/codex/v2.1-alpha) | Filtered source history; new commit IDs |
| str8-n / `main` | [archive/local/str8-n/main](https://github.com/95westus/STR8-N/tree/archive/local/str8-n/main) | Filtered source history; new commit IDs |
| str8-n / `v2` | [archive/local/str8-n/v2](https://github.com/95westus/STR8-N/tree/archive/local/str8-n/v2) | Filtered source history; new commit IDs |
| str8-n / `v2.0a24c1` | [v2.0a24c1](https://github.com/95westus/STR8-N/tree/v2.0a24c1) | Original commit IDs |
| foundation-bootstrap / `main` | [archive/local/foundation-bootstrap/main](https://github.com/95westus/STR8-N/tree/archive/local/foundation-bootstrap/main) | Original commit IDs |
| foundation-development / `codex/identify-sxb-edu` | [codex/identify-sxb-edu](https://github.com/95westus/STR8-N/tree/codex/identify-sxb-edu) | Original commit IDs |
| foundation-development / `codex/mona-monb` | [codex/mona-monb](https://github.com/95westus/STR8-N/tree/codex/mona-monb) | Filtered source history; new commit IDs |
| foundation-development / `codex/nf-v0.2.0` | [codex/nf-v0.2.0](https://github.com/95westus/STR8-N/tree/codex/nf-v0.2.0) | Original commit IDs |
| foundation-development / `codex/nf030-readme-label` | [codex/nf030-readme-label](https://github.com/95westus/STR8-N/tree/codex/nf030-readme-label) | Original commit IDs |
| foundation-development / `codex/str8nf-base1` | [codex/str8nf-base1](https://github.com/95westus/STR8-N/tree/codex/str8nf-base1) | Original commit IDs |
| foundation-development / `main` | [archive/str8n-f/main](https://github.com/95westus/STR8-N/tree/archive/str8n-f/main) | Original commit IDs |

B33 and B34 originally pointed to the same local commit. Their published named refs preserve that relationship; their distinct uncommitted source/doc versions were already saved separately under archive/uncommitted/2026-11-04/legacy-b33 and legacy-b34 on main. RC1-main-merge keeps its original commit ID because that commit was already public.

## Filtering and provenance

All 33 previously unpublished commits retain their source changes, author and committer identities/timestamps, full commit messages and mapped parent relationships. Generated binaries/S19/archives/maps, BUILD/private data directories, capture/result files and private inventory documents were omitted from their new trees. Older already-public history is used as immutable anchors and is not rewritten or removed.

Filtering changes commit IDs. The JSON catalog records every original-to-published mapping; original full histories remain in local Git bundles, not imported as unsafe parents. Original signatures are not claimed for rewritten commits. The retained source file blobs are byte-identical to their originals. Historical branches may need external/generated inputs and are not a claim of newly qualified runnable releases.

Conflicting local main/v2 tips are published under archive/local/* rather than moving current main or an existing public v2 branch. Existing Foundation archive refs and all original releases/tags remain unchanged. Frozen F on main stays at SHA-256 8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1.

No board, F build, flash, reset or source working-folder change is part of branch publication.
