"""Owner-authorized exact 2609 bf1 B/A install; halt for physical RESET.

2604's worker continues on its own port. A short shared-lease registration
blocks 2609 snapshots; snapshots recheck that guard under their lease.
"""
import argparse,hashlib,json,shutil,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,read_s19
from qualify_v2_spi_install import load_image
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from atomic_json import publish
import bf1_2609_readonly as live
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase',choices=['B','A'],required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--prior-hardware',type=Path);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    root=ROOT/'output/qualification/bf1-2609-hardware-2026-10-17';auth=read(root/'owner-authorization.json');pre=root/'shared-firmware-preflight.json'
    assert auth['board']=='2609' and auth['unchanged_startup_detection_exception_accepted'] and auth['same_pinned_bf1_artifacts_as_2604'] and sha(pre)==auth['shared_firmware_preflight_sha256'] and read(pre)['passed']
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert state['2609_candidate_installation_authorized'] and set(active['powered_off_boards'])=={'2205'} and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    pointer=read(ROOT/'output/qualification/bf1-2609-route-current.json');cp=Path(pointer['checkpoint']);assert sha(cp)==pointer['checkpoint_sha256'];closure=read(cp);rp=Path(closure['model_report']);assert sha(rp)==closure['model_report_sha256'];model=read(rp);assert model['passed'] and model['cases']==28 and model['board']=='2609'
    backup=Path(closure['backup']);assert read(backup/'report.json')['passed'] and not read(backup/'restore-needed.json')['needed']
    source=rp.parent/('install-B-complete' if a.phase=='B' else 'install-A-after-B-complete');info=read(source/'plan.json');case=next(v for v in model['checks'] if v['name']==source.name);assert case['passed'] and info['expected_sha256']==case['bank_sha256']
    if a.phase=='A':
        assert a.prior_hardware;prior=read(a.prior_hardware);assert prior['passed'] and prior['board']=='2609' and prior['phase']=='B' and prior['full_flash_verified'] and prior['initial_checks_passed'] and prior['application_ram_restored']
        assert prior['expected_hashes']==info['source_sha256']
    for path,digest in model['sources'].items():assert sha(Path(path))==digest
    assert sha(source/'installer-model-only.s19')==info['installer_sha256']
    transfers=[]
    for i,digest in enumerate(info['transfer_sha256']):
        data=(source/f'transfer-{i:02d}.bin').read_bytes();assert len(data)==4096 and sha(source/f'transfer-{i:02d}.bin')==digest;transfers.append(data)
    assert len(transfers)==len(info['steps']);cells,entry=read_s19(source/'installer-model-only.s19');assert entry==0x2000
    if a.check_only:print('PASS exact 2609',a.phase,'receipts, shared firmware and installer inputs; no port opened');return
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']];assert len(ports)==1;port=ports[0].device
    a.out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,a.out/'pinned-model-inputs');marker=ROOT/'output/qualification/device-operations/2609.json'
    report=dict(board='2609',phase=a.phase,port=port,usb_serial=SERIALS['2609'],started_utc=datetime.now(timezone.utc).isoformat(),owner_authorized=True,authorization_sha256=sha(root/'owner-authorization.json'),shared_firmware_preflight_sha256=sha(pre),passed=False,clock_set=False,trim_changed=False,retained_sram_eeprom_written=False,global_release_qualified=False,model_report_sha256=sha(rp),installer_sha256=info['installer_sha256'],source_hashes=info['source_sha256'],expected_hashes=info['expected_sha256'],transfers_completed=0,physical_reset_pending=False)
    def save():publish(a.out/'report.json',report)
    save()
    with serial_lease('bf1-register-2609',timeout=600,priority=True):
        assert read(marker)['state'] in ('return-captured-offline-bf1-route-models-passed','B-initial-checks-passed'),'Pending operation must be inspected'
        publish(marker,dict(board='2609',state='installing',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
    # Snapshot protection remains published while only this board port is held.
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);version=link.command('VERSION');(a.out/'version-before.txt').write_bytes(version);assert b'65C816' in version and b'Board: 2609' in version
            (a.out/'time-before.txt').write_bytes(link.command('TIME'))
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert hashlib.sha256(data).hexdigest()==info['source_sha256'][bank],f'B{bank} stale: no installation permitted';print('PASS current preimage',bank,flush=True)
            link.command('B3');original=(backup/'application-ram-original.bin').read_bytes()
            actual=b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096));assert actual==original,'Application RAM differs from captured original'
            publish(a.out/'restore-needed.json',dict(needed=True,first=512,last=0x64ff,sha256=hashlib.sha256(original).hexdigest(),source=str(backup/'restore-application-ram.s19')))
            report['preinstall_cpu_mode']=live.cpu_mode(link,a.out,'preinstall-cpu-mode');save();print('PASS 65C816 emulation-mode entry',flush=True)
            assert load_image(link,source/'installer-model-only.s19')==hashlib.sha256(bytes(cells[x] for x in range(min(cells),max(cells)+1))).hexdigest()
            (a.out/'title.txt').write_bytes(link.command('G 2000',b'Y then Enter> '));link.send(b'Y\r');report['transaction_started']=True;save()
            for n,((bank,sector),data) in enumerate(zip(info['steps'],transfers)):
                link.until(f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode(),90)
                for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
                report['transfers_completed']=n+1;save();print('TRANSFER',a.phase,n+1,bank,sector,flush=True)
            result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90);(a.out/'result.txt').write_bytes(result)
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save();publish(marker,dict(board='2609',state='reset-required',run=str(a.out.resolve()),phase=a.phase,block_snapshot=True));print('PASS',a.phase,'transaction verified; PHYSICAL RESET REQUIRED',flush=True)
        except BaseException:
            report.update(failure=traceback.format_exc(),needs_inspection=True);save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()
if __name__=='__main__':main()
