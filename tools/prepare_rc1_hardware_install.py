"""Prepare exact preserving bf1 -> published rc1 plans; no board ports."""
import hashlib,json,sys,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=Q/'rc1-2604-2609-hardware-2026-10-18-r1'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
    assert not OUT.exists();OUT.mkdir()
    pointer=read(Q/'rc1-github-publication-current.json');receipt_path=Path(pointer['receipt']);assert sha(receipt_path.read_bytes())==pointer['sha256'];pub=read(receipt_path);assert pub['published'] and pub['tag']=='v2.0rc1' and pub['asset_count']==1
    req=urllib.request.Request(pub['download'],headers={'User-Agent':'STR8-N-owner-installation'})
    with urllib.request.urlopen(req,timeout=60) as response:data=response.read()
    assert sha(data)==pub['sha256']=='8e717a3672aded069a6498f0f0fa5a6c572b5b9bfb8926792b46749f5d60caa5';archive=OUT/'published-release.zip';archive.write_bytes(data)
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==77 and len(set(z.namelist()))==77
        assert all(n.startswith('str8n-2.0rc1/') and '..' not in Path(n).parts for n in z.namelist());z.extractall(OUT/'extracted')
    package=OUT/'extracted/str8n-2.0rc1';manifest=read(package/'release-manifest.json');assert manifest['version']=='2.0rc1' and manifest['generation']==49 and manifest['source_commit']==pub['source_commit']
    for name,info in manifest['files'].items():body=(package/name).read_bytes();assert len(body)==info['bytes'] and sha(body)==info['sha256']
    for row in (package/'SHA256SUMS.txt').read_text().splitlines():digest,name=row.split('  ',1);assert sha((package/name).read_bytes())==digest
    sys.path.insert(0,str(package/'migration'));import runtime as r;import migrate
    migrate.verify_kit(package/'migration');full=(package/'firmware/str8n-2.0rc1-apps-str8n-only.bin').read_bytes();assert len(full)==98304
    active=read(Q/'active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert not state['soak_active'] and not state['RTC_sampling_active'] and set(active['powered_off_boards'])=={'2205','2512'}
    auth=dict(owner_authorized=True,authorization='Install rc1 on 2604 and 2609 from the published ZIP, then verify both monitor slots and apps',boards=['2604','2609'],powered_off=['2205','2512'],clock_trim_changes_authorized=False,RTC_sampling_and_soaks_stay_stopped=True,deferred=['native 816 applications/tests','ACIA','crypto'],published_zip_sha256=pub['sha256'],source_commit=pub['source_commit'],created_utc=datetime.now(timezone.utc).isoformat())
    save(OUT/'owner-authorization.json',auth);plans={}
    for board,folder,check in [('2604','2604-beta4-to-full-bf1','2604-full-bf1-checks'),('2609','2609-WDC-to-full-bf1','2609-full-bf1-checks-r3')]:
        old=Q/'bf1-empty-bank-tests-2026-10-18-r1'/folder;hw=Q/'bf1-empty-bank-hardware-2026-10-18-r1'/check/'report.json';proof=read(hw);source=[(old/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        assert proof['passed'] and proof['expected_hashes']==r.hashes(source)
        cfg=r.clean_journal(source)[2][8:24];original_page=cfg[8] if cfg[7]==ord('P') else 0xa0;assert original_page in (0xa0,0xb0)
        desired=list(map(bytearray,source))
        for seg in r.read(package/'migration/layout.json')['segments']:
            b=seg['bank'];off=seg['address']-0x8000;body=(package/'migration/payload'/seg['file']).read_bytes()[seg['offset']:seg['offset']+seg['bytes']]
            if b==3 and off==0x3000:continue
            assert source[b][off:off+len(body)]==body,'Installed non-monitor firmware differs from release'
        for slot,off,page in [('a',0x2000,0xa0),('b',0x3000,0xb0)]:
            body=(package/f'firmware/str8n-2.0rc1-monitor-{slot}.bin').read_bytes();assert body==full[0x10000+off:0x11000+off] and r.migration.slot_valid(body,page) and int.from_bytes(body[8:12],'little')==49
            desired[3][off:off+4096]=body
        tx,rows,target=r.transaction(source,list(map(bytes,desired)),r.preference(cfg,original_page,49),f'{board} published rc1 MON B then MON A; preserve apps, settings and fallback')
        assert len(rows)==5 and [(o['bank'],o['address']) for o in tx['operations'][2:-1]]==[(3,0xb000),(3,0xa000)]
        assert all(target[b]==source[b] for b in (0,1,2)) and target[3][:0x2000]==source[3][:0x2000] and target[3][0x6000:]==source[3][0x6000:]
        name=board+'-published-rc1';info=r.compose(package/'migration/template',OUT/name,source,tx,rows,target);info.update(board=board,route='owner-preserving-bf1-to-published-rc1',original_preferred_page=original_page,source_hardware_receipt_sha256=sha(hw.read_bytes()),published_zip_sha256=pub['sha256'],owner_authorization_sha256=sha((OUT/'owner-authorization.json').read_bytes()))
        save(OUT/name/'plan.json',info);plans[name]=sha((OUT/name/'plan.json').read_bytes())
    save(OUT/'preparation.json',dict(passed=True,board_access=False,package=str(package),kit_manifest_sha256=sha((package/'migration/kit-manifest.json').read_bytes()),published_zip_sha256=pub['sha256'],plans=plans,only_MON_A_B_and_wear_journals_change=True,complete_apps_already_match_published_release=True,CPU_execution_qualified=False))
    print('PASS published ZIP/77 files, both exact preserving four-transfer plans; no ports opened')
if __name__=='__main__':main()
