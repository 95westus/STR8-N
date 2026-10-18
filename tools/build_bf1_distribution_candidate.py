"""Build a new offline migration-kit prototype from an explicit public file allowlist."""
import argparse,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--admit-empty-bank-hardware',action='store_true');a=p.parse_args();out=a.out.resolve();assert out.is_relative_to(ROOT) and not out.exists();out.mkdir(parents=True)
    stage=ROOT/'tmp/bf1-distribution-r1/migration';old=json.loads((stage/'kit-manifest.json').read_text());assert not old['distribution_qualified']
    layout=json.loads((stage/'layout.json').read_text());needed_payload={s['file'] for s in layout['segments']}|{'str8n-v2-recovery-slot-a0.bin'}
    for name,info in old['files'].items():
        if name.startswith('beta4-bridge/'):continue
        if name.startswith('payload/') and name[len('payload/'):] not in needed_payload:continue
        path=(stage/name).resolve();assert path.is_relative_to(stage.resolve());data=path.read_bytes();assert len(data)==info['bytes'] and sha(data)==info['sha256'];dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    sources=ROOT/'release/bf1-migration-r1'
    for name in ('runtime.py','legacy_transport.py','migrate.py','recover.py','user_cli.py','factory_wdc.py','factory_recover.py','install_transport.py','workflow.py'):shutil.copyfile(sources/name,out/name)
    factory=ROOT/'tmp/bwf1';fm=json.loads((factory/'manifest.json').read_text());raw=(factory/'bootstrap-template.s19').read_bytes();assert fm['passed'] and sha(raw)==fm['integrated_sha256']
    (out/'factory-template').mkdir();(out/'factory-template/bootstrap-template.s19').write_bytes(raw)
    keys=('count','commit_after','banks','commits','commit_addresses','commit_values','table','passed','integrated_sha256','entry_65C02','entry_65C816','native_entry_bytes','kind')
    (out/'factory-template/manifest.json').write_text(json.dumps({k:fm[k] for k in keys},indent=2)+'\n')
    app=ROOT/'output/qualification/bf1-app-image-2026-10-18-r1';report=json.loads((app/'report.json').read_text());image=(app/report['filename']).read_bytes();assert report['passed'] and sha(image)==report['sha256'];record=image[:1463];assert record[:4]==b'SR\1?' and record[8:24]==b'UCHESS'.ljust(16,b'\0')
    (out/'applications').mkdir();(out/'applications/uchess-record.bin').write_bytes(record)
    # Source recognition uses digests; neither WDC vendor images nor an
    # intermediate beta4 firmware distribution belongs in the final bf1 kit.
    profiles=json.loads((out/'profiles.json').read_text());b4=ROOT/'BUILD/v2-beta4/kit'
    profiles['wdcmonv2']['cpu']='65C02'
    profiles['wdcmonv2_65c816']=dict(cpu='65C816',source_sha256='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94',scope='Exact owner-local original 65C816 WDCMONV2 plus SPI/EDU image; no vendor bytes included')
    for key,name in (('maintenance_sha256','maint-8000-9fff'),('monitor_A_sha256','slot-a'),('monitor_B_sha256','slot-b'),('E_sha256','e000-efff'),('F_sha256','f000-ffff')):profiles['beta4'][key]=sha((b4/('str8n-v2-b4-'+name+'.bin')).read_bytes())
    (out/'profiles.json').write_text(json.dumps(profiles,indent=2)+'\n')
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(out.rglob('*')) if p.is_file()}
    assert not any(Path(n).name.lower() in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl') for n in files)
    for name in files:
        if name.endswith('.py'):
            text=(out/name).read_text();assert 'C:/SRC/STR8-N' not in text and 'C:\\SRC\\STR8-N' not in text and 'output/qualification' not in text
    if a.admit_empty_bank_hardware:
        q=ROOT/'output/qualification';hardware=q/'bf1-empty-bank-hardware-2026-10-18-r1';evidence={}
        for name in ('2609-WDC-to-full-bf1','2604-beta4-to-full-bf1','2609-full-bf1-checks-r3','2604-full-bf1-checks'):
            path=hardware/name/'report.json';proof=json.loads(path.read_text());assert proof['passed'];evidence[name]=sha(path.read_bytes())
            if 'packaged_install_transport_sha256' in proof:assert proof['packaged_install_transport_sha256']==files['install_transport.py']['sha256'] and proof['transfers_completed']==22 and proof['device_full_source_preflight'] and proof['device_target_verification']
            else:assert proof['boot_identity_verified'] and proof['UCHESS_discovered_executed_and_returned'] and proof['native_app_Batch_passed'] and proof['loader_acknowledged']
        for name in ('bf1-live-transport-tests-2026-10-18-r1.json','bf1-public-empty-bank-models-2026-10-18-r1/CPU-report.json','bf1-public-beta4-recovery-models-2026-10-18-r1/CPU-report.json'):
            path=q/name;proof=json.loads(path.read_text());assert proof['passed'];evidence[Path(name).parent.name if Path(name).name=='CPU-report.json' else Path(name).stem]=sha(path.read_bytes())
            if 'install_transport_sha256' in proof:assert proof['install_transport_sha256']==files['install_transport.py']['sha256']
        qualification=dict(schema=1,version='2.0bf1',empty_bank_routes_hardware_passed=True,portable_transport_tests_passed=True,
            live_WDC_debugger_identities=['SXB6'],required_files={n:i['sha256'] for n,i in files.items()},evidence_sha256=evidence,
            scope='Exact SXB6 original 65C816 WDC and published beta4; B0/B1/B2 erased; full preimage guard; all providers and UCHESS',
            limitations=['Linux physical serial migration not performed','Earlier RTC continuity failure remains unresolved','General occupied-bank upgrades not admitted','Early WDC cuts may require external programmer'],
            host_extra_RAM_readbacks_optional=True,full_release_qualified=False,publication_permitted=False)
        data=(json.dumps(qualification,indent=2)+'\n').encode();(out/'hardware-qualification.json').write_bytes(data);files['hardware-qualification.json']=dict(bytes=len(data),sha256=sha(data))
    manifest=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,files=files,live_installation_enabled=a.admit_empty_bank_hardware,distribution_qualified=False,requires_qualification=True)
    (out/'kit-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('PASS new portable candidate:',out,'files:',len(files),'admitted empty-bank live routes:',a.admit_empty_bank_hardware)
if __name__=='__main__':main()
