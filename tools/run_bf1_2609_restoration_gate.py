"""Owner-coordinated exact 2609 original-payload restoration; no automatic reset."""
import argparse,hashlib,json,shutil,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from qualify_v2_spi_install import load_image
from atomic_json import publish
import bf1_2609_readonly as live
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case',choices=['restore-A40-retain-Bbf1','restore-original-B35-complete'],required=True)
    ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--prior-checks',type=Path,help='Required for B35 stage: completed current A40 restoration checks')
    ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    assert read(G/'owner-authorization.json')['owner_power_and_reset_actions_only']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205']
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    backup=read(a.backup/'report.json');assert backup['passed'] and backup['application_ram_restored'] and backup['ports_released']
    assert backup['flash_repeat_verified'] and backup['eeprom_repeat_verified'] and backup['sram_repeat_verified']
    assert not read(a.backup/'restore-needed.json')['needed']
    for name,info in backup['files'].items():assert sha(a.backup/name)==info['sha256'] and (a.backup/name).stat().st_size==info['bytes']
    pointer=read(Q/'bf1-2609-route-current.json');cp=Path(pointer['checkpoint']);assert sha(cp)==pointer['checkpoint_sha256']
    closure=read(cp);model_path=Path(closure['model_report']);assert sha(model_path)==closure['model_report_sha256']
    model=read(model_path);assert model['passed'] and model['cases']==28
    for name,digest in model['sources'].items():assert sha(Path(name))==digest
    source=model_path.parent/a.case;plan=read(source/'plan.json')
    case=next(c for c in model['checks'] if c['name']==a.case)
    assert case['passed'] and plan['expected_sha256']==case['bank_sha256']
    if a.case=='restore-original-B35-complete':
        assert a.prior_checks,'The B35 stage requires completed A40 hardware checks'
        prior=read(a.prior_checks/'report.json');previous=G/'restore-A40'
        assert prior['passed'] and prior['case']=='restore-A40-retain-Bbf1' and prior['board']=='2609'
        assert prior['full_flash_verified'] and prior['application_ram_restored'] and prior['ports_released']
        assert prior['transaction_report_sha256']==sha(previous/'report.json')
        assert read(previous/'activation-completed.json')['hardware_report_sha256']==sha(a.prior_checks/'report.json')
        assert not read(a.prior_checks/'restore-needed.json')['needed'] and not read(previous/'restore-needed.json')['needed']
        for bank,digest in enumerate(plan['source_sha256']):
            assert sha(a.prior_checks/f'before-checks-b{bank}.bin')==sha(a.prior_checks/f'after-checks-b{bank}.bin')==digest
        assert (a.prior_checks/'eeprom-after.bin').read_bytes()==(a.backup/'eeprom.bin').read_bytes()
        assert (a.prior_checks/'sram-after.bin').read_bytes()==(a.backup/'sram.bin').read_bytes()
    else:
        assert a.prior_checks is None
        assert [sha(a.backup/f'b{i}.bin') for i in range(4)]==plan['source_sha256'],'Fresh preimage differs; replan offline'
    assert sha(source/'installer-model-only.s19')==plan['installer_sha256']
    transfers=[]
    for i,digest in enumerate(plan['transfer_sha256']):
        path=source/f'transfer-{i:02d}.bin';assert sha(path)==digest and path.stat().st_size==4096;transfers.append(path.read_bytes())
    assert len(transfers)==len(plan['steps'])
    cells,entry=read_s19(source/'installer-model-only.s19');assert entry==0x2000
    if a.check_only:print('PASS exact restoration inputs, preserved backup and current source receipts; no board opened');return
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['state']=='gate-restoration-authorized' and guard['block_snapshot']
    assert guard['case']==a.case and guard['backup_report_sha256']==sha(a.backup/'report.json')
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==backup['port']
    a.out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,a.out/'pinned-model-inputs')
    report=dict(board='2609',case=a.case,port=port,passed=False,started_utc=datetime.now(timezone.utc).isoformat(),
                authorization_sha256=sha(G/'owner-authorization.json'),backup=str(a.backup.resolve()),backup_report_sha256=sha(a.backup/'report.json'),
                model_report_sha256=sha(model_path),installer_sha256=plan['installer_sha256'],source_hashes=plan['source_sha256'],
                expected_hashes=plan['expected_sha256'],transfers_completed=0,clock_set=False,trim_changed=False,
                eeprom_sram_written=False,automatic_reset=False,release_qualified=False,physical_interruption_test=False)
    if a.prior_checks:
        report['prior_hardware_checks']=str(a.prior_checks.resolve())
        report['prior_hardware_checks_sha256']=sha(a.prior_checks/'report.json')
        report['source_admission']='Fresh before/after flash reads from completed A40 checks, retained storage equal to pre-restoration backup, plus new live four-bank/RAM admission'
    shutil.copyfile(Path(__file__),a.out/'transaction-runner.py')
    save=lambda:publish(a.out/'report.json',report)
    save();publish(marker,dict(board='2609',state='installing',case=a.case,run=str(a.out.resolve()),block_snapshot=True))
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);version=link.command('VERSION');(a.out/'version-before.txt').write_bytes(version)
            assert b'65C816' in version and b'Board: 2609' in version
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert hashlib.sha256(data).hexdigest()==plan['source_sha256'][bank],'Stale live preimage; stop before write'
                print('PASS current preimage',bank,flush=True)
            link.command('B3');original=(a.backup/'application-ram-original.bin').read_bytes()
            actual=b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096));assert actual==original
            publish(a.out/'restore-needed.json',dict(needed=True,first=512,last=0x64ff,sha256=hashlib.sha256(original).hexdigest(),source=str((a.backup/'restore-application-ram.s19').resolve())))
            report['cpu_mode_before']=live.cpu_mode(link,a.out,'cpu-mode-before');save()
            assert load_image(link,source/'installer-model-only.s19')==hashlib.sha256(bytes(cells[x] for x in range(min(cells),max(cells)+1))).hexdigest()
            (a.out/'title.txt').write_bytes(link.command('G 2000',b'Y then Enter> '));link.send(b'Y\r');report['transaction_started']=True;save()
            for i,((bank,sector),body) in enumerate(zip(plan['steps'],transfers)):
                link.until(f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode(),90)
                for off in range(0,4096,64):link.send(body[off:off+64]);time.sleep(.01)
                report['transfers_completed']=i+1;save();print('TRANSFER',i+1,bank,sector,flush=True)
            result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90);(a.out/'result.txt').write_bytes(result)
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
            publish(marker,dict(board='2609',state='reset-required',case=a.case,run=str(a.out.resolve()),block_snapshot=True))
            print('PASS restoration transaction verified; PHYSICAL RESET REQUIRED',flush=True)
        except BaseException:
            report.update(failure=traceback.format_exc(),needs_inspection=True);save()
            publish(marker,dict(board='2609',state='inspection-required',case=a.case,run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()
if __name__=='__main__':main()
