# STR8-N repository and release consolidation plan

Status: proposal only, November 4, 2026. No repository rename, visibility
change, remote update, tag migration, publication or archival is authorized
by this document. Implementation requires a separate explicit instruction.

## Intended result

One canonical public STR8-N repository contains the distributable source,
reproducible build, documentation and releases for STR8-N F, MON, UTIL and
DEV. Component versions and compatibility profiles remain independent.
Private development history and device evidence remain private.

| Existing repository | Proposed destination | Visibility |
| --- | --- | --- |
| STR8-N | STR8-N-dev | Private |
| STR8N-F | STR8-N | Public |

Renaming the existing public repository retains its public history. GitHub
documents redirects after a rename, with exceptions including project sites
and hosted Actions; reusing an old repository name disables its redirect.
Reference: https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository

## Preparation and inventory

1. Record exact repository names, visibility, default branches, commit IDs,
   remotes, tags, release IDs, dates, titles, descriptions and asset URLs.
2. Back up both Git histories and download every release asset. Record byte
   counts and SHA-256 hashes, including source archives where applicable.
   Record signatures, provenance, qualification receipts and licensing.
3. Classify each private release and asset as public-distributable, private
   evidence, vendor-owned, or requiring review. Include only cleared material
   in a public migration. Board captures, saved settings, owner applications,
   serial identities and credentials are not automatically public assets.
4. Inventory links and integrations: README/manual URLs, release downloads,
   Git remotes, automation, CI secrets, submodules, package references and
   any GitHub Pages or Actions consumers. Preserve an inventory before editing.

## Safe repository transition

1. Establish a short publication freeze and confirm backups/inventories.
2. Rename private STR8-N to STR8-N-dev without changing its visibility.
3. Update and verify ALL private-clone remotes, worktrees, jobs and credentials
   before the name STR8-N is reused. Otherwise an old origin could point at
   the future public repository. Do not rely on that private redirect afterward.
4. Rename public STR8N-F to STR8-N. Keep its original name unused to preserve
   the public redirect. Verify original release and asset links individually;
   repair integration exceptions explicitly. Do not assume every consumer redirects.
5. Publish only a reviewed export of the unified distributable tree. Do not
   push the entire private development branch/history into the public repository.
   Check a clean clone for private files and required build dependencies.

## Release consolidation

Keep existing Foundation releases, tags and assets unchanged. Preserve old
full-system STR8-N releases as a distinct historical firmware line. Their
versions are not successive Foundation component versions.

For each cleared private release, prepare a migration manifest containing:

- Original repository, tag, commit, release date and release identity.
- Destination tag/release and any tag-name collision resolution.
- Original asset name, size, SHA-256 and destination asset/link.
- CPU/layout/profile requirements and actual qualification scope.
- Source snapshot, license/third-party notices and provenance.

Preserve original tags where they are unambiguous. For collisions, use an
explicit origin prefix such as legacy-str8-n-v2.0rc1; never move an existing
public tag to different bytes. Retain original asset filenames and checksums
for historical releases. Canonical new names apply to future builds, not
retroactively to qualified historical binaries.

Recreate approved release descriptions/assets in the canonical repository
with original dates and provenance stated in the body; do not present the
migration/publication timestamp as the original qualification date. GitHub
release records are migrated separately from Git tags. Verify every uploaded
asset by downloading it and comparing its hash to the inventory. Keep the
private originals until verification and acceptance are complete.

Create RELEASE_INDEX.md mapping both former release lines to their canonical
locations, components, versions, compatibility and support status. Explain
superseded, experimental and private-only records. Do not merge incompatible
artifacts into an apparently interchangeable single firmware version.

## Future public source and releases

Consolidate the authoritative distributable source and build dependencies.
The present naming recipe still depends on accepted local BUILD inputs; this
must be resolved before claiming a clean public source-only rebuild. A clean
public clone should build and test without private qualification captures.

Use STR8-N F / MON / UTIL / DEV and the canonical component filenames. Preserve
component versions/generations, CPU variants, load/entry addresses, ABI/profile,
checksums and qualification limits in a machine-readable release manifest.
Future component tags may use f/v..., mon/v..., util/... and dev/...; a complete
kit can have its own release identifier and exact component lock manifest.

Include the full MIT LICENSE with every binary package and retain applicable
third-party notices. New component identity/VERSION output carries the existing
holder's copyright notice. Foundation remains byte-for-byte frozen until a
separate deliberate revision is authorized. Embedded attribution supplements
the full license; it does not replace it.

## Acceptance, rollback and boundaries

Acceptance requires preserved historical asset hashes, reviewed tag mappings,
working old public links, verified remotes, no private-data exposure, a clean
source build, package/model tests, and separate hardware qualification for any
new firmware bytes. Test Pages/Actions/integrations individually if present.

Keep the inventories, backups and migration receipts. If acceptance fails,
stop new publication and restore the reviewed mapping or repository naming
under an explicit rollback plan. Privacy exposure cannot be undone merely by
renaming or deleting a repository; prevent it before the first public push.
Do not delete old tags/assets or archive repositories until acceptance is signed
off. No step in this plan is being executed by the copyright/naming task.
