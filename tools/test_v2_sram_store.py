"""Execute the linked SRAM manager with the real resident bit-level SPI model."""
import binascii,hashlib,json,struct
from test_v2_spi_resident import boot,k,OUT
STORE=OUT/'store';META=json.loads((STORE/'build.json').read_text());SYM=META['symbols']
CORE=(STORE/'store-core.bin').read_bytes();IMAGE=(STORE/'sram.bin').read_bytes()
DATA=(STORE/'store-data.bin').read_bytes()
AUX=(STORE/'store-layout.bin').read_bytes() if META.get('aux_bytes') else b''
MAX_STACK=[0]

def install(cpu,m):
    m.ram[0x6C00:0x6C00+len(CORE)]=CORE
    data_start=META.get('data_start',0x6800)
    m.ram[data_start:data_start+len(DATA)]=DATA
    if AUX:m.ram[0x6800:0x6800+len(AUX)]=AUX
    if META.get('streams'):
        ext=(STORE/'store-stream.bin').read_bytes();m.ram[0x7B90:0x7B90+len(ext)]=ext
    cpu.pc=0x200

def request(op,name='DEMO',start=0x2000,end=0x201F,entry=0x2000,key=b''):
    r=bytearray(32);r[0]=op;r[2:8]=struct.pack('<HHH',start,end,entry)
    r[8:24]=name.encode().ljust(16,b'\0');r[24:32]=key.ljust(8,b'\0')
    return r

def run_api(cpu,m,r,max_steps=12000000,hook=None):
    m.ram[0x6200:0x6220]=r;cpu.a=0;cpu.x=0x62;cpu.p=cpu.UNUSED|cpu.INTERRUPT
    sp=cpu.sp;cpu.stPushWord(0x1FF);cpu.pc=0x6C03;lowest=cpu.sp
    for steps in range(max_steps):
        if cpu.pc==0x200:break
        if hook:hook(cpu,m)
        if getattr(m,'fast',False) and cpu.pc==0x66A6:
            fast_transfer(cpu,m);continue
        lowest=min(lowest,cpu.sp);cpu.step()
    else:raise AssertionError(('timeout',hex(cpu.pc)))
    assert cpu.sp==sp
    m.manager_stack=max(getattr(m,'manager_stack',0),sp-lowest)
    MAX_STACK[0]=max(MAX_STACK[0],sp-lowest)
    assert bool(cpu.p&cpu.CARRY)==(cpu.a==0)
    return cpu.a

def fast_transfer(cpu,m):
    """ABI-level fault model for exhaustive manager tests; bit SPI tested separately."""
    if cpu.pc!=0x66A6:return
    r=m.ram[0x6650:0x6660];op=r[0];addr=int.from_bytes(r[2:5],'little')
    buf=int.from_bytes(r[5:7],'little');n=r[7];status=0;done=0
    array=m.spi.devices[0].data if 0 in m.spi.devices else None
    if array is None:status=7
    elif op==0:m.ram[0x665B:0x665F]=bytes((0,0,2,0x81))
    elif op not in (1,2) or not 1<=n<=64 or addr+n>0x20000 or buf<0x200 or buf+n>0x6500:status=9
    elif op==2 and m.ram[0x66AE]:status=6
    else:
        fault=getattr(m,'transfer_fault',None)
        if fault:status,limit=fault(op,addr,buf,n)
        else:limit=n
        if op==1:m.ram[buf:buf+limit]=array[addr:addr+limit]
        else:
            for j in range(limit):
                array[addr+j]=m.ram[buf+j]
                if getattr(m,'cut',None):m.cut(addr+j)
        done=limit
    m.ram[0x6658]=status;m.ram[0x6659]=done
    cpu.a=status;cpu.p=(cpu.p&~cpu.CARRY)|(cpu.CARRY if status==0 else 0)
    cpu.pc=(cpu.stPopWord()+1)&0xFFFF

def formatted(fast=False):
    cpu,m=boot();install(cpu,m);m.fast=fast
    if fast:m.transfer_fault=None
    assert run_api(cpu,m,request(6,key=b'FORMAT!!'))==0
    return cpu,m

def records(m):
    a=m.spi.devices[0].data
    return [(i,bytes(a[64+i*64:128+i*64])) for i in range(8) if a[127+i*64]==0xA5]

def console(cpu,m,keys=b'',entry=None,limit=18000000):
    start=len(m.tx);m.rx.extend(keys)
    if entry is not None:cpu.pc=entry
    for _ in range(limit):
        if k.model.waiting(cpu):break
        if getattr(m,'fast',False) and cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    else:raise AssertionError(('console timeout',hex(cpu.pc),bytes(m.tx[-100:])))
    return bytes(m.tx[start:])

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=boot();install(cpu,m);initial=bytes(m.spi.devices[0].data)
    assert run_api(cpu,m,request(0))==0x40
    assert bytes(m.spi.devices[0].data)==initial
    assert run_api(cpu,m,request(6,key=b'NO'))==0x44
    assert bytes(m.spi.devices[0].data)==initial
    passed('unformatted retained contents never trigger formatting; destructive format requires exact key')
    cpu,m=formatted();a=m.spi.devices[0].data
    assert a[:8]==b'SS\x01\x08\x08\0\x01\0' and a[63]==0xA5 and binascii.crc_hqx(a[:62],0xFFFF)==0
    assert a[0x10000:]==initial[0x10000:]
    data=bytes((i*17)&255 for i in range(96));m.ram[0x2000:0x2060]=data
    before=[bytes(b) for b in m.banks];calendar=bytes(m.bus.rtc_regs);ee=bytes(m.bus.ee)
    assert run_api(cpu,m,request(1,end=0x205F))==0
    rec=records(m);assert len(rec)==1
    header=rec[0][1];assert binascii.crc_hqx(header[:62],0xFFFF)==0
    assert int.from_bytes(header[12:14],'little')==binascii.crc_hqx(data,0xFFFF)
    assert bytes(a[header[14]*256:header[14]*256+96])==data
    m.ram[0x2000:0x2060]=bytes([0xCC])*96
    assert run_api(cpu,m,request(2))==0 and m.ram[0x2000:0x2060]==data
    assert before==[bytes(b) for b in m.banks] and calendar==bytes(m.bus.rtc_regs) and ee==bytes(m.bus.ee)
    passed('explicit format affects only management bytes; named save and restore validate payload/header CRCs; flash/RTC/EEPROM intact')
    changed=bytes([0xA7])*96;m.ram[0x2000:0x2060]=changed
    assert run_api(cpu,m,request(1,end=0x205F))==0 and len(records(m))==2
    m.ram[0x2000:0x2060]=bytes(96);assert run_api(cpu,m,request(2))==0
    assert m.ram[0x2000:0x2060]==changed
    assert run_api(cpu,m,request(5))==0 and len(records(m))==1
    assert run_api(cpu,m,request(4))==0 and len(records(m))==2
    assert run_api(cpu,m,request(2))==0x42
    assert run_api(cpu,m,request(5))==0
    assert not records(m)
    passed('replacement publishes a higher sequence while retaining previous image; explicit reclaim preserves latest; deletion prevents resurrection')
    # Loader bootstrap must not overwrite monitor worker or API state.
    worker_end=0x7B90 if META.get('streams') else 0x7C00
    cpu,m=boot();m.ram[0x4000:0x4000+len(IMAGE)]=IMAGE;worker=bytes(m.ram[0x7800:worker_end])
    cpu.pc=0x4000
    for _ in range(30000):
        if cpu.pc==0x6C00:break
        cpu.step()
    else:raise AssertionError('bootstrap did not relocate')
    assert m.ram[0x6C00:0x6C00+len(CORE)]==CORE and bytes(m.ram[0x7800:worker_end])==worker
    if META.get('streams'):
        assert m.ram[0x7B90:0x7B90+META['ext_bytes']]==(STORE/'store-stream.bin').read_bytes()
    ds=META.get('data_start',0x6800);assert m.ram[ds:ds+len(DATA)]==DATA
    if AUX:assert m.ram[0x6800:0x6800+len(AUX)]==AUX
    passed('saved utility bootstrap relocates completely within staging workspace and preserves the flash worker')
    cpu,m=formatted(fast=True);a=m.spi.devices[0].data
    # Source/target through the preserved 6400 window, inclusive top 64FF.
    upper=bytes((i^0x96)&255 for i in range(0x120));m.ram[0x63E0:0x6500]=upper
    assert run_api(cpu,m,request(1,'TOP',0x63E0,0x64FF,0))==0
    assert m.ram[0x63E0:0x6500]==upper
    m.ram[0x63E0:0x6500]=bytes(0x120)
    assert run_api(cpu,m,request(2,'TOP'))==0 and m.ram[0x63E0:0x6500]==upper
    assert run_api(cpu,m,request(3,'TOP'))==0x47
    before=bytes(a)
    for r in (request(1,'BAD',0x6400,0x6500),request(1,'BAD',0x1FF,0x210),
              request(1,'BAD',0x2300,0x2200),request(1,'BAD',entry=0x2100),request(1,'bad')):
        assert run_api(cpu,m,r)==0x44 and bytes(a)==before
    passed('save/restore preserves transfer-window contents, accepts inclusive 64FF, refuses protected/wrapped ranges and out-of-image entry points')
    # Corrupt payload or committed metadata must refuse before any target copy.
    slot,header=records(m)[0];page=header[14];a[page*256]^=1
    m.ram[0x63E0:0x6500]=bytes([0x7C])*0x120;unchanged=bytes(m.ram[0x63E0:0x6500])
    assert run_api(cpu,m,request(2,'TOP'))==0x45 and bytes(m.ram[0x63E0:0x6500])==unchanged
    a[page*256]^=1;a[64+slot*64+4]^=1
    assert run_api(cpu,m,request(2,'TOP'))==0x41 and bytes(m.ram[0x63E0:0x6500])==unchanged
    a[64+slot*64+4]^=1
    # Identical name and highest sequence is ambiguous even with valid seals.
    second=(slot+1)%8;clone=bytearray(header);clone[14]=page+2
    clone[60:62]=binascii.crc_hqx(clone[:60],0xFFFF).to_bytes(2,'big')
    a[64+second*64:128+second*64]=clone
    assert run_api(cpu,m,request(2,'TOP'))==0x41
    a[127+second*64]=0
    passed('bad payload/header and duplicate highest sequences reject before overwriting destination; no fallback to flash')
    # Eight directory slots bound publication. Existing data remains on refusal.
    cpu,m=formatted(fast=True);a=m.spi.devices[0].data
    m.ram[0x2000:0x2020]=bytes(range(32))
    for i in range(8):assert run_api(cpu,m,request(1,f'P{i}'))==0
    before=bytes(a);assert run_api(cpu,m,request(1,'P0'))==0x43 and bytes(a)==before
    passed('full directory refuses replacement without destroying prior record')
    # Extent exhaustion is independent of directory space.
    cpu,m=formatted(fast=True);a=m.spi.devices[0].data
    for i,end in enumerate((0x60FF,0x60FF,0x60FF,0x54FF)):
        assert run_api(cpu,m,request(1,f'BIG{i}',0x2000,end,0))==0
    before=bytes(a);assert run_api(cpu,m,request(1,'FULL',0x2000,0x2000,0))==0x43 and bytes(a)==before
    passed('all 248 payload pages can be allocated; payload-full refusal preserves every record')
    # Power cuts after every new metadata byte, and at payload/commit boundaries.
    cpu,m=formatted(fast=True);a=m.spi.devices[0].data
    m.ram[0x2000:0x2020]=bytes([0x31])*32;assert run_api(cpu,m,request(1))==0
    baseline=bytes(a);old=records(m)[0];cut_results=[]
    class Cut(Exception):pass
    for cut in (1,16,32,*range(33,98)):
        a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x2000:0x2020]=bytes([0xA4])*32
        writes=[0]
        def cut_at(address):
            writes[0]+=1
            if writes[0]==cut:raise Cut()
        m.cut=cut_at
        try:run_api(cpu,m,request(1))
        except Cut:pass
        else:raise AssertionError(('cut not reached',cut))
        m.cut=None;install(cpu,m);cpu.sp=0xFF;m.ram[0x66AE]=1
        assert run_api(cpu,m,request(2))==0
        expected=bytes([0xA4 if cut==97 else 0x31])*32
        assert m.ram[0x2000:0x2020]==expected,(cut,records(m))
        assert bytes(a[64+old[0]*64:128+old[0]*64])==old[1]
        cut_results.append(cut)
    passed(f'{len(cut_results)} replacement power-cut cases retain old record through payload/header writes and publish only at final marker')
    # A reported failed read after copying starts cannot execute the program.
    a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x2000:0x2020]=bytes([0xCC])*32
    def failed_copy(op,addr,buf,n):
        if op==1 and buf==0x2000:return 7,8
        return 0,n
    m.transfer_fault=failed_copy
    assert run_api(cpu,m,request(3))==0x46 and m.ram[0x2000:0x2008]==bytes([0x31])*8
    assert m.ram[0x2008:0x2020]==bytes([0xCC])*24
    m.transfer_fault=None
    passed('interrupted restore reports partial completion and never jumps to saved entry')
    # Short success is a malformed transfer result and cannot be treated as done.
    m.transfer_fault=lambda op,addr,buf,n:(0,8) if op==1 and buf==0x2000 else (0,n)
    assert run_api(cpu,m,request(3))==0x46
    m.transfer_fault=None
    passed('short completed-count result is refused rather than counted as a full restore')
    # FORMAT interruption cannot leave a valid layout describing a cleared directory.
    for cut in range(1,75):
        a[:]=baseline;install(cpu,m);cpu.sp=0xFF
        count=[0]
        def format_cut(address):
            count[0]+=1
            if count[0]==cut:raise Cut()
        m.cut=format_cut
        try:run_api(cpu,m,request(6,key=b'FORMAT!!'))
        except Cut:pass
        else:raise AssertionError(('format cut not reached',cut))
        m.cut=None;install(cpu,m);cpu.sp=0xFF
        assert run_api(cpu,m,request(0))==(0 if cut==74 else 0x40)
        assert bytes(a[0x800:])==baseline[0x800:]
    passed('all 74 format-write cut points invalidate layout first and preserve payload/workspace; retry remains explicit')
    # Returned write error before publication retains the old version.
    a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x2000:0x2020]=bytes([0xA4])*32
    m.transfer_fault=lambda op,addr,buf,n:(7,8) if op==2 and addr>=0x800 else (0,n)
    assert run_api(cpu,m,request(1))==7
    m.transfer_fault=None;assert run_api(cpu,m,request(2))==0 and m.ram[0x2000:0x2020]==bytes([0x31])*32
    passed('reported payload write failure retains the prior committed version')
    # Reclaim cannot discard the older image if its replacement is corrupt.
    a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x2000:0x2020]=bytes([0xA4])*32
    assert run_api(cpu,m,request(1))==0
    new=max(records(m),key=lambda row:int.from_bytes(row[1][10:12],'little'))
    a[new[1][14]*256]^=1;before=bytes(a)
    assert run_api(cpu,m,request(5))==0x45 and bytes(a)==before
    a[new[1][14]*256]^=1
    m.ram[0x2000:0x2020]=bytes([0x77])*32;assert run_api(cpu,m,request(1,'OTHER'))==0
    assert run_api(cpu,m,request(4))==0;deleted=bytes(a)
    other=next(h for _,h in records(m) if h[16:21]==b'OTHER')
    for cut in (1,2,3):
        a[:]=deleted;install(cpu,m);cpu.sp=0xFF;counter=[0]
        def gc_cut(address):
            counter[0]+=1
            if counter[0]==cut:raise Cut()
        m.cut=gc_cut
        try:run_api(cpu,m,request(5))
        except Cut:pass
        else:raise AssertionError(('GC cut not reached',cut))
        m.cut=None;install(cpu,m);cpu.sp=0xFF
        assert run_api(cpu,m,request(2))==0x42
        assert run_api(cpu,m,request(2,'OTHER'))==0 and m.ram[0x2000:0x2020]==bytes([0x77])*32
        assert any(h==other for _,h in records(m))
    passed('reclaim verifies newer data before releasing old image; every deletion/reclaim cut prevents resurrection and preserves unrelated names')
    # Every new call rereads layout/directory, not a prior cached listing.
    a[:]=baseline;install(cpu,m);cpu.sp=0xFF;assert run_api(cpu,m,request(0))==0
    a[127+old[0]*64]=0;assert run_api(cpu,m,request(2))==0x42
    passed('stale RAM directory cannot restore a removed SPI record')
    # Console uses the SPI provider explicitly; monitor R continues to use flash.
    cpu,m=formatted(fast=True)
    program=bytes.fromhex('EE 00 23 4C 67 7E');m.ram[0x2000:0x2006]=program;m.ram[0x2300]=0
    output=console(cpu,m,entry=0x6C00);assert b'SRAM> ' in output
    assert b'SRAM: 00' in console(cpu,m,b'S DEMO 2000 2005 2000\r')
    assert b'SRAM: 44' in console(cpu,m,b'T EXTRA\r')
    before=bytes(m.spi.devices[0].data)
    output=console(cpu,m,b'S X 2000 2005 2000'+b'X'*256+b'\r')
    assert b'SRAM: 00' not in output and bytes(m.spi.devices[0].data)==before
    assert b'SRAM: 44' in console(cpu,m,b'F\rNO\r') and bytes(m.spi.devices[0].data)==before
    console(cpu,m,b'S DEMO\x03');assert bytes(m.spi.devices[0].data)==before
    console(cpu,m,b'F\r\x1B');assert bytes(m.spi.devices[0].data)==before
    assert b'SRAM: 44' not in console(cpu,m,b'TX\x08\r')
    output=console(cpu,m,b'T\r');assert b'DEMO 2000 0006' in output and b'Free bytes: $F700' in output
    m.ram[0x2000:0x2006]=bytes(6)
    assert b'SRAM: 00' in console(cpu,m,b'R DEMO\r') and m.ram[0x2000:0x2006]==program
    assert b'B3> ' in console(cpu,m,b'Q\r')
    assert b'Done' in k.model.command(cpu,b'S 2 8000 2000 2005 DEMO\r',16000000)
    m.ram[0x2000:0x2006]=bytes(6)
    assert b'Done' in k.model.command(cpu,b'R 2 DEMO L\r',16000000) and m.ram[0x2000:0x2006]==program
    output=k.model.command(cpu,b'R 2 DEMO\r',16000000);assert b'B3> ' in output and m.ram[0x2300]==1
    install(cpu,m);m.fast=True
    console(cpu,m,entry=0x6C00);m.ram[0x2000:0x2006]=bytes(6)
    output=console(cpu,m,b'G DEMO\r');assert b'B3> ' in output and m.ram[0x2300]==2
    assert m.ram[0x2000:0x2006]==program
    # Q/HOLD may invalidate borrowed staging contents; reloading is deliberate.
    m.ram[0x4000:0x4000+len(IMAGE)]=IMAGE
    transport=0xB000 if k.REPORT.get('storage_services') else 0xA000
    assert b'Done' in k.model.command(cpu,f'S 1 {transport:04X} 4000 {META["load_end"]:04X} SRAM\r'.encode(),16000000)
    m.ram[0x4000:0x4000+len(IMAGE)]=bytes(len(IMAGE))
    output=k.model.command(cpu,b'R SRAM\r',16000000);assert ('SRAM '+META['version']).encode() in output and b'SRAM> ' in output
    output=console(cpu,m,b'T\rQ\r');assert b'DEMO 2000 0006' in output and b'B3> ' in output
    if META.get('streams'):
        m.ram[0x4000:0x4000+len(IMAGE)]=IMAGE
        output=k.model.command(cpu,b'G 4000\r',16000000)
        assert ('SRAM '+META['version']).encode() in output and b'SRAM> ' in output
        assert console(cpu,m,b'T\rQ\r').count(b'DEMO 2000 0006')==1
    passed('console save/table/restore/run, strict/overflow/canceled input, and R SRAM reload work; identical named flash/SPI images load and execute the same bytes')
    for options in (dict(present=False),dict(stuck='low'),dict(stuck='high')):
        cpu,m=boot(**options);install(cpu,m)
        assert run_api(cpu,m,request(0))==7
        assert m.ram[0x66AE]==1
    passed('missing or stuck EDU SRAM fails bounded probe and leaves managed write protection enabled')
    report=dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],store_sha256=META['sha256'],
        core_bytes=META['core_bytes'],data_bytes=META['data_bytes'],replacement_power_cut_cases=cut_results,
        max_stack_bytes=MAX_STACK[0],hardware_tested=False,board_writes=False,
        fault_tests='linked 65C02 manager with ABI transfer fault model; basic integration uses real bit-level resident service')
    (STORE/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
