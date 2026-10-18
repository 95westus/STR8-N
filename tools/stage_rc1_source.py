"""Stage an allowlisted source commit for rc1, preserving the remote main tree."""
import base64,hashlib,json,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/releases/rc1-2026-10-18-r1';REPO='95westus/STR8-N'
sha=lambda b:hashlib.sha256(b).hexdigest()
def api(method,endpoint,data=None):
    cmd=['gh','api','--method',method,endpoint]
    if data is not None:
        request=OUT/'github-request.json';request.write_text(json.dumps(data),encoding='utf-8');cmd+=['--input',str(request)]
    r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stderr;return json.loads(r.stdout)
def main():
    assert not (OUT/'source-commit.json').exists()
    # Publish the exact final kit sources and reproducible firmware recipe.
    kit=OUT/'migration';target=ROOT/'release/rc1-migration-r1'
    manifest=json.loads((kit/'kit-manifest.json').read_text());assert manifest['live_installation_enabled']
    for name in [*manifest['files'],'kit-manifest.json']:
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():assert p.read_bytes()==(kit/name).read_bytes()
        else:p.write_bytes((kit/name).read_bytes())
    chess=ROOT/'release/rc1-uchess';assert not chess.exists();shutil.copytree(OUT/'base/uchess-source',chess)
    (ROOT/'release/rc1-build/README.md').write_text('''# Reproduce the rc1 BINs

First build the source-only candidate into a fresh short directory:

```text
python release/candidates/rc1/build.py --out C:\\tmp\\rc1build
python release/rc1-build/build_release_images.py --payload C:\\tmp\\rc1build\\payload --reference C:\\tmp\\rc1build\\build-report.json --uchess-record release/rc1-migration-r1/applications/uchess-record.bin --out C:\\tmp\\rc1images
```

The unchanged UCHESS executable/record is supplied with complete credited source
and its original license under `release/rc1-uchess`. It was assembled from
`uchess.a` with the actual ASM 0.5 instructions in both monitor-slot models.
The complete user ZIP includes the same sources, license and ASM/S/T/R walkthrough.
No vendor firmware or device capture is an image-composition input.
''',encoding='utf-8')
    paths=[ROOT/'README.md']
    for folder in ('release/candidates/rc1','release/rc1-migration-r1','release/rc1-build','release/rc1-uchess','docs/rc1'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    assert len({p.relative_to(ROOT).as_posix() for p in paths})==len(paths)
    head=api('GET',f'repos/{REPO}/git/ref/heads/main')['object']['sha'];parent=api('GET',f'repos/{REPO}/git/commits/{head}')
    entries=[]
    for p in sorted(paths):
        data=p.read_bytes();name=p.relative_to(ROOT).as_posix();entry=dict(path=name,mode='100644',type='blob')
        try:
            text=data.decode('utf-8');assert '\0' not in text
            assert not re.search(r'C:[\\/]+(?:SRC|Users)[\\/]|output[\\/]qualification|github_pat_|ghp_',text,re.I),name
            entry['content']=text
        except (UnicodeDecodeError,AssertionError) as error:
            if p.suffix not in ('.bin','.s19'):raise
            entry['sha']=api('POST',f'repos/{REPO}/git/blobs',dict(content=base64.b64encode(data).decode(),encoding='base64'))['sha']
        entries.append(entry)
    tree=api('POST',f'repos/{REPO}/git/trees',dict(base_tree=parent['tree']['sha'],tree=entries))
    commit=api('POST',f'repos/{REPO}/git/commits',dict(message='Release STR8-N v2.0rc1: generation 49, complete Windows/Linux kit and manuals',tree=tree['sha'],parents=[head]))
    actual=api('GET',f"repos/{REPO}/git/trees/{tree['sha']}?recursive=1");assert not actual['truncated'];blobs={p['path']:p['sha'] for p in actual['tree'] if p['type']=='blob'}
    for p in paths:
        data=p.read_bytes();assert blobs[p.relative_to(ROOT).as_posix()]==hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    receipt=dict(passed=True,repo=REPO,tag='v2.0rc1',source_commit=commit['sha'],source_tree=tree['sha'],parent_main=head,main_not_updated_yet=True,files={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)},allowlist_only=True,private_data_excluded=True)
    (OUT/'source-commit.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print('PASS allowlisted rc1 source commit:',commit['sha'],len(paths),'files; existing main tree preserved')
if __name__=='__main__':main()
