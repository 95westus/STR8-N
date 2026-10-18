"""Execute one exact owner-authorized empty-bank test plan; no host memory dumps."""
import argparse,json,hashlib,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';PLANS=Q/'bf1-empty-bank-tests-2026-10-18-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PHASES={'2609-stage-empty-WDC':('2609','bf1'),'2609-WDC-to-full-bf1':('2609','stock'),
    '2604-empty-B0':('2604','bf1'),'2604-stage-empty-beta4':('2604','bf1'),'2604-beta4-to-full-bf1':('2604','beta4')}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase',choices=PHASES,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    board,source_mode=PHASES[a.phase];prep=read(PLANS/'preparation.json');kit=Path(prep['kit']);sys.path.insert(0,str(kit))
    import migrate;import factory_wdc;import legacy_transport as wire
    migrate.verify_kit(kit);assert sha(kit/'kit-manifest.json')==prep['kit_manifest_sha256']
    auth=Q/'bf1-empty-bank-hardware-owner-authorization-2026-10-18-r1.json';assert read(auth)['owner_authorized'] and board in read(auth)['boards']
    folder=PLANS/a.phase;plan=read(folder/'plan.json');assert sha(folder/'plan.json')==prep['plans'][a.phase] and plan['board']==board
    progress=read(PLANS/('CPU-report.json' if (PLANS/'CPU-report.json').exists() else 'CPU-progress.json'))
    checks=progress['checks'] if isinstance(progress,dict) else progress
    cpu=next(c for c in checks if c['name']==a.phase);assert cpu['passed'] and cpu['fresh_CPU_execution'] and cpu['plan_sha256']==sha(folder/'plan.json')
    assert cpu['installer_sha256']==plan['installer_sha256']==sha(folder/'installer-model-only.s19')
    if source_mode=='stock':factory_wdc.validate_plan(folder,kit)
    if source_mode=='beta4':migrate.validate_beta4_plan(folder,kit)
    active=read(Q/'active-rtc-campaign.json');state=read(Path(active['campaign_state']))
    assert active['RTC_sampling_owner_stopped'] and not state['RTC_sampling_active'] and not state['soak_active']
    assert set(active['powered_off_boards'])=={'2205','2512'}
    marker=Q/'device-operations'/f'{board}.json';guard=read(marker);assert guard['block_snapshot']
    if source_mode=='stock':
        assert guard['state']=='empty-bank-stock-debugger-connected' and read(Path(guard['stock_probe'])/'report.json')['passed']
    elif a.phase not in ('2609-stage-empty-WDC','2604-empty-B0'):
        assert guard['state']=='empty-bank-source-boot-checked'
        boot=read(Path(guard['run'])/'report.json');assert boot['passed'] and boot['board']==board
        assert boot['expected_hashes']==plan['source_sha256']
    else:assert guard['state']=='empty-bank-migration-preparation'
    ops=plan['transaction']['operations'] if source_mode=='stock' else plan['transaction']['operations'][1:]
    data=[]
    for n,op in enumerate(ops):
        body=(folder/f'transfer-{n:02d}.bin').read_bytes();assert len(body)==4096
        final=bytearray(body)
        if op['commit_address'] is not None:final[op['commit_address']-op['address']]=(folder/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(final).hexdigest()==op['data_sha256'];data.append(body)
    cells,entry=wire.read_s19(folder/'installer-model-only.s19');assert 0x2000==min(cells) and max(cells)<0x3800
    if a.check_only:print('PASS',a.phase,'exact authorization/CPU/model/plan guards; no ports opened');return
    assert not a.out.exists();a.out.mkdir(parents=True)
    ports=[p for p in comports() if p.serial_number==SERIALS[board]];assert len(ports)==1
    report=dict(board=board,phase=a.phase,passed=False,port=ports[0].device,plan=str(folder/'plan.json'),plan_sha256=sha(folder/'plan.json'),
        source_hashes=plan['source_sha256'],expected_hashes=plan['expected_sha256'],transfers_completed=0,
        host_memory_readbacks=False,device_full_source_preflight=True,device_target_verification=True,
        physical_reset_pending=False,clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,
        original_application_RAM_restoration_pending=True,started_utc=datetime.now(timezone.utc).isoformat())
    def save():publish(a.out/'report.json',report)
    save();publish(marker,dict(board=board,state='empty-bank-installing',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
    with (a.out/'serial.jsonl').open('x') as log:
        link=wire.Link(ports[0].device,log,stock=source_mode=='stock')
        try:
            if a.phase in ('2609-WDC-to-full-bf1','2604-beta4-to-full-bf1'):
                import importlib.util
                engine_path=ROOT/'release/bf1-migration-r1/install_transport.py'
                spec=importlib.util.spec_from_file_location('qualified_install_transport',engine_path)
                engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
                if source_mode=='beta4':
                    establish_b3(link);assert b'Preferred A 0000000D' in link.command('P')
                report.update(execution_may_have_started=True,packaged_install_transport_sha256=sha(engine_path));save()
                def progress(n,op):
                    report['transfers_completed']=n;save();print('TRANSFER',a.phase,n,op['bank'],hex(op['address']),flush=True)
                result=engine.execute(link,folder,stock=source_mode=='stock',host_readback=False,progress=progress)
                report.update(result,passed=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
                publish(marker,dict(board=board,state='empty-bank-reset-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
                print('PASS',a.phase,'shared package RAM transport/device verification; physical RESET required',flush=True)
                return
            if source_mode!='stock':
                establish_b3(link);text=link.command('P' if source_mode=='beta4' else 'VERSION')
                if source_mode=='bf1':assert b'2.0bf1' in text and ('Board: '+board).encode() in text
                else:assert b'Preferred A 0000000D' in text
                link.command('L',b'S19')
                for row in (folder/'installer-model-only.s19').read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
                loaded=link.until(b'\r\nB3> ');assert f'Entry {entry:04X}'.encode() in loaded
                assert not any(t in loaded for t in (b'Bad',b'Protected',b'Wrap',b'Error'))
                link.send(f'G {entry:04X}\r'.encode())
            else:
                for first in range(min(cells),max(cells)+1,256):
                    body=bytes(cells[x] for x in range(first,min(first+256,max(cells)+1)))
                    link.protocol(2);link.send(first.to_bytes(3,'little')+len(body).to_bytes(3,'little')+body)
                    assert link.exact(1)==b'\0'
                link.protocol(6);link.send(entry.to_bytes(3,'little'))
            report['execution_may_have_started']=True;save();link.until(b'Y then Enter> ');link.send(b'Y\r')
            for n,(op,body) in enumerate(zip(ops,data)):
                link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
                for offset in range(0,4096,64):link.send(body[offset:offset+64]);time.sleep(.01)
                report['transfers_completed']=n+1;save();print('TRANSFER',a.phase,n+1,op['bank'],hex(op['address']),flush=True)
            result=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90);(a.out/'result.txt').write_bytes(result)
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
            publish(marker,dict(board=board,state='empty-bank-reset-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
            print('PASS',a.phase,'device verified; physical RESET required',flush=True)
        except BaseException:
            report['failure']=traceback.format_exc();save();publish(marker,dict(board=board,state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()

if __name__=='__main__':main()
