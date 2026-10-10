"""Execute unflashed storage candidate; no serial ports or board access."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-storage')
import json,hashlib,sys
from test_v2_sram_store import k,OUT,boot,console,formatted,run_api,request,fast_transfer

def cmd(cpu,m,line):
    if '--trace' not in sys.argv:return console(cpu,m,line,limit=40000000)
    s=json.loads((OUT/'maint/manifest.json').read_text())['symbols'];watch={s[n]:n for n in ('X_FAIL','X_BAD','X_FIND_DONE','X_RESULT','X_FROM_SRAM')}
    start=len(m.tx);m.rx.extend(line)
    for _ in range(40000000):
        if k.model.waiting(cpu):return bytes(m.tx[start:])
        if cpu.pc in watch:print('TRACE',watch[cpu.pc],hex(cpu.a),m.ram[0x6300:0x6338].hex(),m.ram[0x6380:0x6393].hex(),flush=True)
        if cpu.pc==s['X_FIND_ID'] and m.ram[0x638C:0x638E]==b'\0\xD0':print('FIND',cpu.x,m.ram[0x7C80:0x7C90].hex(),m.ram[s['X_RECORD_ID']:s['X_RECORD_ID']+4].hex(),m.bank,flush=True)
        if getattr(m,'fast',False) and cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    raise AssertionError(('trace timeout',hex(cpu.pc)))

def service(cpu,m,op,limit=12000000):
    cpu.a=op;sp=cpu.sp;cpu.stPushWord(0x1ff);cpu.pc=0xEF09
    for _ in range(limit):
        if cpu.pc==0x200:break
        if getattr(m,'fast',False) and cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    else:raise AssertionError(('service timeout',hex(cpu.pc)))
    assert cpu.sp==sp
    return cpu.a,cpu.x,bool(cpu.p&cpu.CARRY)

def general(passed):
    cpu,m=boot();pattern=bytes((i*17+i//256)&255 for i in range(0x6300));m.ram[0x200:0x6500]=pattern
    before=([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
    out=cmd(cpu,m,b'T 2\r');assert b'SRAM loader unav' not in out,out[-800:]
    out=cmd(cpu,m,b'R SRAM\rQ\r')
    assert b'SRAM 1.2' in out,out[-400:]
    assert m.ram[0x200:0x6500]==pattern
    assert ([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))==before
    passed('R SRAM loads directly into staging and preserves the entire $0200-$64FF application and all storage')
    out=cmd(cpu,m,b'R 2 SRAM\rQ\r');assert b'SRAM 1.2' in out and m.ram[0x200:0x6500]==pattern
    out=cmd(cpu,m,b'R SRAM L\r');assert b'SRAM 1.2' not in out and m.ram[0x200:0x6500]==pattern
    m.banks[2][0x2200]^=1;out=cmd(cpu,m,b'R SRAM\r');assert b'SRAM loader unavailable' in out and m.ram[0x200:0x6500]==pattern
    passed('explicit bank alias preserves RAM; unsafe load-only refuses; corrupt sealed manager refuses before execution')
    cpu,m=boot();m.ram[0x7D2C]=2;m.ram[0x7D2D:0x7D2F]=(56).to_bytes(2,'little')
    assert service(cpu,m,5)==(0,0x80,True)
    # An FF-filled payload is occupied even though every data byte is erased.
    record=b'SR\x01\x3F\x00\x02\x00\x01'+b'FILL'.ljust(16,b'\0')+b'\xff'*256
    m.banks[2][:len(record)]=record
    assert service(cpu,m,5)==(24,0x81,True)
    m.banks[2][:0x4800]=b'\0'*0x4800
    asset_end=(k.REPORT['status_asset_address']+k.REPORT['status_asset_bytes'])>>8
    assert service(cpu,m,5)==(0,asset_end,True)
    m.ram[0x7D2C]=3;assert not service(cpu,m,5)[2]
    m.ram[0x7D2C]=0;m.banks[0][0x7FFC:0x7FFE]=b'\x00\xF0';assert not service(cpu,m,5)[2]
    passed('first-fit skips complete record payloads and the entire sealed formatter asset; refuses B3 and bootable B0')
    cpu,m=boot();m.ram[0x200:0x220]=bytes(range(32))
    out=cmd(cpu,m,b'S 2 AUTO 0200 021F TINY\r');assert b'SAVE B02:8000' in out,out
    assert m.banks[2][:24]==b'SR\x01\x3F\x00\x02\x20\x00'+b'TINY'.ljust(16,b'\0')
    assert m.banks[2][24:56]==bytes(range(32))
    m.ram[0x200:0x220]=b'\xA5'*32;out=cmd(cpu,m,b'R 2 TINY L\r');assert m.ram[0x200:0x220]==bytes(range(32)),out
    passed('native S bank AUTO start end label selects, displays and saves an ordinary restorable SR record')
    from test_v2_status import fresh,boot as status_boot
    cpu,m=fresh(off=True);status_boot(cpu);area=bytes(m.ram[0x200:0x6700]);frames=len(m.spi.frames)
    out=cmd(cpu,m,b'R SRAM\r');assert b'SRAM loader unavailable' in out and bytes(m.ram[0x200:0x6700])==area and len(m.spi.frames)==frames
    cpu,m=boot();off=k.REPORT['status_asset_address']-0x8000;m.banks[2][off+100]^=1
    out=cmd(cpu,m,b'R SRAM\r');assert b'Status unavailable' in out and b'B3> ' in out,out[-500:]
    passed('EDU OFF preserves all reclaimed/application RAM and performs no SPI calls; corrupt shared executive refuses with a normal monitor prompt')
def transfers(passed):
    cpu,m=formatted(fast=True)
    manifest=json.loads((OUT/'maint/manifest.json').read_text());n=int.from_bytes(m.banks[1][6:8],'little')
    assert hashlib.sha256(bytes(m.banks[1][24:24+n])).hexdigest()==manifest['program_sha256']
    # The transfer operates on storage directly; it must not load the program
    # over MAINT or use the application's original RAM as an intermediate.
    payload=bytes((i*29)&255 for i in range(257))
    record=b'SR\x01\x3F\x00\x02'+len(payload).to_bytes(2,'little')+b'ORIGIN'.ljust(16,b'\0')+payload
    origin_offset=max(0x5000,k.REPORT['status_asset_address']+k.REPORT['status_asset_bytes']-0x8000)
    m.banks[2][origin_offset:origin_offset+len(record)]=record
    flash=[bytes(b) for b in m.banks];ee=bytes(m.bus.ee);clock=bytes(m.bus.rtc_regs);area=bytes(m.spi.devices[0].data[0x10000:])
    cpu.pc=0x7E67;cmd(cpu,m,b'');out=cmd(cpu,m,b'R MAINT\rX 2 ORIGIN S COPIED\rY\r')
    assert b'Copied and verified' in out,out[-800:]
    assert [bytes(b) for b in m.banks]==flash and bytes(m.bus.ee)==ee and bytes(m.bus.rtc_regs)==clock
    assert bytes(m.spi.devices[0].data[0x10000:])==area
    out=cmd(cpu,m,b'X S COPIED 2 RETURNED\rY\r')
    assert b'Destination B02:8000' in out and b'Copied and verified' in out,out[-800:]
    assert m.banks[2][:24]==b'SR\x01\x3F\x00\x02'+len(payload).to_bytes(2,'little')+b'RETURNED'.ljust(16,b'\0')
    assert m.banks[2][24:24+len(payload)]==payload
    assert bytes(m.banks[2][origin_offset:origin_offset+len(record)])==record and bytes(m.spi.devices[0].data[0x10000:])==area
    before=([bytes(b) for b in m.banks],bytes(m.spi.devices[0].data))
    out=cmd(cpu,m,b'X 2 ORIGIN S CANCEL\rN\rX 2 ORIGIN S MAINT\rX S COPIED 3 BAD\rX 2 ABSENT S MISSING\r')
    assert b'CANCELED' in out and b'Copy failed' in out and b'INVALID' in out,out[-800:]
    assert ([bytes(b) for b in m.banks],bytes(m.spi.devices[0].data))==before
    # Duplicate flash labels refuse instead of silently choosing one image.
    m.banks[2][0x5400:0x5400+len(record)]=record
    out=cmd(cpu,m,b'X 2 ORIGIN S AMBIG\r');assert b'Copy failed' in out
    m.banks[2][0x5400:0x5400+len(record)]=b'\xff'*len(record)
    # Pending records reserve their entire payload; they do not add a source.
    pending=bytearray(record);pending[3]=255;m.banks[2][0x5400:0x5400+len(record)]=pending
    out=cmd(cpu,m,b'X 2 ORIGIN S CANCEL\rN\r');assert b'CANCELED' in out,out[-700:]
    m.banks[2][0x5400:0x5400+len(record)]=b'\xff'*len(record)
    passed('cancel, missing source, duplicate label, pending source, forbidden B3 and MAINT-to-SRAM refuse without committing destinations')
    # Independent/zero entry points cannot be represented by SR v1.
    assert run_api(cpu,m,request(1,'NORUN',start=0x2000,end=0x2001,entry=0))==0
    cpu.pc=manifest['symbols']['BM_MENU'];before=[bytes(b) for b in m.banks]
    out=cmd(cpu,m,b'X S NORUN 2 BADENTRY\r');assert b'INVALID' in out and [bytes(b) for b in m.banks]==before
    a=m.spi.devices[0].data;data=0x800;a[data]^=1;before=[bytes(b) for b in m.banks]
    out=cmd(cpu,m,b'X S COPIED 2 BADCRC\r');assert b'Copy failed' in out and [bytes(b) for b in m.banks]==before;a[data]^=1
    saved=m.banks[3][0x6E95];m.banks[3][0x6E95]=2;before=([bytes(b) for b in m.banks],bytes(a))
    out=cmd(cpu,m,b'X 2 ORIGIN S OLDABI\r');assert b'Copy failed' in out and ([bytes(b) for b in m.banks],bytes(a))==before
    m.banks[3][0x6E95]=saved
    passed('restore-only entry, bad source CRC and mismatched private executive refuse before writing destinations')
    # A short SRAM write never publishes the partial destination.
    a=m.spi.devices[0].data;directory=bytes(a[:0x800]);old_data=bytes(a[0x800:0xA00]);flash=[bytes(b) for b in m.banks]
    m.transfer_fault=lambda op,addr,buf,n:(7,min(17,n)) if op==2 and addr>=0xA00 else (0,n)
    out=cmd(cpu,m,b'X 2 ORIGIN S SHORT\rY\r');assert b'Copy failed' in out,out[-700:]
    m.transfer_fault=None
    assert bytes(a[:0x800])==directory and bytes(a[0x800:0xA00])==old_data and [bytes(b) for b in m.banks]==flash
    # Flash timeout leaves an uncommitted header and preserves the SPI source.
    source=bytes(a);m.fault='timeout';start=len(m.events)
    out=cmd(cpu,m,b'X S COPIED 2 TIMEOUT\rY\r');assert b'Copy failed' in out,out[-700:]
    m.fault=None
    events=m.events[start:];assert events and all(e[0]=='program' and e[1]==2 for e in events)
    first=events[0][2];assert m.banks[2][first-0x8000+3]==255 and bytes(a)==source
    assert m.ram[0xF4]==0 and m.ram[0x67F1:0x67F7]==bytes(6)
    passed('short SPI writes and flash timeout retain both sources, leave destination uncommitted, clear hooks/NMI hold and issue no erases')
    out=cmd(cpu,m,b'Q\rR 2 RETURNED L\r');assert m.ram[0x200:0x200+len(payload)]==payload,out[-500:]
    passed('MAINT flash-to-SRAM and SRAM-to-AUTO-flash copies preserve metadata/payload and source; EEPROM/UTC/workspace untouched; flash copy restores normally')
    assert hashlib.sha256(bytes(m.banks[1][24:24+n])).hexdigest()==json.loads((OUT/'maint/manifest.json').read_text())['program_sha256']

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    if '--maint' not in sys.argv:general(passed)
    transfers(passed)
    manifest=json.loads((OUT/'maint/manifest.json').read_text());store=json.loads((OUT/'store/build.json').read_text())
    report=dict(passed=True,checks=checks,board_access=False,boards_flashed=False,artifacts=k.REPORT['artifacts'],asset_sha256=k.REPORT['status_asset_sha256'],maint_sha256=manifest['program_sha256'],store_sha256=store['sha256'])
    (OUT/('storage-transfer-test-results.json' if '--maint' in sys.argv else 'storage-test-results.json')).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
