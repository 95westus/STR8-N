"""Owner-authorized exact bf1 2604 transaction; stops for physical RESET.

No automatic retry, rollback, RTC setter or retained-device writer. Only the
passed, receipt-bound B-first and subsequent A transactions are admitted.
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
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase',choices=['B','A'],required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--prior-hardware',type=Path);a=ap.parse_args()
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert state.get('2604_candidate_installation_authorized') is True
    assert set(active['powered_off_boards'])=={'2205','2609'} and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    pointer=read(ROOT/'output/qualification/bf1-2604-route-current.json');cp=Path(pointer['checkpoint']);assert sha(cp)==pointer['checkpoint_sha256'];closure=read(cp);rp=Path(closure['route_report']);assert sha(rp)==closure['route_report_sha256'];model=read(rp);assert model['passed'] and model['cases']==28
    name='install-B-complete' if a.phase=='B' else 'install-A-after-B-complete';source=rp.parent/name;info=read(source/'plan.json');case=next(v for v in model['checks'] if v['name']==name);assert case['passed'] and info['expected_sha256']==case['bank_sha256']
    if a.phase=='A':
        assert a.prior_hardware;prior=read(a.prior_hardware);assert prior['passed'] and prior['board']=='2604' and prior['phase']=='B' and prior['full_flash_verified'] and prior['initial_checks_passed']
        assert prior['expected_hashes']==info['source_sha256']
    for path,digest in model['sources'].items():assert sha(Path(path))==digest
    assert sha(source/'installer-model-only.s19')==info['installer_sha256']
    transfers=[]
    for i,digest in enumerate(info['transfer_sha256']):
        data=(source/f'transfer-{i:02d}.bin').read_bytes();assert len(data)==4096 and sha(source/f'transfer-{i:02d}.bin')==digest;transfers.append(data)
    cells,entry=read_s19(source/'installer-model-only.s19');assert entry==0x2000
    ports=[p for p in comports() if p.serial_number==SERIALS['2604']];assert len(ports)==1;port=ports[0].device
    a.out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,a.out/'pinned-model-inputs')
    marker=ROOT/'output/qualification/device-operations/2604.json';marker.parent.mkdir(parents=True,exist_ok=True)
    if marker.exists():assert read(marker).get('state') in ('idle','B-initial-checks-passed'),'Pending device operation must be reviewed'
    report=dict(board='2604',phase=a.phase,port=port,usb_serial=SERIALS['2604'],started_utc=datetime.now(timezone.utc).isoformat(),owner_authorized=True,authorization='Proceed with bf1 installation and initial checks on 2604, then start its soak; stop 2512 soak only after checks pass',passed=False,clock_set=False,trim_changed=False,retained_sram_eeprom_written=False,global_release_qualified=False,model_report_sha256=sha(rp),installer_sha256=info['installer_sha256'],source_hashes=info['source_sha256'],expected_hashes=info['expected_sha256'],transfers_completed=0,physical_reset_pending=False)
    def save(): (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    with serial_lease('bf1-install-2604',timeout=600,priority=True):
      marker.write_text(json.dumps(dict(board='2604',state='installing',run=str(a.out.resolve()),block_snapshot=True),indent=2)+'\n')
      with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);(a.out/'version-before.txt').write_bytes(link.command('VERSION'));(a.out/'time-before.txt').write_bytes(link.command('TIME'))
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert hashlib.sha256(data).hexdigest()==info['source_sha256'][bank],f'B{bank} stale: no installation permitted'
                print('PASS current preimage',bank,flush=True)
            link.command('B3');assert load_image(link,source/'installer-model-only.s19')==hashlib.sha256(bytes(cells[x] for x in range(min(cells),max(cells)+1))).hexdigest()
            (a.out/'title.txt').write_bytes(link.command('G 2000',b'Y then Enter> '));link.send(b'Y\r');report['transaction_started']=True;save()
            for n,((bank,sector),data) in enumerate(zip(info['steps'],transfers)):
                token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode();link.until(token,90)
                for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
                report['transfers_completed']=n+1;save();print('TRANSFER',a.phase,n+1,bank,sector,flush=True)
            result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90);(a.out/'result.txt').write_bytes(result)
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
            marker.write_text(json.dumps(dict(board='2604',state='reset-required',run=str(a.out.resolve()),phase=a.phase,block_snapshot=True),indent=2)+'\n')
            print('PASS',a.phase,'transaction verified; PHYSICAL RESET REQUIRED',flush=True)
        except BaseException:
            report['failure']=traceback.format_exc();report['needs_inspection']=True;save();marker.write_text(json.dumps(dict(board='2604',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True),indent=2)+'\n');raise
        finally:link.serial.close()
if __name__=='__main__':main()
