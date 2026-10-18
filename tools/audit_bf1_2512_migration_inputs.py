"""Offline admission of exact 2512 migration inputs; no installer or serial access."""
import argparse, hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'
sha=lambda data:hashlib.sha256(data).hexdigest()
read=lambda path:json.loads(path.read_text())

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backup',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists()
    backup=args.backup;report=read(backup/'report.json')
    assert report['board']=='2512' and report['usb_serial']=='A10MQFLCA'
    assert report['passed'] and not report.get('failure') and report['ports_released']
    assert all(report[k] for k in ('flash_repeat_verified','eeprom_repeat_verified','sram_repeat_verified','application_ram_restored'))
    assert not any(report[k] for k in ('clock_set','trim_changed','persistent_writes','reset'))
    for name,info in report['files'].items():
        data=(backup/name).read_bytes();assert len(data)==info['bytes'] and sha(data)==info['sha256'],name
    restore=read(backup/'restore-needed.json');assert restore['verified'] and not restore['needed']
    banks=[(backup/f'b{n}.bin').read_bytes() for n in range(4)]
    for n,bank in enumerate(banks):assert len(bank)==32768 and bank==(backup/f'b{n}-repeat.bin').read_bytes()
    for name,size in [('eeprom',137),('sram',131072)]:
        data=(backup/(name+'.bin')).read_bytes();assert len(data)==size and data==(backup/(name+'-repeat.bin')).read_bytes()
    original=(backup/'application-ram-original.bin').read_bytes()
    assert original==(backup/'application-ram-restored.bin').read_bytes() and sha(original)==restore['sha256']
    active=read(Q/'active-rtc-campaign.json')
    assert sha(Path(active['baseline_index']).read_bytes())==report['baseline_sha256']==active['baseline_index_sha256']
    intake=read(Q/'bf1-2512-migration-route-preparation-2026-10-17-r1/intake.json')
    stock_ref=intake['source_fixtures']['private_2512_WDCMONV2'];stock_path=Path(stock_ref['path'])
    stock=stock_path.read_bytes();assert sha(stock)==stock_ref['sha256'] and len(stock)==32768
    assert stock==(stock_path.parent/'b0-before.bin').read_bytes()
    # Only the retained top sector still matches. Different lower sectors are
    # current board contents, not permission to replay the old whole-bank copy.
    assert stock[0x7000:]==banks[0][0x7000:]
    beta4_ref=intake['source_fixtures']['published_beta4'];archive=Path(beta4_ref['path'])
    assert sha(archive.read_bytes())==beta4_ref['sha256']
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();assert len(names)==len(set(names))
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        archive_manifest=json.loads(z.read('manifest.json'))
        assert archive_manifest['version']=='2.0b4' and archive_manifest['generation']==13
        for name,digest in archive_manifest['artifacts'].items():
            assert sha(z.read(name))==digest,name
            assert (ROOT/'BUILD/v2-beta4/kit'/name).read_bytes()==z.read(name),name
        for name,digest in beta4_ref['component_hashes'].items():assert sha(z.read(name))==digest
    pin_path=Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json';pin=read(pin_path)
    assert sha(pin_path.read_bytes())==intake['target_artifact_pin_sha256']
    build=ROOT/'tmp/bfx5';assert sha((build/'build-report.json').read_bytes())==pin['build_report_sha256']
    for name,info in pin['artifacts'].items():
        data=(build/'payload'/name).read_bytes();assert len(data)==info['bytes'] and sha(data)==info['sha256']
    old_f=(ROOT/'BUILD/v2-beta4/kit/str8n-v2-b4-f000-ffff.bin').read_bytes()
    new_f=(build/'payload/str8n-v2-recovery-f000-ffff.bin').read_bytes();assert old_f!=new_f
    result=dict(passed=True,scope='Exact input and preservation admission only; not converter execution or hardware route qualification',
        observed_utc=datetime.now(timezone.utc).isoformat(),backup=str(backup.resolve()),backup_report_sha256=sha((backup/'report.json').read_bytes()),
        source_fixture_sha256=sha(stock),published_beta4_archive_sha256=sha(archive.read_bytes()),target_pin_sha256=sha(pin_path.read_bytes()),
        source_admission=dict(WDCMONV2=dict(private_fixture=True,retained_top_sector_matches=True,current_B0_equals_historical_fixture=banks[0]==stock,
            changed_lower_sectors=[8+n for n in range(7) if banks[0][n*4096:(n+1)*4096]!=stock[n*4096:(n+1)*4096]],
            existing_stock_copy_policy_applicable=False,current_B0_must_be_preserved=True),
            beta4=dict(exact_published_archive_and_local_components_verified=True,old_F_sha256=sha(old_f),target_F_sha256=sha(new_f),core_conversion_required=True)),
        application_RAM_restored=True,retained_memory_double_reads_verified=True,baseline_sha256=report['baseline_sha256'],
        offline_converter_execution_qualified=False,hardware_route_qualified=False,publication_permitted=False,
        next_gates=['Receipt-bound source staging and restoration with conservative current wear history',
            'Separate stock transport/core conversion without overwriting occupied B0',
            'Published beta4 owned-range conversion and collision refusal',
            'Linked installers, interruption/recovery and original-source restoration offline',
            'Owner-coordinated source boot and full bf1 hardware acceptance on 2512 for each route'],
        audit_source_sha256=sha(Path(__file__).read_bytes()),board_access=False,clocks_trims_changed=False)
    args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
