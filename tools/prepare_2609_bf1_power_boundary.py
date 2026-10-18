"""Prove a stable transfer-boundary power-cut state and recovery offline."""
import argparse,json,hashlib,os,sys
from pathlib import Path
import plan_bf1_2609_route as route
import bf1_offline_recovery_model as harness
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    report=read(a.route/'report.json');assert report['passed'] and report['cases']==28
    for name,digest in report['sources'].items():assert sha(Path(name))==digest
    phase=a.route/'install-B-complete';info=read(phase/'plan.json');tx=info['transaction']
    source=[(a.backup/f'b{i}.bin').read_bytes() for i in range(4)];target=[(phase/f'b{i}.bin').read_bytes() for i in range(4)]
    assert route.p.bank_hashes(source)==info['source_sha256'] and route.p.bank_hashes(target)==info['expected_sha256']
    assert sha(phase/'installer-model-only.s19')==info['installer_sha256']
    events=read(phase/'events.json');erases=[i for i,e in enumerate(events) if e[0]=='erase'];assert len(erases)>=2
    prefix=events[:erases[1]];current=list(map(bytearray,source))
    for kind,bank,address,value in prefix:
        offset=address-0x8000
        if kind=='erase':current[bank][offset:offset+4096]=b'\xff'*4096
        else:assert kind=='program';current[bank][offset]&=value
    current=list(map(bytes,current));assert route.p.bank_hashes(current)==tx['operations'][1]['proposed_bank_sha256']
    assert route.c.latest(current)[2][16]==0xa0
    route.attest_recovery(current,source,events=prefix,info=info,certificate=route.p.bank_hashes(current))
    assert not a.out.exists();a.out.mkdir()
    harness.route=route;harness.c=route.c;harness.p=route.p;harness.j=route.j
    d=harness.Driver(a.out,a.backup,ROOT/'tmp/bfr2')
    # Complete model event history supplies the exact staged bodies.
    cells=route.c.old.read_s19(phase/'installer-model-only.s19')
    data=[bytes(cells[n] for n in range(0x3600,0x3680))]
    for i,op in enumerate(tx['operations'][1:]):
        body=bytearray((phase/f'transfer-{i:02d}.bin').read_bytes())
        if op['kind']=='payload-sector' and op['commit_address'] is not None:
            body[op['commit_address']-op['address']]=target[op['bank']][op['commit_address']-0x8000]
        data.append(bytes(body))
    assert [route.p.sha(v) for v in data]==[op['data_sha256'] for op in tx['operations']]
    cut,cutinfo=d.execute('stable-first-transfer-cut',source,tx,data,target,cut=len(prefix))
    assert list(map(bytes,cut.banks))==current and [list(event) for event in cut.events]==prefix
    # Boot with board-2609 virtual RTC/control/trim, then validate the RAM-only
    # CPU observation helper under the retained A40 monitor before live use.
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    cpu,mem=fresh();mem.fast=True
    for i,bank in enumerate(current):mem.banks[i][:]=bank
    ee=(a.backup/'eeprom.bin').read_bytes();mem.bus.ee[:128]=ee[:128];mem.bus.ee[0xff]=ee[128];mem.bus.ee[0xf0:0xf8]=ee[129:137]
    mem.spi.devices[0].data[:]=(a.backup/'sram.bin').read_bytes();mem.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 80 0E')
    retained=(bytes(mem.bus.ee),bytes(mem.spi.devices[0].data),bytes(mem.bus.rtc_regs));boot(cpu);assert mem.ram[0x7d30]==0xa0
    probe=(ROOT/'tmp/bf1cpu2/mode.bin').read_bytes();mem.ram[0x2000:0x2000+len(probe)]=probe
    text=console(cpu,mem,b'',entry=0x2000,limit=100000000);raw=bytes(mem.ram[0x2440:0x244e])
    assert raw[:6]==bytes.fromhex('02ff00000000') and raw[7:12]==bytes.fromhex('0117040102') and raw[13]==0xa5,raw.hex()
    assert retained==(bytes(mem.bus.ee),bytes(mem.spi.devices[0].data),bytes(mem.bus.rtc_regs))
    differences=[(b,i) for b in range(4) for i,(x,y) in enumerate(zip(current[b],mem.banks[b])) if x!=y]
    assert not differences,'Boot changes flash: classify before physical admission'
    (a.out/'fallback-A40-model.txt').write_bytes(text)
    recovery_cfg=route.c.latest(target)[2][8:24]
    rtx,rd,re=route.transaction(current,target,fallback_page=0xa0,target_config=recovery_cfg,label='Exact stable-boundary power-cut recovery to bf1 B',attestation=route.p.bank_hashes(current))
    d.execute('stable-boundary-recovery',current,rtx,rd,re)
    for i,bank in enumerate(current):(a.out/f'expected-cut-b{i}.bin').write_bytes(bank)
    result=dict(passed=True,board='2609',route_report_sha256=sha(a.route/'report.json'),backup_report_sha256=sha(a.backup/'report.json'),
                installer_sha256=info['installer_sha256'],first_transfer_sha256=info['transfer_sha256'][0],
                cut_boundary='After first full transfer verified, awaiting second SEND token; no second transfer byte sent',
                second_send_token=f"SEND 4096 BYTES FOR B{info['steps'][1][0]}:{info['steps'][1][1]:X}\r\n",
                expected_cut_hashes=route.p.bank_hashes(current),prefix_events=len(prefix),prefix_events_sha256=sha(a.out/'stable-first-transfer-cut/events.json'),
                fallback_page=0xa0,fallback_A40_model_boot=True,mode_probe_A40_model_result=raw.hex(),
                recovery_model_passed=True,model_processor='W65C02',fresh_transactions=2,
                physical_interruption_performed=False,physical_interruption_qualified=False,
                no_board_access=True,release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS exact stable boundary, fallback boot/probe and recovery instruction models',flush=True)
if __name__=='__main__':main()
