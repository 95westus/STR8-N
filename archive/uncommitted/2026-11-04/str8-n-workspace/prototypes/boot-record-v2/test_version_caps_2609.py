"""CPU/NOR, metadata, context and compatibility tests; never accesses a board."""
import argparse,json,types,shutil
from pathlib import Path
import prepare_version_caps_2609 as p
from test_b14_core import load_core
from test_b14_raw import start,feed

REC=b'REC> '
MENU=b'RAM MINSTALL ? V W I Q> '


def machine(build,cpu='65c816-e',banks=None,slot='A',accelerate=True):
    core,_=load_core();core.GENERATION=p.b.GENERATION
    h=core.Machine(build,cpu,opaque=True)
    banks=banks or [(build/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    h.m.banks[:]=list(map(bytearray,banks));h.m.bank=3;h.m.tx.clear();h.m.rx.clear();h.c.pc=0xf004;h.c.p=0x34;h.c.sp=255
    if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
    h.run(lambda:bytes(h.m.tx).endswith(REC))
    if slot:
        h.port_command(1,b'C1\r');h.port_command(1,slot.encode()+b'\r',b'B3> ')
    es=h.sy['extension'];original=h.c.step
    def step():
        c,m=h.c,h.m
        if accelerate and c.pc==es['VX_CRC_BYTE'] and m.bank==3:
            value=p.crc(bytes([c.a]),int.from_bytes(m.ram[0xd4:0xd6],'little'))
            m.ram[0xd4:0xd6]=value.to_bytes(2,'little');c.x=0;c.pc=(c.stPopWord()+1)&65535;return c
        return original()
    h.c.step=step;h.original_step=original
    return h


def call(h,entry,a=0,x=0,y=0):
    c=h.c;c.pc=entry;c.a=a;c.x=x;c.y=y;c.sp=255;c.p=0x34;c.stPushWord(0x1ff)
    h.run(lambda:c.pc==0x200)
    return bool(c.p&1),c.a,c.x,c.y


def query(h,running=0xa0,buffer=0x6000,capacity=224,entry=0xe004):
    h.m.ram[buffer]=capacity
    before=bytes(h.m.ram[0xd0:0xe0]);sp=255
    value=call(h,entry,running,buffer&255,buffer>>8)
    assert bytes(h.m.ram[0xd0:0xe0])==before,'Query changed caller ZP'
    assert h.c.sp==sp and h.c.p&4 and not h.c.p&8
    return value,bytes(h.m.ram[buffer:buffer+224])


def reseal_mon(slot):
    slot=bytearray(slot);slot[18:20]=p.crc(slot[:18]+slot[32:]).to_bytes(2,'little');return slot


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    info=p.verify(build);checks=[]
    source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)];expected=[(build/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    def passed(case,**details):
        checks.append(dict(passed=True,case=case,**details));p.save(out/'progress.json',dict(checks=checks,completed=len(checks)))
        print('PASS',len(checks),case,flush=True)
    for cpu in ('65c816-e','65c02'):
        h=machine(build,cpu,accelerate=False)
        for seed in (0,65535,0x1234):
            for byte in (0,1,127,128,255):
                h.m.ram[0xd4:0xd6]=seed.to_bytes(2,'little');call(h,h.sy['extension']['VX_CRC_BYTE'],byte)
                assert int.from_bytes(h.m.ram[0xd4:0xd6],'little')==p.crc(bytes([byte]),seed)
        passed('linked-CRC-opcodes-'+cpu,comparisons=15)
        for slot,page in (('A',0xa0),('B',0xb0)):
            h=machine(build,cpu,slot=slot)
            before=list(map(bytes,h.m.banks));application=bytes(h.m.ram[0x200:0x6500])
            value,data=query(h,page);assert value==(True,0,0,0x60)
            assert data[:4]==b'VI\x01\xe0' and data[4]==0x17 and data[6]==(0x16 if cpu=='65c816-e' else 2)
            assert data[8]==page and data[9:12]==b'\x03\x03\x03'
            assert data[24:56]==bytes.fromhex(p.b.F_SHA)
            assert data[56:88]==expected[3][0x2fdc:0x2ffc] and data[88:120]==expected[3][0x3fdc:0x3ffc]
            assert bytes(h.m.ram[0x200:0x6000])==application[:0x5e00]
            assert call(h,0x7e85)[:4]==(True,1,0x17,4)
            board=call(h,0x7e88);assert board[0:3]==(True,1,0x16 if cpu=='65c816-e' else 2)
            discover=call(h,(0xa000 if slot=='A' else 0xb000)+0xae);assert discover==(True,1,0,0xe0)
            # Return to command loop, then exercise the actual VERSION consumer.
            h.c.pc=h.sy[f'core/monitor-{page:02x}']['V2_PROMPT'];h.c.sp=255;h.run(lambda:h.c.pc==h.w['V2W_GETC'])
            version=h.port_command(1,b'VERSION\r',b'B3> ')
            assert b'STR8-N VERSION / VX1' in version and ('Running MON: '+slot).encode() in version
            for raw in (bytes.fromhex(p.b.F_SHA),expected[3][0x2fdc:0x2ffc],expected[3][0x3fdc:0x3ffc]):assert raw.hex().upper().encode() in version
            caps=h.port_command(1,b'CAPS\r',b'B3> ');assert b'legacy CAPS=01/17' in caps
            assert b' Y?' not in h.port_command(1,b'S\r',b'B3> ')
            assert not h.m.events and list(map(bytes,h.m.banks))==before
            (out/f'{cpu}-{slot}-VERSION.txt').write_bytes(version);(out/f'{cpu}-{slot}-CAPS.txt').write_bytes(caps)
            passed('VERSION-CAPS-identities-legacy-queries-'+cpu+'-'+slot)
            h.port_command(1,b'J3\r',b'S=Recovery  A/B=Monitor  0-3=Bank\r\n');h.port_command(1,b'S',REC)
            assert not h.m.events;passed('MON-to-REC-'+cpu+'-'+slot)
        h=machine(build,cpu)
        for buffer,capacity,run in ((0x6000,223,0),(0x100,224,0),(0x64f0,224,0),(0x6500,224,0),(0x6701,224,0),(0x6000,224,3)):
            h.m.ram[buffer:buffer+224]=b'\xa5'*224;h.m.ram[buffer]=capacity;before=bytes(h.m.ram[buffer:buffer+224])
            value,data=query(h,run,buffer,capacity);assert not value[0] and value[1]==0x82
            if buffer<0x6700:assert bytes(h.m.ram[buffer:buffer+224])==before
        passed('bad-capacity-buffer-and-request-'+cpu,cases=6)
        client=(build/'payload/version-caps-query-RAM.bin').read_bytes();h.m.ram[0x200:0x200+len(client)]=client
        for bank,bits in enumerate((0xcc,0xce,0xec,0xee)):
            h.m[0x7fec]=(h.m.ram[0x7fec]&0x11)|bits;before=h.m.ram[0x7fec]
            value,data=query(h,0,0x6000,224,0x203)
            assert value[0] and data[8]==0 and h.m.bank==bank and h.m.ram[0x7fec]==before
        passed('public-RAM-client-all-banks-restores-PCR-'+cpu,cases=4)
    # Missing/malformed optional extension must not stop core MON or recovery.
    for case,offset,value in [('missing',None,None),('format',2,2),('length',3,63),('extent',17,0x20),('ABI',13,2),('flags',14,2),('uncommitted',31,255),('entry-header',5,0),('entry-footer',5,0xc0),('CRC',0x201,0)]:
        banks=list(map(bytearray,expected))
        if offset is None:banks[3][0x6000:0x7000]=b'\xff'*4096
        else:
            banks[3][0x6000+offset]=value
            if case=='entry-footer':banks[3][0x6006]=0xef
            if case!='CRC':banks[3][0x6ffe:0x7000]=p.crc(banks[3][0x6000:0x6ffe]).to_bytes(2,'big')
        h=machine(build,banks=list(map(bytes,banks)))
        out_text=h.port_command(1,b'VERSION\r',b'B3> ');assert b'VX1 unavailable' in out_text and not h.m.events
        h.port_command(1,b'D 7D30 7D30\r',b'B3> ')
        client=(build/'payload/version-caps-query-RAM.bin').read_bytes();h.m.ram[0x200:0x200+len(client)]=client
        value,data=query(h,0,0x6000,224,0x203);assert not value[0]
        passed('optional-extension-refusal-'+case)
    # Independent MON identities: absent/corrupt/older MON does not hide F.
    for case in ('old-B','bad-B-CRC','bad-B-metadata','different-B-generation','invalid-B-entry'):
        banks=list(map(bytearray,expected))
        if case=='old-B':banks[3][0x3000:0x4000]=source[3][0x3000:0x4000]
        if case=='bad-B-CRC':banks[3][0x3100]^=1
        if case=='bad-B-metadata':banks[3][0x3fc5]=63;banks[3][0x3000:0x4000]=reseal_mon(banks[3][0x3000:0x4000])
        if case=='different-B-generation':
            banks[3][0x3008:0x300c]=(0x80000010).to_bytes(4,'little');banks[3][0x3fc8:0x3fcc]=(0x80000010).to_bytes(4,'little');banks[3][0x3000:0x4000]=reseal_mon(banks[3][0x3000:0x4000])
        if case=='invalid-B-entry':banks[3][0x300e:0x3010]=b'\0\x80';banks[3][0x3000:0x4000]=reseal_mon(banks[3][0x3000:0x4000])
        h=machine(build,banks=list(map(bytes,banks)));value,data=query(h)
        assert value[0] and data[9]==3 and data[24:56]==bytes.fromhex(p.b.F_SHA)
        if case in ('old-B','bad-B-metadata'):assert data[11]==1 and data[88:120]==b'\xff'*32
        elif case in ('bad-B-CRC','invalid-B-entry'):assert data[11]==0
        else:assert int.from_bytes(data[20:24],'little')==0x80000010
        passed('independent-identities-'+case)
    h=machine(build);h.m.banks[3][0x7001]^=1;h.m.ram[0x6000:0x60e0]=b'\xa5'*224
    value,data=query(h);assert not value[0] and value[1]==0x81 and data[1:]==b'\xa5'*223
    passed('unknown-F-refuses-before-publishing-identity')
    h=machine(build);h.m.ram[0x7e60]=0;value,data=query(h);assert not value[0] and value[1]==0x81
    passed('invalid-legacy-RA-refused')
    for name,kind,offset in [('version-caps-e000.bin','EXT',0x6000),('monitor-a0-version-caps.bin','MON',0x2000),('monitor-b0-version-caps.bin','MON',0x3000)]:
        raw=(build/'payload'/name).read_bytes();assert raw[0xfdc:0xffc]==p.normalized(raw,kind)
        changed=bytearray(raw);changed[0x150]^=1;assert p.normalized(changed,kind)!=raw[0xfdc:0xffc]
    passed('normalized-SHA256-identities-bound-to-built-bytes',components=3)
    # Direct query writes only its caller buffer, documented scratch and stack.
    h=machine(build);writes=[];base_class=h.m.__class__
    class Watched(base_class):
        def __setitem__(self,address,value):
            if isinstance(address,int):writes.append(address)
            return super().__setitem__(address,value)
    h.m.__class__=Watched;value,data=query(h)
    assert value[0] and all(0xd0<=a<0xe0 or 0x100<=a<0x200 or 0x6000<=a<0x60e0 or 0x6700<=a<0x6800 for a in writes)
    passed('structured-query-no-I-O-flash-or-unowned-RAM-writes')
    p.save(out/'proof.json',dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,checks=len(checks),cases=checks,
        build_plan_sha256=p.b.digest(build/'plan.json'),test_source_sha256=p.b.digest(__file__),
        limits=['ROM-locator VX1 candidate, not F-published resident discovery','CPU simulation only; no board or ACIA qualification']))
    print('PASS',len(checks),'VERSION/capability groups; no hardware access',flush=True)


if __name__=='__main__':main()
