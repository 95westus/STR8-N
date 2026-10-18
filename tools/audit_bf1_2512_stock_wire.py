"""Independently parse the actual stock-source check wire log; only INFO, reads and exact RAM restore."""
import argparse,json,hashlib
from pathlib import Path
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def audit(events,original,expected_b3):
    index=0;writes=[];reads=0;identities=0;ram_final=False
    def event(direction):
        nonlocal index
        e=events[index];index+=1;assert e['direction']==direction;return bytes.fromhex(e['hex'])
    def receive(count):
        data=bytearray()
        while len(data)<count:data.extend(event('RX'))
        assert len(data)==count;return bytes(data)
    while index<len(events):
        assert event('TX')==b'\x55\xaa' and receive(1)==b'\xcc'
        command=event('TX');assert command in (b'\x0c',b'\x02',b'\x03'),'Unexpected command/EXEC'
        if command==b'\x0c':assert receive(12).hex()=='535842322c010000c8000000';identities+=1;continue
        packet=event('TX');address=int.from_bytes(packet[:3],'little');count=int.from_bytes(packet[3:6],'little');assert count>0
        if command==b'\x02':
            assert len(packet)==count+6 and 0x200<=address and address+count<=0x6500
            assert packet[6:]==original[address-0x200:address-0x200+count] and receive(1)==b'\0';writes.append((address,count))
        else:
            assert len(packet)==6;data=receive(count);reads+=1
            if address==0x8000:assert count==32768 and data==expected_b3
            else:
                assert 0x200<=address and address+count<=0x6500 and data==original[address-0x200:address-0x200+count]
                if address==0x200 and count==len(original):ram_final=True
    assert identities==1 and ram_final and writes==[(a,min(256,0x6500-a)) for a in range(0x200,0x6500,256)]
    return dict(passed=True,read_commands=reads,write_commands=len(writes),RAM_bytes_restored=sum(n for _,n in writes),only_original_RAM_written=True,no_EXEC_or_persistent_write_commands=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
    events=[json.loads(s) for s in (a.session/'serial.jsonl').read_text().splitlines()];original=(a.backup/'application-ram-original.bin').read_bytes();b3=(a.session/'b3-0.bin').read_bytes();r=audit(events,original,b3)
    r.update(wire_sha256=sha(a.session/'serial.jsonl'),original_RAM_sha256=sha(a.backup/'application-ram-original.bin'),source_b3_sha256=sha(a.session/'b3-0.bin'),audit_source_sha256=sha(Path(__file__)),board_access=False)
    negatives=[]
    for name,change in [('EXEC substituted for INFO',lambda ev:ev[2].update(hex='06')),('Persistent address substituted for RAM write',None)]:
        copied=[dict(e) for e in events]
        if change:change(copied)
        else:
            n=next(n for n,e in enumerate(copied) if e['direction']=='TX' and e['hex']=='02');data=bytearray.fromhex(copied[n+1]['hex']);data[:3]=(0x8000).to_bytes(3,'little');copied[n+1]['hex']=data.hex()
        try:audit(copied,original,b3)
        except AssertionError:negatives.append(dict(name=name,passed=True,refused=True))
        else:raise AssertionError('Altered transcript admitted')
    r['negative_checks']=negatives;a.out.write_text(json.dumps(r,indent=2)+'\n');print('PASS actual wire: exact full RAM restoration, no EXEC/persistent writes, altered traces refused',flush=True)
if __name__=='__main__':main()
