"""Exact qualified WDCMONV2-to-bf1 hardware transaction on 2512 only; owner RESET afterward."""
import argparse,json,hashlib,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from atomic_json import publish
import install_bf1_2512_legacy as staging
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-check',type=Path,required=True);ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    stage=read(a.stage/'report.json');backup=Path(stage['fresh_backup']);cp=Q/'bf1-2512-legacy-offline-checkpoint-2026-10-17-r1.json';checkpoint=read(cp)
    staging.validate(Path(stage['plan']).parent,backup,cp)
    verified=read(a.source_check/'report.json');assert verified['passed'] and verified['application_ram_restored'] and verified['source_stage_report_sha256']==sha(a.stage/'report.json')
    assert not read(a.stage/'restore-needed.json')['needed']
    review=read(Path(checkpoint['hardware_review']));phase=next(p for p in review['phases'] if p['phase']=='wdcmonv2-convert');source=Path(phase['plan']).parent;info=read(source/'plan.json')
    assert sha(source/'plan.json')==phase['plan_sha256'] and sha(source/'installer-model-only.s19')==info['installer_sha256']==phase['installer_sha256']
    assert verified['expected_b3_sha256']==info['source_sha256'][3] and read(Path(stage['plan']))['expected_sha256']==info['source_sha256']
    for n in range(4):assert sha(source/f'source-b{n}.bin')==info['source_sha256'][n] and sha(source/f'expected-b{n}.bin')==info['expected_sha256'][n]
    transfers=[]
    for n,op in enumerate(info['transaction']['operations'][1:]):
        data=(source/f'transfer-{n:02d}.bin').read_bytes();assert len(data)==4096;body=bytearray(data)
        if op['commit_address'] is not None:body[op['commit_address']-op['address']]=(source/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(body).hexdigest()==op['data_sha256'];transfers.append(data)
    cells,entry=read_s19(source/'installer-model-only.s19');assert min(cells)==entry==0x2000 and max(cells)==0x36ff
    auth=read(Q/'bf1-2512-hardware-owner-authorization-2026-10-17-r1.json');assert auth['hardware_qualification_authorized'] and auth['offline_checkpoint_sha256']==sha(cp)
    marker=Q/'device-operations/2512.json';assert read(marker)['state']=='historical-wdc-verified' and read(marker)['block_snapshot']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and active['baseline_index_sha256']==checkpoint['baseline_sha256']
    if a.check_only:print('PASS exact live WDC source, qualified converter, transfer hashes, RAM restoration and owner authorization; no port opened');return
    assert not a.out.exists();a.out.mkdir(parents=True);report=dict(board='2512',route_id='2512-wdcmonv2-to-bf1',phase='wdcmonv2-convert',passed=False,target_version='2.0bf1',source_check=str((a.source_check/'report.json').resolve()),source_check_sha256=sha(a.source_check/'report.json'),plan=str(source/'plan.json'),plan_sha256=sha(source/'plan.json'),installer_sha256=info['installer_sha256'],expected_hashes=info['expected_sha256'],source_hashes=info['source_sha256'],source_sha256=sha(Path(__file__)),fresh_backup=str(backup),clock_set=False,trim_changed=False,retained_sram_eeprom_written=False,started_utc=datetime.now(timezone.utc).isoformat(),transfers_completed=0)
    def save():publish(a.out/'report.json',report)
    save();publish(marker,dict(board='2512',state='installing-bf1-from-wdc',run=str(a.out.resolve()),block_snapshot=True));ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1
    with (a.out/'serial.jsonl').open('x') as log:
      link=Link(ports[0],log,stock=False);link.serial.rts=True;link.serial.reset_output_buffer();link.serial.reset_input_buffer()
      try:
        link.protocol(12);identity=link.exact(12);assert identity.hex()=='535842322c010000c8000000'
        for n in range(2):
            data=link.stock_read(0x8000,32768);(a.out/f'preflight-b3-{n}.bin').write_bytes(data);assert sha(a.out/f'preflight-b3-{n}.bin')==info['source_sha256'][3]
        original=(backup/'application-ram-original.bin').read_bytes();assert link.stock_read(0x200,len(original))==original
        publish(a.out/'restore-needed.json',dict(needed=True,first=0x200,last=0x64ff,sha256=hashlib.sha256(original).hexdigest(),source=str(backup/'application-ram-original.bin')))
        link.stock_load(cells,entry);(a.out/'title.txt').write_bytes(link.until(b'Y then Enter> '));link.send(b'Y\r');report['transaction_started']=True;save()
        for n,(op,data) in enumerate(zip(info['transaction']['operations'][1:],transfers)):
            link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
            for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
            report['transfers_completed']=n+1;save();print('TRANSFER',n+1,op['bank'],hex(op['address']),flush=True)
        (a.out/'result.txt').write_bytes(link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90));report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save();publish(marker,dict(board='2512',state='reset-required-bf1-from-wdc',run=str(a.out.resolve()),block_snapshot=True));print('PASS WDC-to-bf1 transaction verified; owner physical RESET required',flush=True)
      except BaseException:report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:link.serial.cancel_write();link.serial.reset_output_buffer();link.serial.close()
if __name__=='__main__':main()
