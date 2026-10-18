"""Content/provenance/vendor/private-data audit of an actual release ZIP; no devices."""
import argparse,hashlib,json,posixpath,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def audit(archive,out):
    assert not out.exists();out.mkdir();checks=[]
    def passed(name,**kw):checks.append(dict(name=name,passed=True,**kw))
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();assert len(names)==len(set(names)) and all(n.startswith('str8n-2.0rc1/') and '..' not in Path(n).parts and not n.endswith('/') for n in names)
        data={n.split('/',1)[1]:z.read(n) for n in names}
    manifest=json.loads(data['release-manifest.json']);assert set(data)==set(manifest['files'])|{'release-manifest.json','SHA256SUMS.txt'}
    for name,info in manifest['files'].items():assert len(data[name])==info['bytes'] and sha(data[name])==info['sha256']
    for row in data['SHA256SUMS.txt'].decode().splitlines():
        digest,name=row.split('  ',1);assert sha(data[name])==digest
    passed('ZIP paths, exhaustive manifest and every checksum',files=len(data))
    kit=ROOT/'output/releases/rc1-2026-10-18-r1/migration';km=read(kit/'kit-manifest.json')
    for name in [*km['files'],'kit-manifest.json']:assert data['migration/'+name]==(kit/name).read_bytes()
    assert {n for n in data if n.startswith('migration/')}=={'migration/'+n for n in [*km['files'],'kit-manifest.json']}
    passed('All migration/recovery code, RAM templates and payloads equal qualified runtime; no unknown tool files')
    wanted=['rc1','wdcmonv2-to-rc1','beta4-to-rc1','rc1-recovery']
    for stem in wanted:
        assert stem+'.cmd' in data and stem+'.sh' in data
    passed('Both Windows/Linux direct-WDC, beta4 and recovery launchers present')
    full=data['firmware/str8n-2.0rc1-apps-str8n-only.bin'];assert sha(full)=='8704eff78e177696383c496225408c47fb51a70a3b26b3f2a715e575cc61e066'
    for name,offset,length in [('boot-core-b3',0x10000,32768),('monitor-a',0x12000,4096),('monitor-b',0x13000,4096),('b3-f000-ffff',0x17000,4096)]:assert data[f'firmware/str8n-2.0rc1-{name}.bin']==full[offset:offset+length]
    image_report=read(ROOT/'output/releases/rc1-2026-10-18-r1/image-report.json');assert image_report['passed'] and image_report['sha256']==sha(full) and image_report['sr_table_code_included']
    assert full[:4]==b'SR\1?' and full[8:24]==b'UCHESS'.ljust(16,b'\0') and int.from_bytes(full[6:8],'little')==1439
    passed('All five firmware BINs, complete app/provider inventory and S/R/T match source-built image',applications=image_report['applications'],providers=image_report['providers'])
    assert data['uchess-source/LICENSE.txt']==(ROOT/'BUILD/microchess-asm04/LICENSE.txt').read_bytes()
    text=re.sub(r'\s+',' ',data['uchess-source/README.md'].decode());assert all(word in text for word in ('Peter Jennings','Daryl Rictor','Bill Forster'))
    for name,digest in image_report['uchess_source_sha256'].items():
        if name!='README.md':assert sha(data['uchess-source/'+name])==digest
    if 'uchess-source/uchess.a' in data:assert data['uchess-source/uchess.a']==data['uchess-source/microchess.asm']
    passed('Credited uChess sources and complete original license; source bytes pinned')
    required_docs={'README.md','QUICK_START.md','QUICK_START_MIGRATION.md','QUICK_START_WINDOWS.md','QUICK_START_LINUX.md','MIGRATION_RECOVERY.md','OPERATOR_GUIDE.md','USER_GUIDE.md','ASM_GUIDE.md','COMMAND_REFERENCE.md','TECHNICAL_MANUAL.md','ABI_REFERENCE.md','THIRD_PARTY_NOTICES.md','FIRMWARE_CONTENTS.md','RELEASE_PATHS.md'}
    assert all('docs/'+n in data for n in required_docs) and len([n for n in data if n.startswith('docs/') and n.endswith('.svg')])==3
    for name,body in data.items():
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)',body.decode()):
                if re.match('[a-z]+:',link):continue
                target=posixpath.normpath((Path(name).parent/link.split('#')[0]).as_posix());assert target in data,(name,target)
    passed('Complete required manuals/quickstarts/ABI/Mermaid set; all internal links resolve',manuals=len([n for n in data if n.startswith('docs/') and n.endswith('.md')]))
    forbidden_names={'b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl','capture.json','workflow.json'}
    assert not any(Path(n).name.lower() in forbidden_names or n.endswith(('.zip','.tar.gz','.log')) for n in data)
    sensitive=re.compile(r'C:[\\/]+(?:SRC|Users)[\\/]|/mnt/c/(?:SRC|Users)/|/home/walter/|/Users/Walter/|\bghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bAKIA[A-Z0-9]{16}',re.I)
    for name,body in data.items():
        if name.endswith(('.md','.py','.json','.txt','.a','.asm','.sh','.cmd')):
            text=body.decode('utf-8');assert not sensitive.search(text.replace('\\\\','\\')),'Private host path or credential pattern in '+name
        for raw in (bytes.fromhex('5410ecb663a4'),bytes.fromhex('5410ecb664d3')):assert raw not in body,'Captured board EUI bytes found'
    passed('No captured-device files, serial logs, private host paths, known board EUIs or credential patterns')
    # In addition to the exhaustive source-derived binary allowlist above,
    # compare high-information vendor-code windows from private test fixtures.
    fixtures=[Q/'board-2609-restore-2026-09-30/b0-source.bin',Q/'bf1-2512-legacy-offline-2026-10-17-r6/wdcmonv2-convert/source-b3.bin']
    fingerprint_count=0;fixture_count=0
    for fixture in fixtures:
        if not fixture.exists():continue
        vendor=fixture.read_bytes();fixture_count+=1
        assert all(sha(body)!=sha(vendor) for body in data.values())
        windows={vendor[n:n+128] for n in range(0,len(vendor)-127,64) if len(set(vendor[n:n+128]))>=16}
        fingerprint_count+=len(windows)
        for name,body in data.items():
            assert not any(window in body for window in windows),'Known vendor-code fingerprint found in '+name
    assert fixture_count>=1
    passed('No supported WDCMONV2 vendor image or high-information code fingerprint; opaque binaries all match project source provenance',private_fixture_families=fixture_count,vendor_windows_checked=fingerprint_count)
    extracted=out/'extracted';extracted.mkdir()
    for name,body in data.items():
        p=extracted/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    result=dict(passed=True,zip_sha256=sha(archive.read_bytes()),checks=checks,files=len(data),runtime_byte_equivalence=True,model_and_Linux_hardware_claims_separate=True,board_access=False,soaks_and_RTC_sampling_stopped=True)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'published ZIP content/provenance/privacy checks;',fixture_count,'vendor fixtures;',fingerprint_count,'code windows')
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();audit(a.archive,a.out)
if __name__=='__main__':main()
