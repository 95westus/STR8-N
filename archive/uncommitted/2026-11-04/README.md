# Saved uncommitted source and documentation

These source-only worktree snapshots preserve unfinished work without merging
conflicting historical versions into the tested Foundation main. Each folder
records its original worktree/branch/base commit and the SHA-256 of every saved
file. The branch was created from consolidated STR8-N main; unpublished local
Git ancestry and application-managed refs were not imported.

Only changed tracked files and nonignored untracked source/docs were selected.
This is not a complete runnable checkout of each historical project. Original
Git bundles and full nonignored working-file backups remain owner-local.

BUILD/output files, generated binaries/S19/maps, private captures, result logs
and private inventories are not included. Capture/test tool source is retained;
the captured data those tools refer to remains local. Exact excluded-file lists
are in the local receipt, not in this public archive.

Original source bytes and notices are unchanged. Nested source .gitattributes
files are saved with .source appended so their rules cannot alter neighboring
snapshot bytes; the manifest records that original-to-stored path mapping.

The snapshots are unfinished source, not integrated or newly hardware-qualified
firmware. The active Foundation tree, frozen F and main branch remain unchanged.
