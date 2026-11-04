"""CPU/NOR tests for read-only b15 MAINT, with independent byte/CRC oracles."""
import argparse,re
from pathlib import Path
import prepare_ram_maint_ro_2609 as p
from test_b14_core import load_core
from test_b14_raw import start,feed

PROMPT=b'MAINT RO> '
core,_=load_core();core.GENERATION=p.base.GENERATION


def machine(build,cpu,port=1,banks=None,accelerate=True,fault=None):
    h=core.Machine(build,cpu,opaque=True)
    banks=banks or [(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    h.m.banks[:]=list(map(bytearray,banks));h.recovery();h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    h.ms=h.sy['core/ram-maint-ro'];sy=h.ms;original_step=h.c.step
    def step():
        c=h.c
        if accelerate and c.pc==sy['MA_CRC_BYTE']:
            address=sy['MA_CRC'];value=p.crc(bytes([c.a]),int.from_bytes(h.m.ram[address:address+2],'little'))
            h.m.ram[address:address+2]=value.to_bytes(2,'little');c.x=0;c.pc=(c.stPopWord()+1)&65535;return c
        return original_step()
    h.c.step=step
    h.m.ram[0x2000:0x6500]=bytes((n*17+3)&255 for n in range(0x4500))
    h.m.ram[0x2000:0x2009]=b'123456789'
    h.user_before=bytes(h.m.ram[0x2000:0x6500]);h.flash_before=list(map(bytes,h.m.banks));h.pcr_before=h.m.ram[0x7fec]
    h.low_before=bytes(h.m.ram[:0xe0])
    start(h,port);feed(h,port,(build/'payload'/p.BIN).read_bytes())
    if fault=='RA':h.m.ram[0x7e60]^=1
    elif fault=='worker':h.m.ram[h.w['V2W_ERASE_RAW']]^=1
    elif fault=='vectors':h.m.ram[0x7e20]^=1
    elif fault=='F':h.m.banks[3][0x7f80]^=1;h.flash_before=list(map(bytes,h.m.banks))
    elif fault=='image':h.m.ram[sy['MA_HELP_TEXT']+5]^=1
    h.run(lambda:bytes(h.m.tx if port==1 else h.m.acia_tx).endswith(PROMPT) or h.c.pc==sy['MA_HALT'])
    if fault:
        assert h.c.pc==sy['MA_HALT'] and h.m.ram[sy['MA_ERROR']]==1
    else:assert h.c.pc!=sy['MA_HALT'],'Startup guard refused qualified app/services'
    return h


def unchanged(h,buffer=True):
    assert not h.m.events and list(map(bytes,h.m.banks))==h.flash_before
    assert bytes(h.m.ram[:0xe0])==h.low_before
    assert bytes(h.m.ram[0x2000:0x5000])==h.user_before[:0x3000]
    assert bytes(h.m.ram[0x6000:0x6500])==h.user_before[0x4000:]
    assert h.m.ram[0x7fec]==h.pcr_before and h.m.bank==3
    if not buffer:assert bytes(h.m.ram[0x5000:0x6000])==h.user_before[0x3000:0x4000]


def command(h,port,line,ending=b'\r'):
    tx=h.m.tx if port==1 else h.m.acia_tx;begin=len(tx)
    h.port_command(port,line+ending,PROMPT)
    # CRLF leaves its optional LF to the shared editor; cancellation may leave
    # a following Enter as an empty line. Settle all supplied bytes rather than
    # attributing that empty-line reply to the next command in the test.
    h.run(lambda:not h.m.rx and not h.m.acia_rx and h.c.pc==h.w['V2W_GETC'])
    reply=bytes(tx[begin:]);unchanged(h);return reply


def parsed_dump(reply):
    cells={}
    for line in reply.decode('ascii').splitlines():
        match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2})+)',line)
        if match:cells.update((int(match[1],16)+n,v) for n,v in enumerate(bytes.fromhex(match[2])))
    return cells


def functional(build,cpu,port,out,passed):
    h=machine(build,cpu,port);base=p.base.read(build/'baseline.json');trace=bytearray()
    def cmd(line,ending=b'\r'):
        reply=command(h,port,line,ending);trace.extend(reply);return reply
    assert b'No write, erase' in cmd(b'?')
    grid=cmd(b'M 1');assert b'BANK 8 9 A B C D E F\r\n' in grid
    for bank in range(4):
        expected=f'B{bank} '+ ' '.join('E' if h.flash_before[bank][off:off+4096]==b'\xff'*4096 else 'U' for off in range(0,32768,4096))
        assert expected.encode()+b'\r\n' in grid
    roles=cmd(b'M');assert roles.count(b'WDC-BACKUP PROTECTED')==8 and roles.count(b'VX1-SLOT PROTECTED')==1
    wear=cmd(b'M 3')
    for n,value in enumerate(base['counts']):assert f'B{n//8}:{n%8+8:X} U {value:06X} '.encode() in wear
    assert b'SNBT SEQ=000003FC DEFAULT=S BANKS=00 UNKNOWN=FFFFFFFF\r\n' in wear
    unchanged(h,buffer=False)
    passed(cpu,port,'map-grid-sector-roles-all-32-counts-current-S-mask00-seq1020')
    for bank in range(4):
        assert b'BUFFER LOADED' in cmd(f'R {bank} 8000 800F'.encode())
        assert h.m.ram[0x5000:0x5010]==h.flash_before[bank][:16]
        cells=parsed_dump(cmd(b'D'));assert bytes(cells[n] for n in range(16))==h.flash_before[bank][:16]
    assert b'BUFFER LOADED' in cmd(b'R 3 F000 FFFF')
    assert h.m.ram[0x5000:0x6000]==h.flash_before[3][-4096:]
    cells=parsed_dump(cmd(b'D 0FF0 0FFF'));assert bytes(cells[n] for n in range(0xff0,0x1000))==h.flash_before[3][-16:]
    assert b'BUFFER LOADED' in cmd(b'R R 2000 200F')
    assert h.m.ram[0x5000:0x5010]==h.user_before[:16]
    assert b'BUFFER LOADED' in cmd(b'R R 6000 64FF')
    assert h.m.ram[0x5000:0x5500]==h.user_before[0x4000:]
    passed(cpu,port,'read-all-banks-4KiB-and-FFFF-boundary-RAM-read-buffer-display')
    assert b'BUFFER LOADED' in cmd(b'R R 2000 2008')
    assert b'CRC16=29B1\r\n' in cmd(b'K')
    assert b'CRC16=29B1\r\n' in cmd(b'K R 2000 2008')
    for bank,first,last in ((3,0xf000,0xffff),(0,0xfff0,0xffff),(1,0x8000,0xffff)):
        data=h.flash_before[bank][first-0x8000:last-0x8000+1]
        assert f'CRC16={p.crc(data):04X}\r\n'.encode() in cmd(f'K {bank} {first:04X} {last:04X}'.encode())
    passed(cpu,port,'buffer-and-range-CRC-independent-oracles-known-vector-full-bank')
    assert b'MATCH\r\n' in cmd(b'V R 2000 200F R 2000')
    assert b'MATCH\r\n' in cmd(b'V 0 8000 800F 0 8000')
    a,b=h.flash_before[0],h.flash_before[1];offset=next(n for n in range(32768) if a[n]!=b[n])
    assert f'DIFFERENT AT DEST B1:{0x8000+offset:04X}\r\n'.encode() in cmd(b'V 0 8000 FFFF 1 8000')
    if port==1:assert b'MATCH\r\n' in cmd(b'V 0 8000 FFFF 0 8000')
    for bits in (0,1,0x10,0x11):
        h.m[0x7fec]=(h.m.ram[0x7fec]&0xee)|bits;h.pcr_before=h.m.ram[0x7fec]
        assert b'MATCH\r\n' in cmd(b'V 2 FFF0 FFFF 2 FFF0')
    passed(cpu,port,'compare-match-first-difference-full-span-and-PCR-bit-preservation')
    bad=(b'',b'M 0',b'M 4',b'M 1 2',b'R',b'R 4 8000 800F',b'R 00 8000 800F',b'R 0 7FFF 8000',
         b'R R 1FFF 2000',b'R R 6400 6500',b'R R 4FF0 500F',b'R R 5000 5000',b'R R 5FFF 6000',
         b'R 0 8001 8000',b'R 0 8000 9000',b'R 0 8000 10000',b'R 0 800 800F',b'R 0 8000 800F X',
         b'D 1000',b'D 0009',b'D 0000 FFFF',b'D 0008 0001',b'K R 7F00 7FFF',b'K 3 7FFF FFFF',
         b'K 0 FFFF 8000',b'K 0 8000 FFFF X',b'V 0 8000 800F 1 FFF8',b'V 0 8000 800F R 64F8',
         b'V 0 8000 800F R 7F00',b'V 0 8000 800F 4 8000',b'W 0 8000',b'E 1 8',b'C A',b'C S',
         b'P 0000 FF',b'F 0000 00FF 00',b'N 1000 00',b'I',b'J 0',b'NAME TEST',b'X',b'G 0200',
         b'R 0 8000 800F'+b'X'*40,b'R 0 8000 800F\x03',b'R 0 8000 800F\x1b')
    for line in bad:
        old=bytes(h.m.ram[0x5000:0x6000]);assert b'REFUSED' in cmd(line),line
        assert bytes(h.m.ram[0x5000:0x6000])==old,line
    assert b'CRC16=29B1\r\n' in cmd(b'k r 2000 2008',b'\r\n')
    assert b'CRC16=29B1\r\n' in cmd(b'K R 2000 2008',b'\n')
    passed(cpu,port,'malformed-I-O-wrap-buffer-overlap-and-all-write-commands-refused',commands=len(bad))
    reply=h.port_command(port,b'Q\r',b'REC> ');trace.extend(reply)
    assert b'Boot : 6 5 4 3 2 1 0' in reply;unchanged(h)
    (out/f'simulated-MAINT-{cpu}-port{port}.txt').write_bytes(trace)
    passed(cpu,port,'Q-default-S-REC-no-flash-journal-settings-or-unowned-RAM-change')


def extra(build,cpu,passed):
    # Verify actual linked CRC opcodes before using the fast model above.
    h=machine(build,cpu,accelerate=False);sy=h.ms
    for seed in (0,0xffff,0x1234):
        for byte in (0,1,0x7f,0x80,0xff):
            h.m.ram[sy['MA_CRC']:sy['MA_CRC']+2]=seed.to_bytes(2,'little')
            h.call(sy['MA_CRC_BYTE'],byte)
            assert int.from_bytes(h.m.ram[sy['MA_CRC']:sy['MA_CRC']+2],'little')==p.crc(bytes([byte]),seed)
    passed(cpu,0,'actual-linked-CRC-opcodes-and-unaccelerated-startup-guards',comparisons=15)
    for fault in ('image','F','RA','worker','vectors'):
        h=machine(build,cpu,fault=fault);assert not h.m.events and list(map(bytes,h.m.banks))==h.flash_before
    passed(cpu,0,'bad-image-F-RA-worker-vectors-halt-before-menu',cases=5)
    original=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
    for case in ('absent','bad-body','duplicate'):
        banks=list(map(bytearray,original))
        if case=='absent':banks[3][0x4000:0x6000]=b'\xff'*8192
        elif case=='bad-body':banks[3][0x4550]^=1
        else:banks[3][0x4600:0x4700]=banks[3][0x4500:0x4600];banks[3][0x4650]^=1
        h=machine(build,cpu,banks=list(map(bytes,banks)))
        reply=command(h,1,b'M 3')
        assert b'SNBT unavailable/ambiguous' in reply and reply.count(b'??????')==32
    passed(cpu,0,'absent-damaged-conflicting-journal-never-fabricates-wear',cases=3)
    banks=list(map(bytearray,original));banks[1][:4096]=b'\xff'*4096;banks[2][-4096:]=b'\xff'*4096;banks[2][-1]=0
    h=machine(build,cpu,banks=list(map(bytes,banks)));reply=command(h,1,b'M 1')
    assert b'B1 E U U U U U U U\r\n' in reply and b'B2 U U U U U U U U\r\n' in reply
    assert b'REFUSED' in command(h,1,b'D') and b'REFUSED' in command(h,1,b'K')
    unchanged(h,buffer=False)
    passed(cpu,0,'erased-vs-programmed-last-byte-scan-and-unloaded-buffer-refusal')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cpu',choices=('65c816-e','65c02'),required=True);args=parser.parse_args()
    build,out=args.build.resolve(),args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    info=p.verify(build);cases=[]
    def passed(cpu,port,case,**details):
        cases.append(dict(passed=True,cpu=cpu,port=port,case=case,**details));p.base.save(out/'progress.json',dict(completed=len(cases),cases=cases))
        print('PASS',len(cases),cpu,port,case,details,flush=True)
    extra(build,args.cpu,passed)
    for port in (1,2):functional(build,args.cpu,port,out,passed)
    assert not p.base.ATTEMPTS
    p.base.save(out/'qualification.json',dict(passed=True,checks=len(cases),failures=0,hardware=False,serial_access=False,board_access=False,
        RAM_uploaded=False,flash_writes=0,saved_setting_writes=0,BIN_sha256=info['sha256'],build_sha256=p.base.digest(build/'build.json'),
        checker_sha256=p.base.digest(__file__),CPU=args.cpu,cases=cases))
    print('PASS total',len(cases),'RO MAINT groups',args.cpu,'no device access',flush=True)


if __name__=='__main__':main()
