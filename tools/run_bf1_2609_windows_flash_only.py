"""Owner-authorized 2609-only Windows qualification transaction. No automatic reset.

Uses the exact prepared installer and packaged transport. Vendor staging plans
and all captures remain private qualification artifacts, never release inputs.
"""
import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime,timezone
from pathlib import Path
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from atomic_json import publish

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--phase',choices=('stage-original','original-to-bf1'),required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    kit=a.kit.resolve();sys.path.insert(0,str(kit));import migrate;import legacy_transport as wire
    migrate.verify_kit(kit)
    auth=Q/'bf1-2609-windows-migration-owner-authorization-2026-10-18-r1.json';assert read(auth)['owner_authorized'] and read(auth)['board']=='2609'
    stopped=Q/'bf1-powered-soak-2609-2026-10-17-r1';assert read(stopped/'status.json')['application_ram_restored'] and not read(stopped/'restore-needed.json')['needed']
    proof_root=Q/'bf1-2609-windows-offline-2026-10-18-r1';proof=read(proof_root/'report.json');assert proof['passed'] and proof['cases']==7
    key='stage_plan_sha256' if a.phase=='stage-original' else 'forward_plan_sha256'
    plan_root=proof_root/('stage-original-816' if a.phase=='stage-original' else 'original-816-to-bf1');plan=read(plan_root/'plan.json');assert sha(plan_root/'plan.json')==proof[key]
    assert sha(plan_root/'installer-model-only.s19')==plan['installer_sha256']
    backup=Q/'2609-windows-migration-backup-2026-10-18-r1';b=read(backup/'report.json');assert b['passed'] and b['application_ram_restored'] and not read(backup/'restore-needed.json')['needed']
    for name,item in b['files'].items():assert sha(backup/name)==item['sha256']
    wire_proof=Q/'bf1-2609-windows-stock-wire-2026-10-18-r2.json';wp=read(wire_proof);assert wp['passed'] and wp['transport_source_sha256']==sha(Path(wire.__file__))
    original=(backup/'application-ram-original.bin').read_bytes();assert len(original)==0x6300
    for n in range(4):
        assert sha(plan_root/f'source-b{n}.bin')==plan['source_sha256'][n] and sha(plan_root/f'expected-b{n}.bin')==plan['expected_sha256'][n]
    ops=plan['transaction']['operations'][1:] if a.phase=='stage-original' else plan['transaction']['operations']
    transfers=[]
    for n,op in enumerate(ops):
        data=(plan_root/f'transfer-{n:02d}.bin').read_bytes();assert len(data)==4096
        body=bytearray(data)
        if op['commit_address'] is not None:body[op['commit_address']-op['address']]=(plan_root/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(body).hexdigest()==op['data_sha256'];transfers.append(data)
    if a.phase=='stage-original':
        assert all(op['bank']==3 for op in ops) and ops[-1]['address']==0xf000
        assert plan['expected_sha256'][3]=='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
    if a.check_only:print('PASS exact owner authorization, backup, model/transport receipts, installer and transfers; no port opened');return
    assert not a.out.exists();a.out.mkdir(parents=True)
    marker=Q/'device-operations/2609.json'
    assert a.phase=='original-to-bf1','Flash-only launcher is only for the verified stock source'
    old=read(marker)
    assert old.get('block_snapshot') and old['state']=='private-original-816-WDC-verified'
    check=read(Path(old['run'])/'report.json')
    assert check['passed'] and check['original_B3_double_read_verified'] and check['application_ram_safe_ranges_restored']
    assert read(Q/'bf1-2609-windows-flash-only-owner-instruction-2026-10-18-r1.json')['extra_host_readbacks'] is False
    # Existing per-board guard has continuously blocked all other 2609 users.
    # Reuse that guard without asking the 2604 soak to yield again.
    publish(marker,dict(board='2609',state='windows-migration-installing',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']];assert len(ports)==1
    report=dict(board='2609',phase=('original-816-source' if a.phase=='stage-original' else 'A'),case=a.phase,passed=False,
        port=ports[0].device,plan=str(plan_root/'plan.json'),plan_sha256=sha(plan_root/'plan.json'),expected_hashes=plan['expected_sha256'],
        owner_authorization_sha256=sha(auth),model_proof_sha256=sha(proof_root/'report.json'),transport_proof_sha256=sha(wire_proof),
        kit_manifest_sha256=sha(kit/'kit-manifest.json'),packaged_transport_sha256=sha(Path(wire.__file__)),
        clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,physical_reset_pending=False,transfers_completed=0,
        started_utc=datetime.now(timezone.utc).isoformat(),private_WDC_fixture=a.phase=='stage-original',publication_permitted=False)
    def save():publish(a.out/'report.json',report)
    save();link=None
    with (a.out/'serial.jsonl').open('x') as log:
      try:
        link=wire.Link(ports[0].device,log,stock=a.phase!='stage-original')
        report['extra_host_readbacks_skipped_by_owner']=True
        report['prior_WDC_source_check_sha256']=sha(Path(old['run'])/'report.json')
        report['deferred_stock_debugger_stack_page']=0x700
        save()
        publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest(),source=str(backup/'application-ram-original.bin'),first=512,last=0x64ff))
        report['execution_may_have_started']=True;save()
        if a.phase=='stage-original':link.monitor_load(plan_root/'installer-model-only.s19')
        else:
            cells,entry=wire.read_s19(plan_root/'installer-model-only.s19');assert entry==0x3700
            first,last=min(cells),max(cells)
            for address in range(first,last+1,256):
                body=bytes(cells[x] for x in range(address,min(address+256,last+1)))
                assert 0x2000<=address and address+len(body)<=0x3800
                link.protocol(2);link.send(address.to_bytes(3,'little')+len(body).to_bytes(3,'little')+body)
                assert link.exact(1)==b'\0','WDC RAM load rejected; execution forbidden'
            link.protocol(6);link.send(entry.to_bytes(3,'little'))
        link.until(b'Y then Enter> ');link.send(b'Y\r');report['transaction_started']=True;save()
        for n,(op,data) in enumerate(zip(ops,transfers)):
            link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
            for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
            report['transfers_completed']=n+1;save();print('TRANSFER',n+1,op['bank'],hex(op['address']),flush=True)
        (a.out/'result.txt').write_bytes(link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90))
        report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
        publish(marker,dict(board='2609',state='windows-migration-reset-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
        print('PASS transaction verified; physical RESET required; RAM restoration remains pending',flush=True)
      except BaseException:
        report['failure']=traceback.format_exc();save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:
        if link:link.serial.close()


if __name__=='__main__':main()
