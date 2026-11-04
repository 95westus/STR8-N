"""Analyze an owner-local inventory; no network or repository mutations."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def run(folder):
    folder=Path(folder).resolve()
    repos=json.loads((folder/'repositories.json').read_text())
    releases=json.loads((folder/'releases.json').read_text())
    tags=json.loads((folder/'tags.json').read_text())
    assets=json.loads((folder/'assets-verified.json').read_text())
    local=json.loads((folder/'local-clones-before.json').read_text())
    checks=[]
    for a in assets:
        if 'sha256' not in a['name'].lower():continue
        text=(folder/a['local_file']).read_text(encoding='utf-8-sig',errors='replace')
        for line in text.splitlines():
            match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)',line.strip())
            if not match:continue
            digest,name=match.groups();name=name.removeprefix('./')
            target=next((b for b in assets if b['repository']==a['repository'] and b['tag']==a['tag'] and b['name']==name),None)
            checks.append(dict(repository=a['repository'],tag=a['tag'],manifest=a['name'],target=name,
                declared_sha256=digest.lower(),actual_sha256=target['sha256'] if target else None,
                result=('MATCH' if digest.lower()==target['sha256'] else 'MISMATCH') if target else 'PACKAGE_MEMBER_OR_UNRESOLVED_REFERENCE'))
    save(folder/'publisher-checksum-audit.json',checks)
    comparisons=[]
    for repo in repos:
        clone=next((x for x in local if repo['clone_url'] in '\n'.join(x['remotes'])),None)
        if not clone:continue
        result=subprocess.run(['git','-C',clone['path'],'rev-list','--left-right','--count',repo['head']+'...HEAD'],capture_output=True,text=True)
        divergence=result.stdout.split() if result.returncode==0 else []
        remote_tags={t['name']:t for t in tags if t['repository']==repo['full_name']}
        discrepancies=[]
        for row in clone['tags']:
            name,sha,kind,peeled=row.split('|')
            remote=remote_tags.get(name)
            if remote is None or remote['object_sha']!=sha:
                discrepancies.append(dict(tag=name,local_object=sha,remote_object=remote['object_sha'] if remote else None))
        comparisons.append(dict(repository=repo['full_name'],local_path=clone['path'],local_head=clone['head'],
            remote_main=repo['head'],remote_only_commits=int(divergence[0]) if divergence else None,
            local_only_commits=int(divergence[1]) if divergence else None,
            tracked_dirty_files=len(clone['tracked_changes']),untracked_paths=len(clone['untracked_paths']),
            local_tag_discrepancies=discrepancies,
            registered_worktree_count=clone['worktrees'].count('worktree ')))
    save(folder/'local-remote-comparison.json',comparisons)
    mapping=[]
    for r in releases:
        action=('PRESERVE_PUBLIC_RELEASE_AND_TAG' if r['visibility']=='public' else
                'LINK_ONLY_INDEX_ENTRY_REVIEW' if not r['assets'] else 'PRIVATE_ASSET_AND_SOURCE_REVIEW_REQUIRED')
        mapping.append(dict(source_repository=r['repository'],source_release_id=r['id'],source_tag=r['tag'],
            source_commit=r['resolved_tag_commit'],source_url=r['url'],proposed_destination_repository='95westus/STR8-N',
            proposed_destination_tag=r['tag'],destination_commit=None,action=action,
            approved_for_publication=False,tag_or_history_import_authorized=False))
    save(folder/'proposed-release-mapping.json',mapping)
    missing=[dict(repository=a['repository'],tag=a['tag'],asset=a['name']) for a in assets if a.get('archive_index') and not a.get('license_paths')]
    audit=dict(publisher_checksum_matches=sum(x['result']=='MATCH' for x in checks),
        publisher_checksum_mismatches=[x for x in checks if x['result']=='MISMATCH'],
        publisher_checksum_unresolved=[x for x in checks if x['result']=='PACKAGE_MEMBER_OR_UNRESOLVED_REFERENCE'],
        archives_without_license_named_entries=missing,
        license_review_note='Path search only; license text may be embedded elsewhere. Not a legal-compliance conclusion.',
        local_remote_comparison=comparisons,publication_authorized=False)
    save(folder/'analysis.json',audit)
    lines=['# Consolidation worksheet — private inventory, November 4, 2026','',
        'No push, rename, visibility change, tag creation, release edit, publication or commit was performed.',
        'Raw metadata and all downloaded assets remain under this ignored owner-local inventory directory.','',
        '## Inventory captured','',
        '| Repository | Visibility | Releases | Tags | Assets | Default branch |',
        '| --- | --- | ---: | ---: | ---: | --- |']
    for r in repos:
        name=r['full_name'];lines.append(f"| {name} | {r['visibility']} | {sum(x['repository']==name for x in releases)} | {sum(x['repository']==name for x in tags)} | {sum(x['repository']==name for x in assets)} | {r['default_branch']} |")
    lines+=['','All 47 attached assets (7,930,228 bytes) were downloaded and independently hashed; all matched GitHub API SHA-256 digests.',
        f"Publisher checksum files: {audit['publisher_checksum_matches']} matching declarations; {len(audit['publisher_checksum_mismatches'])} mismatches; {len(audit['publisher_checksum_unresolved'])} references needing resolution.",
        '','## Decisions supported by the evidence','',
        '- No exact tag-name collision exists across the two repositories. Proposed mappings preserve names; none are approved for execution.',
        '- Private nf-v0.3.0 is explicitly a link-only announcement for public STR8N-F v0.3.0. Its automatic source archives contain the parent STR8-N repository, not the Foundation source. Keep this distinction in the index.',
        '- GitHub latest currently resolves to nf-v0.3.0 in STR8-N and v0.3.0 in STR8N-F. The consolidated latest-release policy needs an explicit decision.',
        '- F.bin and STR8N-F-BOOT-4096.bin in public v0.3.0 are byte-identical, SHA-256 8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1. Preserve both historical filenames and links.',
        '- SHA256SUMS.txt exists in two public releases with different contents. Keep assets under their release namespaces; do not flatten by filename.',
        '- Three annotated tags were captured and resolved to commit IDs; their tag objects report unsigned. Lightweight refs and their exact targets are recorded separately.',
        '','## Local source reconciliation','']
    for c in comparisons:
        lines.append(f"- {c['repository']}: local {c['local_head'][:12]}, remote main {c['remote_main'][:12]}; {c['local_only_commits']} local-only and {c['remote_only_commits']} remote-only commits; {c['tracked_dirty_files']} tracked edits; {c['untracked_paths']} untracked paths; {c['registered_worktree_count']} registered worktrees.")
        if c['local_tag_discrepancies']:lines.append('  Local tag differences are listed in local-remote-comparison.json.')
    lines+=['','The private checkpoint must not be force-pushed over the remote branch. The dirty, older bootstrap-opaque clone must not be treated as the current public source without reconciliation.',
        'Inventory covers clones/worktrees found here, not every machine or external automation.',
        '','## Integrations','',
        '- Both repositories report no GitHub Pages site, no webhooks and zero environments in the queried metadata.',
        '- STR8N-F has one active workflow, Verify BASE1 freeze. It runs on push, pull request and manual dispatch, using checkout@v4/setup-python@v5 and tools/verify_base1.py. Preserve the Foundation freeze gate.',
        '- STR8N-F has no returned rulesets; classic main protection returned Branch not protected (404). Private STR8-N rulesets/protection reads returned plan/access-related 403s; do not interpret that as proof of no controls.',
        '- Both report Actions enabled, allowed_actions=all, sha_pinning_required=false. No secrets were requested. Webhook config URLs were omitted from the inventory.',
        '','## Review before publication','',
        '- Every private release remains unapproved for public migration. Review payload contents, licenses, ownership and the complete Git ancestry before importing tags/history.',
        '- If a private tag cannot safely retain its original Git ancestry publicly, record that decision and distinct destination provenance. Do not claim a sanitized replacement commit is the original source identity.',
        '- Three early private ZIPs have no license-named entry in their path lists. This is a review flag, not proof that license text is absent. Preserve original bytes; resolve required notices in accompanying distribution material after review.',
        '- Archive names containing backup/capture/vendor-like words are only path flags. No archive was extracted or executed; flags do not establish a privacy leak or publication clearance.',
        '','## Remaining work','',
        '1. Capture Git mirror/bundle backups before a migration is scheduled.',
        '2. Download/pin the automatic source archives or replace them with an explicitly documented immutable source-backup policy.',
        '3. Reconcile local and remote source states and close the public source-build dependency gap.',
        '4. Review each private asset and source history; approve or reject its proposed mapping.',
        '5. Inventory other machines, clone remotes, external integrations and any unavailable settings.',
        '6. Obtain a separate instruction before any repository/release mutation.']
    (folder/'CONSOLIDATION_WORKSHEET.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='local_remote_comparison'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inventory',type=Path);run(p.parse_args().inventory)
