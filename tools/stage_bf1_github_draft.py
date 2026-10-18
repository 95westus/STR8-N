"""Stage the authorized GitHub bf1 draft with an isolated allowlisted source tree."""
import json,hashlib,subprocess,base64
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17';REPO='95westus/STR8-N';TAG='v2.0bf1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def gh(*args):
    r=subprocess.run(['gh',*args],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout
def api(method,endpoint,data=None,name='request'):
    args=['api','--method',method,endpoint]
    if data is not None:
        path=OUT/'github-operations'/(name+'.request.json');path.write_text(json.dumps(data));args+=['--input',str(path)]
    result=json.loads(gh(*args));(OUT/'github-operations'/(name+'.response.json')).write_text(json.dumps(result,indent=2)+'\n');return result
def main():
    prep=read(OUT/'preparation.json');assert prep['prepared'];package=Path(prep['package']);operations=OUT/'github-operations';operations.mkdir(exist_ok=False)
    assert not (OUT/'draft.json').exists()
    for info in prep['assets'].values():assert sha(Path(info['path']))==info['sha256']
    for p in package.rglob('*'):
        if p.is_file() and p.suffix!='.bin':p.read_bytes().decode('utf-8')
    # A root commit contains only the reviewed distribution. No v2.1 branch,
    # dirty workspace, private capture, or unrelated source enters the tag.
    tree=[]
    for i,p in enumerate(sorted(package.rglob('*'))):
        if not p.is_file():continue
        name=p.relative_to(package).as_posix();data=p.read_bytes()
        entry=dict(path=name,mode='100644',type='blob')
        if p.suffix=='.bin':
            blob=api('POST',f'repos/{REPO}/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'),f'blob-{i:03d}');entry['sha']=blob['sha']
        else:entry['content']=data.decode('utf-8')
        tree.append(entry)
    t=api('POST',f'repos/{REPO}/git/trees',dict(tree=tree),'tree')
    # Git blob SHA is independently computable for every uploaded file.
    recursive=api('GET',f"repos/{REPO}/git/trees/{t['sha']}?recursive=1",name='tree-verification')
    assert not recursive['truncated']
    actual={x['path']:x for x in recursive['tree'] if x['type']=='blob'}
    assert len(actual)==len(tree)
    for p in package.rglob('*'):
        if p.is_file():
            data=p.read_bytes();name=p.relative_to(package).as_posix()
            assert actual[name]['sha']==hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    commit=api('POST',f'repos/{REPO}/git/commits',dict(message='STR8-N 2.0bf1 pilot prerelease: pinned shared firmware and accepted qualification policy',tree=t['sha'],parents=[]),'commit')
    branch='codex/bf1-prerelease';ref=api('POST',f'repos/{REPO}/git/refs',dict(ref='refs/heads/'+branch,sha=commit['sha']),'branch')
    notes=OUT/'release-notes.md';notes.write_text('''STR8-N **2.0bf1 generation 48**, CLOCK **1.11**, FT245/F30D.

Fixes native-utility/CLOCK BATCH handoffs under both monitor slots. One pinned
firmware set is used for 65C02 and 65C816 **emulation-mode runtime**. The existing
startup CPU detector's brief native-mode entry is retained; native 816
applications/testing, ACIA and crypto remain deferred.

**Pilot prerelease.** Publication waits for the six-hour 2609 preserving soak
and verified original application RAM restoration. The 72-hour/300-cycle 2604
soak and seven-day RTC acceptance gates remain pending. This does not claim
full release qualification or generic installation permission.

Completed evidence includes both-slot hardware checks on 2604/2609 and original
payload restoration plus two verified-transfer-boundary power-cut/fallback/
recovery cases on 2609. It does not qualify mid-erase/program loss, arbitrary
byte timing or 2604 electrical behavior.

Download `str8n-2.0bf1-prerelease.zip` for all **19 pinned artifacts**, reproducible
source and updated user/ASM/command/technical guides. Separate monitor A0/B0
`.bin` assets are **4096-byte components**, not whole-device images. Use matching
providers from the ZIP; there is no generic stock/legacy flashing launcher.
Only the exact separately admitted 2604/2609 migration lineages are covered.

Verify `str8n-2.0bf1-assets.sha256`. No board backups, EEPROM/SRAM images,
captured full flash banks, private local receipts or serial logs are included.
Existing beta releases remain unchanged. The tag uses an isolated source tree,
with no v2.1 working-tree content.
''',encoding='utf-8')
    gh('release','create',TAG,'--repo',REPO,'--target',commit['sha'],'--title','STR8-N 2.0bf1 — BATCH fix pilot prerelease','--draft','--prerelease','--notes-file',str(notes))
    gh('release','upload',TAG,*[x['path'] for x in prep['assets'].values()],'--repo',REPO)
    releases=api('GET',f'repos/{REPO}/releases?per_page=100',name='release-list')
    matches=[r for r in releases if r['tag_name']==TAG];assert len(matches)==1
    release=api('GET',f"repos/{REPO}/releases/{matches[0]['id']}",name='draft-release')
    assert release['draft'] and release['prerelease'] and release['target_commitish']==commit['sha']
    assert {x['name'] for x in release['assets']}==set(prep['assets'])
    for asset in release['assets']:
        info=prep['assets'][asset['name']];assert asset['size']==info['bytes'] and asset['digest']=='sha256:'+info['sha256']
    receipt=dict(staged=True,repo=REPO,tag=TAG,release_id=release['id'],draft=True,prerelease=True,html_url=release['html_url'],source_commit=commit['sha'],source_tree=t['sha'],source_branch=branch,files=len(tree),preparation_sha256=sha(OUT/'preparation.json'),release_notes_sha256=sha(notes),assets=prep['assets'],created_utc=datetime.now(timezone.utc).isoformat(),publication_pending_2609_six_hour_gate=True,full_release_qualified=False)
    (OUT/'draft.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
