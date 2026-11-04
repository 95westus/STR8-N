# Repository consolidation

The canonical repository is [95westus/STR8-N](https://github.com/95westus/STR8-N). Both
repositories were public before this consolidation. The user authorized merging
the Foundation-based work, histories and releases into STR8-N, then intends to
delete STR8N-F separately. No repository rename or visibility change is needed.

Main uses the verified F/MON/UTIL/DEV source tree. Its merge preserves the prior
STR8-N main and the Foundation main as parents. The old STR8-N main is also
saved as `archive/str8-n/main-before-foundation-20261104`. Foundation branches and advertised PR refs are retained
under `archive/str8n-f/*`; its four tags retain original names/object identities.
Existing STR8-N branch/tag identities, apart from advancing main, are retained.

All 12 original release records are indexed in ../RELEASE_INDEX.md. Existing
STR8-N releases remain; the four Foundation release records are copied with
their original asset names/bytes and original date/identity recorded as origin
metadata. GitHub assigns new destination release and asset IDs/timestamps.
Original releases and assets are not silently replaced. Exact-tag MIT/font
notice supplements accompany three early releases without changing old ZIPs.

The machine-readable origin/asset map is RELEASE_MIGRATION_MANIFEST.json.
Archived source PR/release metadata lives in archive/str8n-f. Source PR IDs are
not represented as native STR8-N PR IDs. Local Git bundles and original asset
downloads are retained separately for recovery.

F remains frozen. Component versions, short commands, CPU variants, load/entry
addresses and compatibility stay independent. Main does not claim new board
qualification. Runtime/private captures, ignored BUILD files and unrelated RTC
work are not introduced by the source merge. Existing working copies are left
unchanged; the isolated consolidated checkout supplies the new main.

STR8N-F remains untouched by the migration. The user may delete it only after
checking the destination history, tags, downloads and verification receipt.
No deletion, repository archive flag, rename or visibility operation is included.
