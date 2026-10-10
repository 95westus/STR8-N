"""Archive, exercise and verify the RAM-only SPI prototype on its exact board."""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-phase2'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def request(op,address=0,count=64,buffer=0x4000):
    return bytes((op,0,address&255,address>>8&255,address>>16,buffer&255,buffer>>8,count,0,0,0,0,0,0,0,0))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True)
    p.add_argument('--stage',choices=('archive','exercise','final'),required=True);p.add_argument('--attempt',default='');p.add_argument('--source-build',type=Path,default=ROOT/'BUILD/v2-rtc-trim');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    meta=read(BUILD/'build.json');test=read(BUILD/'test-results.json');assert test['passed'] and test['sha256']==meta['sha256'] and test['client_sha256']==meta['client']['sha256']
    prior=read(a.root/'prior/manifest.json');assert prior['repeat_verified']
    banks=[(a.root/f'prior/b{b}.bin').read_bytes() for b in range(4)]
    assert banks[3][:4096]==(a.source_build/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    capabilities=read(a.source_build/'build.json').get('capabilities',3)
    out=a.root/('spi-'+a.stage+a.attempt);out.mkdir(exist_ok=False)
    selected=read(a.root/'spi-stages.json') if (a.root/'spi-stages.json').exists() else {}
    archived_root=a.root/selected.get('archive','spi-archive')
    report=dict(board=a.board,stage=a.stage,flash_written=False,rtc_set=False,trim_changed=False,crypto_accessed=False,calls=[])
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if b'CLOCK>' in first or b'BM>' in first:link.command('Q')
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01'+bytes((capabilities,))+b'\0\x65\xff\x64'
            load(link,BUILD/'spi-prototype.s19');load(link,BUILD/'spi-client.s19')
            index=0
            def write(addr,data):
                link.write_ram(addr,data)
            def call(req,bank=3,bulk=False,kind=1,managed=0):
                nonlocal index
                write(0x3E00,req);write(0x3E20,bytes((kind,bank,managed)))
                output=link.command('G 2003' if bulk else 'G 2000');(out/f'call-{index:03d}.txt').write_bytes(output)
                data=link.dump(0x3E10,0x3E38);(out/f'call-{index:03d}.bin').write_bytes(data)
                item=dict(index=index,status=data[8],completed=data[9],bank=bank,bulk=bulk,mode=data[0x22],before_pcr=data[0x23],after_pcr=data[0x24],ddr_before=data[0x26],ddr_after=data[0x25])
                report['calls'].append(item);index+=1
                assert item['before_pcr']==item['after_pcr'] and item['ddr_before']==item['ddr_after'],item
                assert bool(data[0x27]&1)==(item['status']==0),item
                return item
            def array(label):
                blocks=[]
                for i in range(16):
                    r=call(request(1,i*8192,64,0x4000),bulk=True);assert r['status']==0 and r['completed']==64,r
                    block=link.dump(0x4000,0x5FFF);blocks.append(block);(out/f'{label}-{i:02d}.bin').write_bytes(block)
                    print(a.board,label,str(i+1)+'/16',flush=True)
                result=b''.join(blocks);(out/(label+'.bin')).write_bytes(result);return result
            if a.stage=='archive':
                if a.board=='2512':
                    r=call(request(1,count=1));assert r['status']==7,r
                    report.update(absent_sram=True,mode=r['mode'],passed=True)
                else:
                    first=array('array');second=array('array-repeat');assert first==second
                    modes={c['mode'] for c in report['calls']};assert len(modes)==1 and modes.pop() in (0,0x40,0x80)
                    report.update(passed=True,repeat_verified=True,array_sha256=sha(first),mode=report['calls'][0]['mode'],array_bytes=len(first),array_written=False)
            elif a.stage=='exercise':
                checks=[]
                if a.board=='2512':
                    for bank in range(4):assert call(request(0,count=0),bank)['status']==7
                    checks.append('no-EDU usability failure in all caller banks')
                else:
                    archived=(archived_root/'array.bin').read_bytes();assert archived==(archived_root/'array-repeat.bin').read_bytes()
                    for bank in range(4):
                        r=call(request(0,count=0),bank);assert r['status']==0 and r['mode']==read(archived_root/'report.json')['mode']
                    checks.append('explicit probe restored its reserved byte and original mode in all caller banks')
                    for address,count in ((0,1),(0xFFFE,64),(0x10000,64),(0x1FFC0,64),(0x1FFFF,1)):
                        original=archived[address:address+count];pattern=bytes((i*13+0xA5)&255 for i in range(count));bank=len(checks)%4
                        try:
                            write(0x4000,pattern);assert call(request(2,address,count),bank)['status']==0
                            r=call(request(1,address,count,0x4100),bank);assert r['status']==0
                            observed=link.dump(0x4100,0x4100+count-1)
                        finally:
                            # Even a failed comparison/read attempts verified restoration.
                            write(0x4000,original);assert call(request(2,address,count),bank)['status']==0
                            assert call(request(1,address,count,0x4100),bank)['status']==0
                            assert link.dump(0x4100,0x4100+count-1)==original
                        assert observed==pattern
                        checks.append(f'preserving pattern {address:05X} +{count}')
                    # Distinct simultaneous values prove bit 16 is not aliased.
                    addresses=(0x40,0x10040);patterns=(bytes([0x55])*32,bytes([0xAA])*32)
                    observed=[]
                    try:
                        for addr,pattern in zip(addresses,patterns):
                            write(0x4000,pattern);assert call(request(2,addr,32))['status']==0
                        for addr in addresses:
                            assert call(request(1,addr,32,0x4100))['status']==0;observed.append(link.dump(0x4100,0x411F))
                    finally:
                        for addr in addresses:
                            write(0x4000,archived[addr:addr+32]);assert call(request(2,addr,32))['status']==0
                    assert tuple(observed)==patterns,'Address bit 16 aliases'
                    checks.append('simultaneous distinct lower/upper-half values; originals restored')
                    # Upper CPU RAM boundary and managed/raw policy.
                    assert call(request(1,0x10000,64,0x64C0))['status']==0
                    assert link.dump(0x64C0,0x64FF)==archived[0x10000:0x10040]
                    assert call(request(2,0,1),managed=1)['status']==6
                    raw=bytes((0,0,0,0x40,1,0,0x41,1,0,0,0,0,0,0,0,0));assert call(raw,kind=0,managed=1)['status']==6
                    checks.append('maximum CPU buffer and managed write/raw-SRAM policy')
                for req in (request(1,0x20000,1),request(1,0x1FFFF,2),request(1,0,65),request(1,0,2,0x64FF)):
                    assert call(req)['status']==9
                checks.append('array/CPU range overflow rejected')
                report.update(passed=True,checks=checks)
            else:
                if a.board!='2512':
                    final=array('array-final');assert final==(archived_root/'array.bin').read_bytes()
                    report.update(array_sha256=sha(final),array_unchanged=True,mode_preserved=all(c['mode']==read(archived_root/'report.json')['mode'] for c in report['calls']))
                    assert report['mode_preserved']
                hashes=[]
                for b in range(4):
                    prompt=f'\r\nB{b}> '.encode();link.command(f'B{b}',prompt)
                    data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));assert data==banks[b]
                    (out/f'b{b}.bin').write_bytes(data);hashes.append(sha(data))
                link.command('B3');report.update(passed=True,final_flash_hashes=hashes)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            stages=a.root/'spi-stages.json';selected=read(stages) if stages.exists() else {};selected[a.stage]=out.name;stages.write_text(json.dumps(selected,indent=2)+'\n')
            print('PASS',a.board,a.stage,'SPI RAM prototype; bank/VIA preserved; no flash or crypto writes',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
