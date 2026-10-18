"""Private 2609 fixture staging and direct bootstrap rehearsal; never publishes.

Vendor bytes remain only in owner-local qualification output. No board ports.
"""
import argparse
import json
import sys
import traceback
from pathlib import Path
import bf1_offline_recovery_model as harness

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--backup',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    kit=a.kit.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
    sys.path.insert(0,str(kit));import runtime as r;import factory_wdc as f;import migrate
    backup=r.read(a.backup/'report.json');assert backup['passed'] and backup['application_ram_restored'] and backup['flash_repeat_verified'] and backup['eeprom_repeat_verified'] and backup['sram_repeat_verified']
    assert not r.read(a.backup/'restore-needed.json')['needed']
    for name,info in backup['files'].items():assert r.sha((a.backup/name).read_bytes())==info['sha256']
    banks=[(a.backup/f'b{n}.bin').read_bytes() for n in range(4)]
    selected=r.read(Q/'bf1-2609-windows-WDC-source-selection-2026-10-18-r1.json');stock=Path(selected['source_image']).read_bytes();assert r.sha(stock)==selected['sha256']
    seq,offset,row,valid=r.clean_journal(banks);cfg=row[8:24]
    before=[max(int.from_bytes(v[24+i*3:27+i*3],'little') for _,_,v in valid) for i in range(32)]
    retained=offset//4096+8;other=25-retained
    order=[other]+[n for n in (8,9,10,11,14)]+[retained,15]
    assert len(order)==8 and len(set(order))==8
    counts=list(before)
    for sector in order:counts[24+sector-8]+=1
    start=(retained-8)*4096;free=next(i for i in range(start,start+4096,128) if banks[3][i:i+128]==b'\xff'*128)
    data=[r.record(cfg,counts,seq+1)];state=list(map(bytearray,banks));operations=[]
    def append(kind,address,body,commit=None):
        initial=r.hashes(state);off=address-0x8000;state[3][off:off+len(body)]=body
        operations.append(dict(kind=kind,bank=3,address=address,commit_address=commit,source_sha256=initial,after_sha256=r.hashes(state),data_sha256=r.sha(body)))
    append('reserve-owner-local-fixture-attempts',free+0x8000,data[0],free+0x807f)
    for sector in order:
        body=stock[(sector-8)*4096:(sector-7)*4096];append('original-private-WDC-sector',sector<<12,body);data.append(body)
    staged=list(map(bytes,state));assert staged[:3]==banks[:3] and staged[3]==stock
    tx=dict(label='Owner-local original 65C816 WDC B3 fixture',source_sha256=r.hashes(banks),expected_sha256=r.hashes(staged),operations=operations,
        planned_erase_order=[[3,n] for n in order],counts_before=before,reserved_counts=counts,sequence_before=seq,sequence_after=seq+1,
        reservation_offset=free,source_config=cfg.hex(),target_config=cfg.hex(),model_only=True,installation_permitted=False)
    stage=out/'stage-original-816';info=r.compose(kit/'template',stage,banks,tx,data,staged)
    info.update(board='2609',phase='private-original-816-WDC-B3-staging',private_vendor_payload=True,public_distribution_permitted=False)
    (stage/'plan.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    history=out/'tracked-history.json';history.write_text(json.dumps(dict(schema=1,board='2609',config=cfg.hex(),counts=counts,sequence=seq+1,
        origin='Conservative host escrow after original WDC fixture staging; no lifetime erase claim'),indent=2)+'\n',encoding='utf-8')
    metadata=out/'private-metadata-escrow.bin';metadata.write_bytes(banks[3][0x1c00:0x2000])
    cap=out/'model-only-WDC-capture';cap.mkdir();files={}
    for n,body in enumerate(staged):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(cap/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    (cap/'capture.json').write_text(json.dumps(dict(schema=1,board='2609',model_fixture=True,repeat_verified=True,files=files),indent=2)+'\n',encoding='utf-8')
    forward=out/'original-816-to-bf1';factory=f.prepare(cap,kit,forward,history,metadata)
    model,wire,_,freeze=harness.setup();mf=r.read(ROOT/'tmp/blg4/manifest.json');model.S=mf['symbols'];model.MANIFEST=mf;S=model.S;checks=[]
    def execute(name,folder,source,expected,tx,stale=None,corrupt=None,partial=None,bootstrap=False):
        initial=list(map(bytearray,source))
        if stale is not None:initial[stale][0x123]^=1
        allowed={tuple(v) for v in tx['planned_erase_order']}
        class Memory(model.Memory):
            def __init__(self):
                super().__init__(initial,allowed,{},commit_records={});self.require_maintenance_commit=False;self.attempts=[0]*32
            def mutated(self,kind,address,value):
                super().mutated(kind,address,value)
                assert bytes(self.banks[0])==bytes(initial[0])
                if not bootstrap:assert all(bytes(self.banks[n])==bytes(initial[n]) for n in (1,2))
                if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
                # Once a tracked journal exists it must remain conservative.
                try:latest=r.latest(self.banks)[2]
                except ValueError:latest=None
                if latest is not None:
                    assert all(int.from_bytes(latest[24+i*3:27+i*3],'little')>=tx['counts_before'][i]+self.attempts[i] for i in range(32))
        memory=Memory();cells,entry=wire.read_s19(folder/'installer-model-only.s19')
        for address,value in cells.items():memory.ram[address]=value
        # This is the common E=1 worker test. The separate 816 entry bytes are
        # checked below; full native-entry execution requires hardware evidence.
        cpu=model.CPU(memory=memory,pc=0x2000);memory.cpu=cpu;memory.rx.extend(b'Y\r');operations=tx['operations'] if bootstrap else tx['operations'][1:]
        outcome='complete'
        for index,op in enumerate(operations):
            token=f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode()
            model.run(cpu,lambda:token in bytes(memory.tx) or cpu.pc==S['MIG_HALT'])
            if cpu.pc==S['MIG_HALT']:
                assert stale is not None and not memory.events and b'REFUSED/FAILED' in memory.tx;outcome='stale source refused';break
            memory.tx.clear();count=len(memory.events);body=bytearray((folder/f'transfer-{index:02d}.bin').read_bytes())
            if corrupt==index:body[100]^=1
            if partial==index:body=body[:2048]
            memory.rx.extend(body)
            if corrupt==index:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert len(memory.events)==count and b'REFUSED/FAILED' in memory.tx;outcome='corrupt transfer refused';break
            if partial==index:
                model.run(cpu,lambda:not memory.rx and cpu.pc==S['V2W_RAW_POLL']);assert len(memory.events)==count;outcome='partial transfer waits without erase';break
        else:
            model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert b'MIGRATION VERIFIED' in memory.tx and list(map(bytes,memory.banks))==expected
            assert [[bank,address>>12] for kind,bank,address,value in memory.events if kind=='erase']==tx['planned_erase_order']
        (out/(name+'-events.json')).write_text(json.dumps(memory.events)+'\n',encoding='utf-8')
        checks.append(dict(name=name,passed=True,outcome=outcome,mutation_events=len(memory.events),fresh_common_worker_CPU_execution=True,native_entry_CPU_execution=False))
        (out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8');print('PASS',name,outcome,flush=True)
    try:
        execute('stage-original-816',stage,banks,staged,tx)
        expected=[(forward/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        execute('direct-original-816-to-bf1',forward,staged,expected,factory['transaction'],bootstrap=True)
        for bank in (0,1):execute('direct-stale-bank-'+str(bank),forward,staged,expected,factory['transaction'],stale=bank,bootstrap=True)
        execute('direct-corrupt-first-transfer',forward,staged,expected,factory['transaction'],corrupt=0,bootstrap=True)
        execute('direct-partial-first-transfer',forward,staged,expected,factory['transaction'],partial=0,bootstrap=True)
        cells,entry=wire.read_s19(forward/'installer-model-only.s19');assert entry==0x3700 and bytes(cells[a] for a in range(0x3700,0x3710))==bytes.fromhex('38FB78D8A2FF9AF400002B4BAB4C0720')
        checks.append(dict(name='816 entry forces E=1/DP=0/DBR=0 before common worker; exact opcode contract only',passed=True,native_entry_CPU_execution=False))
        result=dict(passed=True,board='2609',checks=checks,cases=len(checks),backup_report_sha256=r.sha((a.backup/'report.json').read_bytes()),
            kit_manifest_sha256=r.sha((kit/'kit-manifest.json').read_bytes()),stage_plan_sha256=r.sha((stage/'plan.json').read_bytes()),forward_plan_sha256=r.sha((forward/'plan.json').read_bytes()),
            stock_source_sha256=selected['sha256'],source_WDC_bytes_private_only=True,public_distribution_permitted=False,
            model_only=True,board_access=False,hardware_qualified=False,native_entry_CPU_execution=False,
            pending=['native-entry hardware/readback checks','exact Windows installer transport','original-WDC RTC/storage behavior check','beta4 Windows route hardware checks'])
        (out/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    except Exception:
        (out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc(),board_access=False),indent=2)+'\n',encoding='utf-8');raise


if __name__=='__main__':main()
