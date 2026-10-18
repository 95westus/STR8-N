"""Execute one owner-authorized, exact offline-qualified 2512 restoration/staging phase."""
import argparse,json,hashlib,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from atomic_json import publish
import install_bf1_2512_legacy as staging
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PHASES=('wdcmonv2-restore-historical-source','wdcmonv2-restore-original','v2-0b4-stage-source','v2-0b4-convert','v2-0b4-restore-historical-source','v2-0b4-restore-original','final-bf1')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=PHASES,required=True);ap.add_argument('--prior',type=Path,required=True);ap.add_argument('--prior-transaction',type=Path);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    cp=Q/'bf1-2512-legacy-offline-checkpoint-2026-10-17-r1.json';checkpoint=read(cp);review=read(Path(checkpoint['hardware_review']))
    if a.phase=='final-bf1':
        final_root=Q/'bf1-2512-final-offline-2026-10-18-r1';final=read(final_root/'report.json')
        pointer=read(Q/'bf1-2512-final-offline-current.json');seal=final_root/'seal.json';assert Path(pointer['checkpoint']).resolve()==seal.resolve() and sha(seal)==pointer['sha256']
        for name,digest in read(seal)['files'].items():
            path=(final_root/name).resolve();assert path.is_relative_to(final_root.resolve()) and sha(path)==digest
        assert final['passed'] and final['routes']==['2512-owner-final-bf1'] and final['board_access'] is False
        assert final['planner_sha256']==sha(ROOT/'tools/plan_bf1_2512_legacy.py') and final['test_sha256']==sha(ROOT/'tools/qualify_bf1_2512_final.py')
        assert final['build_manifest_sha256']==sha(ROOT/'tmp/blg4/manifest.json')
        required={'final-bf1','final-bf1-0xa0','final-bf1-0xb0','final-corrupt-first-row','final-partial-first-row'}|{'final-stale-bank-'+str(n) for n in range(4)}
        assert required<={r['name'] for r in final['checks'] if r['passed']}
        for route in ('2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1'):
            pointer=read(Q/(route+'-acceptance-current.json'));receipt=Path(pointer['checkpoint']);assert sha(receipt)==pointer['sha256']
            accepted=read(receipt);assert accepted['passed'] and accepted['hardware_qualified'] and accepted['original_RAM_restored'] and accepted['board']=='2512'
        owner=read(Q/'bf1-2512-hardware-2026-10-17-r1/final-bf1-owner-instruction.json');assert owner['final_bf1_load_authorized'] and owner['complete_shared_bf1_firmware'] and owner['board']=='2512'
        source=final_root/'final-bf1';info=read(source/'plan.json');case=next(r for r in final['checks'] if r['name']=='final-bf1');assert case['fresh_CPU_execution'] and case['outcome']=='complete' and case['bank_sha256']==info['expected_sha256']
        phase=dict(plan=str(source/'plan.json'),plan_sha256=sha(source/'plan.json'),installer_sha256=info['installer_sha256'])
    else:
        phase=next(p for p in review['phases'] if p['phase']==a.phase);source=Path(phase['plan']).parent;info=read(source/'plan.json')
    staging.validate(Q/'bf1-2512-legacy-offline-2026-10-17-r6/wdcmonv2-stage-source',a.backup,cp)
    auth=read(Q/'bf1-2512-hardware-owner-authorization-2026-10-17-r1.json');assert auth['hardware_qualification_authorized'] and auth['offline_checkpoint_sha256']==sha(cp)
    assert sha(source/'plan.json')==phase['plan_sha256'] and sha(source/'installer-model-only.s19')==info['installer_sha256']==phase['installer_sha256']
    for n in range(4):assert sha(source/f'source-b{n}.bin')==info['source_sha256'][n] and sha(source/f'expected-b{n}.bin')==info['expected_sha256'][n]
    prior=read(a.prior/'report.json');assert prior['passed'] and prior['board']=='2512' and prior['application_ram_restored']
    if a.prior_transaction:
        t=read(a.prior_transaction/'report.json');assert t['passed'] and prior['install_report_sha256']==sha(a.prior_transaction/'report.json') and prior['full_flash_verified']
        prior_hashes=t['expected_hashes']
    else:prior_hashes=prior.get('expected_hashes')
    stock=a.phase=='wdcmonv2-restore-original'
    if stock:
        previous=Path(read(Q/'device-operations/2512.json')['transaction'])/'report.json';pr=read(previous);assert prior['source_stage_report_sha256']==sha(previous)
        prior_hashes=read(Path(pr['plan']))['expected_sha256'];assert prior['expected_b3_sha256']==info['source_sha256'][3]
    assert prior_hashes==info['source_sha256'],'Prior verified transaction does not admit this exact phase'
    transfers=[]
    for n,op in enumerate(info['transaction']['operations'][1:]):
        data=(source/f'transfer-{n:02d}.bin').read_bytes();assert len(data)==4096;body=bytearray(data)
        if op['commit_address'] is not None:body[op['commit_address']-op['address']]=(source/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(body).hexdigest()==op['data_sha256'];transfers.append(data)
    cells,entry=read_s19(source/'installer-model-only.s19');assert min(cells)==entry==0x2000 and max(cells)==0x36ff
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and active['baseline_index_sha256']==checkpoint['baseline_sha256']
    marker=Q/'device-operations/2512.json';operation=read(marker)
    allowed={'wdcmonv2-restore-historical-source':('bf1-wdc-hardware-checks-passed',),'wdcmonv2-restore-original':('historical-wdc-verified',),'v2-0b4-stage-source':('legacy-phase-checked',),'v2-0b4-convert':('legacy-phase-checked',),'v2-0b4-restore-historical-source':('bf1-b4-hardware-checks-passed',),'v2-0b4-restore-original':('legacy-phase-checked',)}
    allowed['final-bf1']=('legacy-phase-checked',)
    assert operation['state'] in allowed[a.phase]
    if a.phase=='final-bf1':assert operation['phase']=='v2-0b4-restore-original' and prior['phase']=='v2-0b4-restore-original' and prior['original_payload_restored'] and prior['conservative_wear_retained']
    if a.check_only:print('PASS exact',a.phase,'offline plan/transfers, fresh prior hardware and original RAM evidence; no port opened');return
    assert not a.out.exists();a.out.mkdir(parents=True)
    with serial_lease('bf1-register-2512',timeout=600,priority=True):
        assert read(marker)==operation;publish(marker,dict(board='2512',state='installing-legacy-phase',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
    original=(a.backup/'application-ram-original.bin').read_bytes();report=dict(board='2512',phase=a.phase,passed=False,source_hashes=info['source_sha256'],expected_hashes=info['expected_sha256'],plan=str(source/'plan.json'),plan_sha256=sha(source/'plan.json'),prior_report_sha256=sha(a.prior/'report.json'),source_sha256=sha(Path(__file__)),fresh_backup=str(a.backup.resolve()),clock_set=False,trim_changed=False,retained_sram_eeprom_written=False,started_utc=datetime.now(timezone.utc).isoformat(),transfers_completed=0)
    def save():publish(a.out/'report.json',report)
    save();ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1
    with (a.out/'serial.jsonl').open('x') as log:
      link=Link(ports[0],log,stock=False)
      if stock:link.serial.rts=True;link.serial.reset_output_buffer();link.serial.reset_input_buffer()
      try:
        if stock:
            link.protocol(12);assert link.exact(12).hex()=='535842322c010000c8000000'
            for n in range(2):
                data=link.stock_read(0x8000,32768);(a.out/f'preflight-b3-{n}.bin').write_bytes(data);assert sha(a.out/f'preflight-b3-{n}.bin')==info['source_sha256'][3]
            assert link.stock_read(0x200,len(original))==original
        else:
            establish_b3(link)
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert sha(a.out/f'preflight-b{bank}.bin')==info['source_sha256'][bank],f'B{bank} changed; execution forbidden';print('PASS current preimage',bank,flush=True)
            link.command('B3');assert b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096))==original
        publish(a.out/'restore-needed.json',dict(needed=True,first=0x200,last=0x64ff,sha256=hashlib.sha256(original).hexdigest(),source=str(a.backup/'application-ram-original.bin')))
        if stock:link.stock_load(cells,entry)
        else:link.monitor_load(source/'installer-model-only.s19')
        link.until(b'Y then Enter> ');link.send(b'Y\r');report['transaction_started']=True;save()
        for n,(op,data) in enumerate(zip(info['transaction']['operations'][1:],transfers)):
            link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
            for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
            report['transfers_completed']=n+1;save();print('TRANSFER',a.phase,n+1,op['bank'],hex(op['address']),flush=True)
        (a.out/'result.txt').write_bytes(link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90));report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save();publish(marker,dict(board='2512',state='legacy-reset-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True));print('PASS',a.phase,'transaction verified; owner physical RESET required',flush=True)
      except BaseException:report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True));raise
      finally:link.serial.cancel_write();link.serial.reset_output_buffer();link.serial.close()
if __name__=='__main__':main()
