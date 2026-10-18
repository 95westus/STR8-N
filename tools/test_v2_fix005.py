"""F-only bootstrap, explicit journal provisioning, refusal and power cuts."""
import os,json,hashlib,copy
import build_v2_recovery as fw
from beta4_migration import default_config,metadata,crc
fw.OUT=fw.ROOT/os.environ.get('STR8_RTC_BUILD','BUILD/v2-fix005');fw.SOURCE=fw.OUT/'source'
META=json.loads((fw.OUT/'build.json').read_text());fw.VERSION=META['version']
import test_v2_recovery as model

OUT=fw.OUT;FIXED=(OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
UTILITY=(OUT/'bootstrap/bootstrap-journal.bin').read_bytes()
INITIAL=metadata(default_config(),[0]*32,1)

def banks():
    b=[bytearray(b'\xff'*32768) for _ in range(4)];b[3][0x7000:]=FIXED;return b

def boot(b,select=b'\x1b'):
    m=model.Memory(b);c=model.MPU(memory=m,pc=0xF004);m.cpu=c
    model.run(c,lambda:c.pc==META['boot']['BOOT_STARTUP_DOTS'],5000000)
    m.rx.extend(select);model.run(c,lambda:model.waiting(c),5000000);return c,m

def provision(c,answer=b'Y\r'):
    m=c.memory;m.ram[0x2000:0x2000+len(UTILITY)]=UTILITY;c.pc=0x2000
    return model.command(c,answer,6000000)

def preserved(m,b,allowed=()):
    for bank in range(4):
        for i in range(32768):
            if not any(bank==x and lo<=i<hi for x,lo,hi in allowed):assert m.banks[bank][i]==b[bank][i],(bank,hex(i))
    assert m.banks[3][0x7000:]==FIXED

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    # Both independent bootstrap destinations, with only F present.
    fixtures={}
    for page,key in ((0xA0,b'A'),(0xB0,b'B')):
        initial=banks();c,m=boot(initial);assert b'REC> ' in m.tx and not m.events
        image=(OUT/f'str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
        text=model.update(c,page,image);assert b'COMMITTED' in text and m.ram[model.EQ['active']]==page,text[-500:]
        assert all(e[0]=='program' and e[1]==3 for e in m.events)
        assert m.events[-1][2]==(page<<8)+31 and m.events[-1][3]==0
        assert bytes(m.banks[3][0x4000:0x6000])==b'\xff'*8192
        preserved(m,initial,((3,(page<<8)-0x8000,(page<<8)-0x7000),))
        assert b'JOURNAL INVALID' in model.command(c,b'W\r')
        fixtures[page]=[bytes(v) for v in m.banks]
        # Exercise the documented S19 load/G entry, not only a direct fixture.
        source=(OUT/'bootstrap/bootstrap-journal.s19').read_bytes().replace(b'\n',b'\r\n')
        model.command(c,b'L\r'+source,6000000)
        assert bytes(m.ram[0x2000:0x2000+len(UTILITY)])==UTILITY
        text=model.command(c,b'G 2000\rY\r',6000000)
        assert b'Journal initialized' in text,text
        assert bytes(m.banks[3][0x4000:0x4080])==INITIAL
        assert model.counts(model.latest(m.banks))==[0]*32
        assert b'B3:A 000000' in model.command(c,b'W\r')
        assert b'B3> ' in model.command(c,b'D 0200 020F\r')
        assert b'B3> ' in model.command(c,b'J3\r',6000000)
        preserved(m,fixtures[page],((3,0x4000,0x4080),))
        (OUT/f'f-only-{key.decode().lower()}-preview.txt').write_bytes(text)
    passed('F alone bootstraps A or B without erase; commit last; actual L/G provisions known journal; W/D/J3 work; F and unrelated flash intact')
    # Guard every relevant C/D boundary, including unknown formats/torn data.
    for where in (0x4000,0x407F,0x4FFF,0x5000,0x5FFF):
        b=banks();b[3][where]=0;c,m=boot(b);image=(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes()
        text=model.update(c,0xA0,image)
        assert b'REFUSED' in text and not m.events,(hex(where),text[-300:],m.events[:2])
        preserved(m,b)
    for mode in ('crc','cookie','cancel','occupied'):
        b=banks();c,m=boot(b);image=bytearray((OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes())
        if mode=='crc':image[500]^=1
        elif mode=='cookie':
            image[20]^=1;image[18:20]=crc(image[:18]+image[32:]).to_bytes(2,'little')
        elif mode=='occupied':m.banks[3][0x2100]=image[0x100]^0x80;b=[bytes(v) for v in m.banks]
        if mode=='cancel':text=model.command(c,b'U A\rN\r')
        else:text=model.update(c,0xA0,image)
        assert b'REFUSED' in text and not m.events,(mode,text)
        preserved(m,b)
    passed('unknown/torn C/D at five boundaries, corrupt/incompatible upload, cancellation and differing occupied target refuse with zero writes')
    # Incomplete binary transfers cause no mutation, and physical cold reset
    # recovers the F console. USB raw binary intentionally has no in-band abort.
    image=(OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    for length in (0,1,31,128,2048,4095):
        c,m=boot(banks());m.rx.extend(b'U A\rY\r'+image[:length])
        model.run(c,lambda:c.pc==META['boot']['BOOT_RECEIVE'] and not m.rx,3000000)
        assert not m.events
        _,r=boot(m.banks);assert r.tx.endswith(b'REC> ')
    passed('six truncated uploads stay uncommitted and cold-reset back to F recovery')
    # Representative slot cuts span header/body/last-body/final commit.
    c,m=boot(banks());model.update(c,0xA0,image);writes=len(m.events)
    cuts=sorted(set((1,2,18,31,32,127,writes//4,writes//2,writes-2,writes-1,writes)))
    for cut in cuts:
        c,m=boot(banks());m.cut_after=cut
        try:model.update(c,0xA0,image)
        except model.PowerCut:pass
        else:raise AssertionError(('slot cut missed',cut,writes))
        if cut==writes:
            _,r=boot(m.banks,b'A');assert r.ram[model.EQ['active']]==0xA0;continue
        c,r=boot(m.banks);assert r.tx.endswith(b'REC> ')
        assert b'COMMITTED' in model.update(c,0xA0,image)
        assert not any(e[0]=='erase' for e in r.events)
        assert bytes(r.banks[3][0x2000:0x3000])==image
    passed(f'{len(cuts)} slot power cuts resume identical bytes with no erase/reprogram; final commit alone enables boot')
    base=fixtures[0xA0];c,m=boot(base,b'A');template=copy.deepcopy(c)
    assert b'Canceled' in provision(c,b'N\r') and not m.events
    c=copy.deepcopy(template);m=c.memory;assert b'Journal initialized' in provision(c)
    total=len(m.events);assert m.events[-1][2]==0xC07F and total>100
    assert all(e[0]=='program' and e[1]==3 and 0xC000<=e[2]<=0xC07F for e in m.events)
    count=len(m.events);assert b'Journal initialized' in provision(c) and len(m.events)==count
    for cut in range(1,total+1):
        c=copy.deepcopy(template);m=c.memory;m.cut_after=cut
        try:provision(c)
        except model.PowerCut:pass
        else:raise AssertionError(('journal cut missed',cut,total))
        # A true reset reinstalls RAM workers before the same utility resumes.
        c,r=boot(m.banks,b'A');assert b'Journal initialized' in provision(c)
        assert bytes(r.banks[3][0x4000:0x4080])==INITIAL
        assert model.counts(model.latest(r.banks))==[0]*32
        assert not any(e[0]=='erase' for e in r.events)
        preserved(r,base,((3,0x4000,0x4080),))
    passed(f'all {total} journal byte-program power cuts resume from exact prefix; body verified before commit; retry is idempotent and erase-free')
    for where,value in ((0x4000,0),(0x4001,ord('C')),(0x407A,0),(0x4080,0),(0x5FFF,0)):
        b=[bytearray(v) for v in base];b[3][where]=value;c,m=boot(b,b'A')
        assert b'REFUSED' in provision(c) and not m.events;preserved(m,b)
    c,m=boot(base,b'A');m.banks[3][META['boot']['BOOT_COMPAT_DATA']-0x8000]^=1
    before=[bytes(v) for v in m.banks];assert b'REFUSED' in provision(c) and not m.events
    assert [bytes(v) for v in m.banks]==before
    passed('RAM utility refuses foreign core, non-prefix record, reserved bytes and nonblank C/D tail without mutation')
    # Once provisioned, the ordinary update still accounts for its erase first.
    c,m=boot(base,b'A');provision(c);start=len(m.events)
    text=model.update(c,0xB0,model.newer(0xB0,META['generation']+1));assert b'COMMITTED' in text,text[-300:]
    events=m.events[start:];erases=[i for i,e in enumerate(events) if e[0]=='erase'];assert len(erases)==1
    assert events[erases[0]][2]==0xB000 and any(e[2]==0xC0FF for e in events[:erases[0]])
    assert model.counts(model.latest(m.banks))[27]==1
    assert m.banks[3][0x7000:]==FIXED
    passed('after explicit provisioning, normal inactive-slot update logs and commits erase attempt before its single erase')
    report=dict(passed=True,checks=checks,artifacts=META['artifacts'],bootstrap_utility_sha256=META['bootstrap_utility_sha256'],
        slot_cut_points=cuts,journal_cut_points=total,board_access=False,boards_flashed=False)
    (OUT/'f-only-bootstrap-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
