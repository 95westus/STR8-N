"""Report only the refusing guard number; no memory dumps or persistent writes."""
import argparse,json,sys,time,hashlib
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
KIT=ROOT/'tmp/bf1-distribution-r10/migration'
PLAN=Q/'bf1-2609-windows-beta4-offline-2026-10-18-r1/stage-beta4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def build(wire):
    cells,entry=wire.read_s19(PLAN/'installer-model-only.s19')
    mf=json.loads((ROOT/'tmp/blg4/manifest.json').read_text());S=mf['symbols']
    def word(a):return cells[a]+256*cells[a+1]
    calls=[word(a+1) for a in (0x3005,0x300a,0x300f,0x3014)]
    assert all(cells[a]==0x20 for a in (0x3005,0x300a,0x300f,0x3014))
    cleanup=word(0x3049);assert cells[0x3048]==0x20
    code=bytearray();jumps=[]
    def emit(*b):code.extend(b)
    def jsr(a):emit(0x20,a&255,a>>8)
    for b in b'GUARD ':emit(0xa9,b);jsr(S['V2W_PUTC'])
    for index,address in enumerate(calls,1):
        jsr(address);emit(0xb0,5,0xa9,ord(str(index)),0x4c);jumps.append(len(code));emit(0,0)
    emit(0xa9,ord('0'));finish=0x3800+len(code)
    emit(0x48);jsr(cleanup);emit(0x68);jsr(S['V2W_PUTC'])
    emit(0xa9,ord(':'));jsr(S['V2W_PUTC']);emit(0xad,0x30,0x62,0x18,0x69,ord('0'));jsr(S['V2W_PUTC'])
    for b in (13,10):emit(0xa9,b);jsr(S['V2W_PUTC'])
    emit(0x4c,7,0xf0)
    for index in jumps:code[index:index+2]=finish.to_bytes(2,'little')
    cells.update(dict(enumerate(code,0x3800)))
    cells.update(dict(enumerate(bytes((0x4c,0,0x38)),S['MIG_NEXT'])))
    cells={a:cells.get(a,0) for a in range(0x2000,0x3800+len(code))}
    return cells,entry,mf

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--offline',action='store_true');a=p.parse_args()
    sys.path.insert(0,str(KIT));import legacy_transport as wire;import migrate
    migrate.verify_kit(KIT);assert not a.out.exists();a.out.mkdir(parents=True)
    cells,entry,mf=build(wire);image=wire.s19(cells,entry);(a.out/'diagnostic.s19').write_bytes(image)
    if a.offline:
        import bf1_offline_recovery_model as h
        model,_,_,_=h.setup();model.S=mf['symbols'];model.MANIFEST=mf;checks=[]
        source=[(PLAN/f'source-b{n}.bin').read_bytes() for n in range(4)]
        for stale,token in ((False,b'GUARD 0:4'),(True,b'GUARD 1:0')):
            initial=list(map(bytearray,source))
            if stale:initial[0][0x100]^=1
            memory=model.Memory(initial,set(),{},commit_records={});memory.require_maintenance_commit=False
            for address,value in cells.items():memory.ram[address]=value
            cpu=model.CPU(memory=memory,pc=entry);memory.cpu=cpu;memory.rx.extend(b'Y\r')
            model.run(cpu,lambda:cpu.pc==0xf007)
            assert token in memory.tx and not memory.events
            checks.append(dict(stale=stale,passed=True,result=token.decode(),persistent_mutations=0))
        (a.out/'report.json').write_text(json.dumps(dict(passed=True,cases=2,checks=checks,diagnostic_sha256=sha(a.out/'diagnostic.s19'),board_access=False),indent=2)+'\n');print('PASS two guard diagnostic CPU checks; no persistent mutations');return
    proof=Q/'bf1-2609-guard-diagnostic-offline-2026-10-18-r1/report.json';pr=json.loads(proof.read_text());assert pr['passed'] and pr['diagnostic_sha256']==sha(a.out/'diagnostic.s19')
    from rtc_boards import SERIALS
    from rtc_prompt_sync import establish_b3
    from serial.tools.list_ports import comports
    from atomic_json import publish
    marker=Q/'device-operations/2609.json';guard=json.loads(marker.read_text());assert guard['state']=='inspection-required' and guard['block_snapshot']
    assert set(json.loads((Q/'active-rtc-campaign.json').read_text())['powered_off_boards'])=={'2205','2512'}
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609'])
    report=dict(board='2609',passed=False,host_memory_readbacks=False,persistent_writes=False,reset_owner_reply='done',recorded_utc=datetime.now(timezone.utc).isoformat())
    with (a.out/'serial.jsonl').open('x') as log:
        link=wire.Link(port,log)
        try:
            establish_b3(link);v=link.command('VERSION');assert b'2.0bf1' in v and b'Board: 2609' in v
            link.command('L',b'S19')
            for line in image.splitlines():link.send(line+b'\r\n');time.sleep(.04)
            link.until(b'\r\nB3> ');link.send(b'G 2000\r');link.until(b'Y then Enter> ');link.send(b'Y\r')
            result=link.until(b'\r\nB3> ',90);(a.out/'result.txt').write_bytes(result)
            import re;m=re.search(rb'GUARD ([0-4]):([0-4])',result);assert m
            report.update(passed=True,guard=int(m[1]),bank_or_input=int(m[2]),monitor_returned=True)
        finally:link.serial.close();publish(a.out/'report.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
