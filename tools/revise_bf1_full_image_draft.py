"""Add the verified complete image to the existing unpublished bf1 draft."""
import json,hashlib,subprocess,base64,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17';REPO='95westus/STR8-N'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def gh(*args):
    r=subprocess.run(['gh',*args],capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout
def main():
    prep_path=OUT/'preparation-full-image-r1.json';prep=read(prep_path);old=read(OUT/'draft.json');package=Path(prep['package'])
    assert prep['prepared'] and prep['owner_authorized_complete_image']
    operations=OUT/'github-full-image-operations';operations.mkdir(exist_ok=False)
    def api(method,endpoint,data=None,name='request'):
        args=['api','--method',method,endpoint]
        if data is not None:
            p=operations/(name+'.request.json');p.write_text(json.dumps(data));args+=['--input',str(p)]
        result=json.loads(gh(*args));(operations/(name+'.response.json')).write_text(json.dumps(result,indent=2)+'\n');return result
    prior=api('GET',f"repos/{REPO}/releases/{old['release_id']}",name='before-release')
    assert prior['draft'] and prior['prerelease'] and prior['target_commitish']==old['source_commit']
    assert {x['name'] for x in prior['assets']}==set(old['assets'])
    for asset in prior['assets']:assert asset['digest']=='sha256:'+old['assets'][asset['name']]['sha256']
    old_tree=api('GET',f"repos/{REPO}/git/trees/{old['source_tree']}?recursive=1",name='before-tree')
    known={x['sha'] for x in old_tree['tree'] if x['type']=='blob'};tree=[]
    for i,p in enumerate(sorted(package.rglob('*'))):
        if not p.is_file():continue
        data=p.read_bytes();digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();entry=dict(path=p.relative_to(package).as_posix(),mode='100644',type='blob')
        if digest in known:entry['sha']=digest
        elif p.suffix=='.bin':entry['sha']=api('POST',f'repos/{REPO}/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'),f'blob-{i:03d}')['sha']
        else:entry['content']=data.decode('utf-8')
        tree.append(entry)
    t=api('POST',f'repos/{REPO}/git/trees',dict(tree=tree),'tree')
    check=api('GET',f"repos/{REPO}/git/trees/{t['sha']}?recursive=1",name='verify-tree');assert not check['truncated']
    actual={x['path']:x['sha'] for x in check['tree'] if x['type']=='blob'};assert len(actual)==len(tree)
    for p in package.rglob('*'):
        if p.is_file():
            data=p.read_bytes();assert actual[p.relative_to(package).as_posix()]==hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    commit=api('POST',f'repos/{REPO}/git/commits',dict(message='Add reproducible shared 128 KiB bf1 image and MON A/MON B layout guide',tree=t['sha'],parents=[old['source_commit']]),'commit')
    api('PATCH',f"repos/{REPO}/git/refs/heads/{old['source_branch']}",dict(sha=commit['sha'],force=False),'branch')
    notes=(OUT/'release-notes.md').read_text(encoding='utf-8')
    notes=notes.replace('Download `str8n-2.0bf1-prerelease.zip` for all **19 pinned artifacts**, reproducible\nsource and updated user/ASM/command/technical guides.', '''The primary download is **`str8n-2.0bf1-firmware.bin`**, one complete **128 KiB**
image for both 65C02 and 65C816 emulation-mode runtime. It includes MON A,
MON B and matching providers in B0/B1/B2/B3 bank order. The full source/docs/
component/image bundle is **`str8n-2.0bf1-firmware-package.zip`**. Verify
`str8n-2.0bf1-firmware-assets.sha256` and consult the layout JSON.

MON A is B3:$A000; MON B is B3:$B000. A0/B0 in internal component filenames
denotes those hexadecimal start pages; the monitor names have not changed.
The whole image has fresh generic defaults and a new provisioning wear baseline.
It is a **fresh-provisioning/programmer image**, not a preserving upgrade for an
existing configured board. It replaces flash configuration, user storage and
wear history; the separately admitted preserving migration remains distinct.

The new complete layout passed 11 offline composition/boot/fallback/BATCH checks
in the W65C02 model. Its exact component firmware already has shared-CPU
hardware evidence; this new whole-image provisioning method has not been
physically flashed on the active soak boards. The earlier component-only ZIP
is retained alongside the new complete package.''')
    notes=notes.replace('captured full flash banks, private local receipts or serial logs are included.', 'captured full flash banks, private local receipts or serial logs are included.\nThe complete image is composed from source-built payloads, not a board dump.')
    (OUT/'release-notes-full-image-r1.md').write_text(notes,encoding='utf-8')
    added=[info['path'] for name,info in prep['assets'].items() if name not in old['assets']]
    assert len(added)==4
    gh('release','upload',old['tag'],*added,'--repo',REPO)
    updated=api('PATCH',f"repos/{REPO}/releases/{old['release_id']}",dict(target_commitish=commit['sha'],body=notes,draft=True,prerelease=True),'draft-update')
    assert updated['draft'] and updated['prerelease'] and updated['target_commitish']==commit['sha']
    assert {x['name'] for x in updated['assets']}==set(prep['assets'])
    for asset in updated['assets']:
        info=prep['assets'][asset['name']];assert asset['size']==info['bytes'] and asset['digest']=='sha256:'+info['sha256']
    revised={**old,'revision':'complete image r1','source_commit':commit['sha'],'source_tree':t['sha'],'files':len(tree),'preparation_sha256':sha(prep_path),'release_notes_sha256':sha(OUT/'release-notes-full-image-r1.md'),'assets':prep['assets'],'previous_source_commit':old['source_commit'],'revised_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'draft-full-image-r1.json').write_text(json.dumps(revised,indent=2)+'\n')
    # Explicit mutable active receipts. Immutable prior assets/receipts remain
    # archived under revisions/components-only and the previous source commit.
    shutil.copyfile(prep_path,OUT/'preparation.json');shutil.copyfile(OUT/'draft-full-image-r1.json',OUT/'draft.json');shutil.copyfile(OUT/'release-notes-full-image-r1.md',OUT/'release-notes.md')
    print(json.dumps(dict(draft=True,release_id=updated['id'],url=updated['html_url'],source_commit=commit['sha'],assets=len(updated['assets']),complete_image_sha256=prep['assets']['str8n-2.0bf1-firmware.bin']['sha256']),indent=2))
if __name__=='__main__':main()
