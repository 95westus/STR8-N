"""Offline qualification of the exact 2512 F-only opaque round trip."""
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_b14_tools as t
ROOT=HERE.parents[1]
BUILD=ROOT/'BUILD/pr04-b14-mon-absent-r5'
SOURCE=ROOT/'output/qualification/mon-absent-2512-remove'
MESSAGE=b'\r\nOPAQUE B0:8 EXECUTED\r\n'

def probe(build):
    symbols=json.loads((build/'symbols.json').read_text());sy=symbols['core/str8n-v2-worker']
    # 65C02/816-emulation executable, no metadata/header. Entry is $8000.
    data=bytearray(bytes.fromhex('78 D8 A2 00 BD 19 80 F0 08 20')+sy['V2W_PUTC'].to_bytes(2,'little')
        +bytes.fromhex('90 03 E8 80 F3 4C')+symbols['core/str8n-v2-vectors']['V2V_RAM_RESET_ENTRY'].to_bytes(2,'little')+bytes([0xea])*5)
    assert len(data)==25
    data+=MESSAGE+b'\0';data+=bytes((i*73+41)&255 for i in range(4096-len(data)))
    assert len(data)==4096 and len(set(data))==256;return bytes(data)

def read(h,expected):
    out=h.request(t.frame(op=0,bank=0,sector=0x80))
    assert out==t.READ_READY+expected+t.crc(expected).to_bytes(2,'little')+t.READ_DONE+t.PROMPT

def scoped(before,after,count):
    assert bytes(after[3][0x2000:0x4000])==b'\xff'*8192
    for bank in range(4):
        for off in range(0,32768,4096):
            if bank==0 and off==0 or bank==3 and 0x4000<=off<0x6000:continue
            assert before[bank][off:off+4096]==after[bank][off:off+4096],(bank,off)
    old,new=t.latest_record(before),t.latest_record(after)
    assert old[7:8]+old[12:30]+old[32:64]+old[160:252]==new[7:8]+new[12:30]+new[32:64]+new[160:252]
    for b in range(4):
        for s in range(0x80,0x100,0x10):assert t.counter(new,b,s)==t.counter(old,b,s)+(count if (b,s)==(0,0x80) else 0)

def main(out):
    assert not out.exists(),'Fresh qualification output required';out.mkdir(parents=True)
    source=[(SOURCE/f'after-rescue-probe-full-flash-r2-b{n}.bin').read_bytes() for n in range(4)]
    body=probe(BUILD);(out/'opaque-probe-b0-8000.bin').write_bytes(body);original=source[0][:4096]
    cases=[]
    def passed(cpu,label,**kw):cases.append(dict(cpu=cpu,case=label,passed=True,**kw));print('PASS',cpu,label,flush=True)
    def snapshot(h,name,cpu):
        for n,bank in enumerate(h.m.banks):
            p=out/f'{name}-b{n}.bin'
            if cpu=='65c02':p.write_bytes(bytes(bank))
            else:assert p.read_bytes()==bytes(bank),'CPU postimages differ'
    for cpu in ('65c02','65c816-e'):
        h=t.patterned_machine(BUILD,cpu,banks=source,via_f=True);h.m.arm((0,0x80));read(h,original)
        assert not h.m.events;passed(cpu,'F-raw-load-installer-and-read-original-MON-absent')
        out_reply=h.request(t.frame(bank=0,sector=0x80,body=body,preimage=original),body)
        assert b'OK: verified sector' in out_reply;read(h,body);scoped(source,h.m.banks,1)
        assert [e[1:3] for e in h.m.events if e[0]=='erase']==[(0,0x8000)]
        snapshot(h,'installed',cpu);passed(cpu,'4KiB-install-readback-and-protected-sectors',payload_sha256=t.sha(body))
        before=tuple(map(bytes,h.m.banks));events=len(h.m.events)
        assert b'OK: identical; no erase' in h.request(t.frame(bank=0,sector=0x80,body=body,preimage=body),body)
        bad=bytearray(t.frame(bank=0,sector=0x80,body=body,preimage=body));bad[10]^=1;bad=t.reseal(bad)
        assert b'REFUSED: preimage CRC' in h.request(bad,body)
        assert tuple(map(bytes,h.m.banks))==before and len(h.m.events)==events
        passed(cpu,'identical-retry-and-wrong-preimage-have-no-mutation')
        h.command(b'Q\r');start=len(h.m.tx);h.m.rx.extend(b'0\r')
        h.run(lambda:len(h.m.tx)>start and bytes(h.m.tx).endswith(b'REC> '),limit=12000000)
        boot=bytes(h.m.tx[start:]);assert MESSAGE in boot and b'Boot : 6 5 4 3 2 1 0\r\n' in boot and b'STR8-N' not in boot
        assert tuple(map(bytes,h.m.banks))==before;passed(cpu,'F-bank0-launch-probe-and-software-return-to-recovery')
        h.load(via_f=True);h.m.arm((0,0x80))
        assert b'OK: verified sector' in h.request(t.frame(bank=0,sector=0x80,body=original,preimage=body),original)
        read(h,original);scoped(source,h.m.banks,2);assert bytes(h.m.banks[0])==source[0]
        snapshot(h,'restored',cpu);passed(cpu,'original-sector-restored-MON-still-absent-and-wear-plus2')
    report=dict(passed=True,hardware=False,serial_access=False,checks=len(cases),failures=0,cases=cases,
        build=str(BUILD),source_run=str(SOURCE),source_bank_sha256=list(map(t.sha,source)),
        source_completion_sha256=t.sha((SOURCE/'state.json').read_bytes()),
        F_sha256=t.sha(source[3][-4096:]),target=dict(bank=0,sector=0x80,bytes=4096,entry=0x8000),
        probe_sha256=t.sha(body),installer_sha256=t.sha((BUILD/'payload/ram-installer-offline.bin').read_bytes()),
        service_loader_sha256=t.sha((BUILD/'payload/mon-service-load.bin').read_bytes()),
        installed_bank_sha256=[t.sha((out/f'installed-b{n}.bin').read_bytes()) for n in range(4)],
        restored_bank_sha256=[t.sha((out/f'restored-b{n}.bin').read_bytes()) for n in range(4)],
        checker_sha256=t.sha(Path(__file__).read_bytes()),
        limitations=['Existing OIP1 interruption/protection suites retained; this round trip adds no physical power-loss test',
                     'Opaque executable is a temporary probe; original B0:8 is restored'])
    t.base.save(out/'opaque-live-model-tests.json',report)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
