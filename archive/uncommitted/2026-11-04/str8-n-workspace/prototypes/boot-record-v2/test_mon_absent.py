"""Linked 65C02/816 emulation and NOR scope proof; no physical device I/O."""
import argparse,json,sys,binascii
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_b14_tools as t
from test_b14_core import fast_idle
base=t.base
crc=base.crc
KIT=b'MON KIT X=eraseAB T=restoreAB Q=boot> '
SVC=b'RAM SERVICE> '

class Memory(t.InstallerMemory):
    def mutated(self,kind,address,value):
        journal=self.bank==3 and 0xc000<=address<0xe000
        assert journal or self.bank==3 and 0xa000<=address<0xc000,('scope',kind,self.bank,address)
        if journal and address&255==255 and kind=='program':
            self.newest=t.latest_record(self.banks)
        if kind=='erase':
            self.newest=t.latest_record(self.banks)
            sector=address>>8
            n=t.counter(self.newest,3,sector)
            old=t.counter(self.initial_counts,3,sector)
            previous=sum(e[0]=='erase' and e[2]==address for e in self.events)
            assert n>=old+previous+1,('unreserved erase',hex(address),n,old)
        self.events.append((kind,self.bank,address,value))
        if self.cut_after is not None and len(self.events)>=self.cut_after:raise t.PowerLoss()

def fresh(build,cpu,banks):
    h=t.InstallerMachine(build,cpu,banks=banks)
    h.accelerate_local_crc=False # This RAM tool has no OIP1 CRC routine.
    old=h.m;m=Memory(banks,dual=True);m.ram[:]=old.ram;m.bank=3;m.cpu=h.c
    m.initial_counts=t.latest_record(m.banks);m.newest=m.initial_counts;h.m=h.c.memory=m
    return h

def load(h,build,name,prompt,via_f=True):
    data=(build/'payload'/name).read_bytes()
    if via_f:
        h.recovery();h.command(b'C1\r');h.command(b'L\r',b'SEND BIN\r\n');h.command(data,prompt)
    else:
        h.m.ram[0x200:0x200+len(data)]=data;h.c.pc=0x200;h.run(lambda:bytes(h.m.tx).endswith(prompt))
    return data

def preserved(before,after,journal=True):
    for bank in range(4):
        for off in range(0,32768,4096):
            if bank==3 and (0x2000<=off<0x4000 or journal and 0x4000<=off<0x6000):continue
            assert before[bank][off:off+4096]==after[bank][off:off+4096],('unrelated flash',bank,hex(off))
    a,b=t.latest_record(before),t.latest_record(after)
    assert a[7:8]+a[12:30]+a[32:64]+a[160:252]==b[7:8]+b[12:30]+b[32:64]+b[160:252], 'Config/history changed'

def svc_read(h,command,n):
    start=len(h.m.tx);h.m.rx.extend(command)
    h.run(lambda:len(h.m.tx)>=start+n+2+len(SVC) and bytes(h.m.tx).endswith(SVC))
    out=bytes(h.m.tx[start:]);assert len(out)==n+2+len(SVC)
    assert crc(out[:n])==int.from_bytes(out[n:n+2],'little');return out[:n]

def main(build):
    info=json.loads((build/'mon-absent-build.json').read_text());plan=Path(info['source_plan'])
    original=[(plan/f'expected-b{i}.bin').read_bytes() for i in range(4)]
    cases=[];failed=[]
    def passed(cpu,label,**kw):cases.append(dict(cpu=cpu,case=label,passed=True,**kw));print('PASS',cpu,label,flush=True)
    for cpu in ('65c02','65c816'):
        h=fresh(build,cpu,original);owner=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0])
        load(h,build,'mon-kit.bin',KIT);h.command(b'X',b'REC> ')
        assert h.m.banks[3][0x2000:0x4000]==b'\xff'*8192
        assert [e[2] for e in h.m.events if e[0]=='erase']==[0xa000,0xb000]
        destroyed=[bytes(b) for b in h.m.banks];preserved(original,destroyed)
        for n,bank in enumerate(destroyed):
            path=build/f'mon-absent-expected-b{n}.bin'
            if cpu=='65c02':path.write_bytes(bank)
            else:assert path.read_bytes()==bank,'CPU models disagree on exact postimage'
        initial,latest=t.latest_record(original),t.latest_record(destroyed)
        for sector in (0xa0,0xb0):assert t.counter(latest,3,sector)==t.counter(initial,3,sector)+1
        passed(cpu,'exact-AB-erases-and-wear-only-boot-to-F',mutations=len(h.m.events))
        for cmd in (b'A\r',b'B\r'):
            out=h.command(cmd);assert b'Recovery L A/B' in out and b'STR8-N' not in out
        passed(cpu,'absent-A-B-refused-in-F')
        erased_events=list(h.m.events)
        # F-only raw load of the restoration kit, complete erase/program/readback.
        load(h,build,'mon-kit.bin',KIT);start=len(h.m.tx);h.m.rx.extend(b'T')
        h.run(lambda:len(h.m.tx)>start and bytes(h.m.tx).endswith(b'\r\nB3> '),limit=12000000)
        for off in (0x2000,0x3000):assert bytes(h.m.banks[3][off:off+4096])==original[3][off:off+4096]
        preserved(original,h.m.banks)
        restore_events=h.m.events[len(erased_events):]
        for sector in (0xa000,0xb000):
            ev=[e for e in restore_events if e[2]&0xf000==sector]
            assert ev[0][0]=='erase' and ev[-1][2]==sector+31 and ev[-1][3]==0
        passed(cpu,'F-only-raw-load-restore-commit-last-boot-MON-B',mutations=len(restore_events))
        # F-only service can inspect every bank and restore owner RAM in place.
        h=fresh(build,cpu,destroyed);load(h,build,'mon-service-load.bin',SVC)
        for n in range(4):assert svc_read(h,b'F'+bytes([n]),32768)==destroyed[n]
        passed(cpu,'F-only-service-full-flash-binary-CRC-readback')
        h.command(b'W'+owner+crc(owner).to_bytes(2,'little'),SVC)
        for _ in range(2):assert svc_read(h,b'M',0x6300)==owner
        assert svc_read(h,b'Z',0xe0)==zp
        h.command(b'Q',b'REC> ')
        assert bytes(h.m.ram[0x200:0x6500])==owner and bytes(h.m.ram[:0xe0])==zp and h.m.ram[0x7d02]==3
        assert not h.m.events
        passed(cpu,'owner-RAM-ZP-restored-and-BOTH-F-recovery')
        # Every flash bank except B3 and changed MON preimages fail before mutation.
        changed=[bytearray(b) for b in original];changed[3][0x2010]^=1
        h=fresh(build,cpu,changed);load(h,build,'mon-kit.bin',KIT);out=h.command(b'X',b'REC> ')
        assert b'REFUSED/FAILED' in out and not h.m.events
        passed(cpu,'unexpected-MON-preimage-refuses-before-any-write')
        h=fresh(build,cpu,original);data=bytearray((build/'payload/mon-kit.bin').read_bytes());data[-3]^=1
        h.recovery();h.command(b'C1\r');h.command(b'L\r',b'SEND BIN\r\n');out=h.command(data,b'REC> ')
        assert b'REFUSED/FAILED' in out and not h.m.events
        passed(cpu,'corrupt-raw-tool-self-check-refuses-before-any-write')
        # Interrupt at journal commit, target erase, early/late target programming,
        # MON commit. Replay exact observed operation prefixes to model power loss.
        events=erased_events+restore_events
        cuts={i+1 for i,e in enumerate(events) if e[0]=='erase' or e[2]&255==255 and 0xc000<=e[2]<0xe000
              or e[2] in (0xa000,0xb000,0xa01f,0xb01f,0xafff,0xbfff)}
        cuts.update((1,len(erased_events),len(events)))
        for cut in sorted(cuts):
            banks=[bytearray(b) for b in original]
            for kind,bank,address,value in events[:cut]:
                if kind=='erase':banks[bank][(address&0xf000)-0x8000:(address&0xf000)-0x7000]=b'\xff'*4096
                else:banks[bank][address-0x8000]=value
            preserved(original,banks)
            q=fresh(build,cpu,banks);q.recovery();load(q,build,'mon-kit.bin',KIT)
            # Recovery can always relaunch the kit. Also actually finish a torn
            # restoration at representative target erase/program/commit cuts.
            if cut>len(erased_events) and events[cut-1][2] in (0xa000,0xb000,0xa01f,0xb01f):
                start=len(q.m.tx);q.m.rx.extend(b'T')
                q.run(lambda:len(q.m.tx)>start and bytes(q.m.tx).endswith(b'\r\nB3> '),limit=12000000)
                assert bytes(q.m.banks[3][0x2000:0x4000])==original[3][0x2000:0x4000]
        passed(cpu,'interruption-prefixes-F-and-rescue-preserved',prefixes=len(cuts))
    report=dict(passed=True,hardware=False,serial_access=False,checks=len(cases),failures=0,cases=cases,
        expected_bank_sha256=[base.sha((build/f'mon-absent-expected-b{n}.bin').read_bytes()) for n in range(4)],
        build_report_sha256=base.sha((build/'mon-absent-build.json').read_bytes()),checker_sha256=base.sha(Path(__file__).read_bytes()),
        limitations=['NOR/CPU model power-loss prefixes; no physical power interruption',
                     'Raw F transfer has no CRC/length; kit checks its own CRC before mutations',
                     'External NMI/electrical brownout not qualified'])
    base.save(build/'mon-absent-tests.json',report)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);main(p.parse_args().build.resolve())
