"""Execute allocation/handle code, with real resident SPI and ABI fault models."""
import binascii,json,struct
from test_v2_sram_store import boot,k,fast_transfer,formatted,install as install_store,run_api as store_api,request as store_request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=k.fw.OUT/'workspace'
META=json.loads((OUT/'build.json').read_text());BODY=(OUT/'workspace.bin').read_bytes();S=META['symbols']
STACK=[0]

def install(cpu,m):m.ram[META['entry']:META['entry']+len(BODY)]=BODY;cpu.pc=0x200
def req(op,owner=1,handle=None,size=0,offset=0,count=0,buffer=0x2300,units=4,key=b''):
    r=bytearray(32);r[0]=op;r[2:4]=struct.pack('<H',owner)
    if handle is not None:r[4:12]=handle
    r[12:15]=offset.to_bytes(3,'little');r[15]=count;r[16:18]=struct.pack('<H',buffer)
    r[18:21]=size.to_bytes(3,'little');r[21]=units;r[24:32]=key.ljust(8,b'\0');return r
def call(cpu,m,r,hook=None,limit=15000000):
    m.ram[0x2200:0x2220]=r;cpu.a=0;cpu.x=0x22;cpu.p=cpu.UNUSED|cpu.INTERRUPT
    sp=cpu.sp;cpu.stPushWord(0x1FF);cpu.pc=META['api'];low=cpu.sp
    for _ in range(limit):
        if cpu.pc==0x200:break
        if hook:hook(cpu,m)
        low=min(low,cpu.sp)
        if getattr(m,'fast',False) and cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    else:raise AssertionError(('timeout',hex(cpu.pc)))
    assert cpu.sp==sp and bool(cpu.p&cpu.CARRY)==(cpu.a==0)
    STACK[0]=max(STACK[0],sp-low)
    return cpu.a,bytes(m.ram[0x2200:0x2220])
def fresh(fast=True):
    cpu,m=boot();install(cpu,m);m.fast=fast
    assert call(cpu,m,req(6,key=b'FORMAT!!'))[0]==0
    return cpu,m
def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=boot();install(cpu,m);m.fast=True;before=bytes(m.spi.devices[0].data)
    assert call(cpu,m,req(0))[0]==0x40 and bytes(m.spi.devices[0].data)==before
    assert call(cpu,m,req(6,key=b'NO'))[0]==0x44
    cpu,m=fresh();a=m.spi.devices[0].data
    status,r=call(cpu,m,req(0));assert status==0 and int.from_bytes(r[18:21],'little')==65504 and r[21]==4
    assert a[:8]==b'SS\x02\x08\x08\0\x01\0' and binascii.crc_hqx(a[:62],0xFFFF)==0
    passed('invalid retained storage stays untouched; confirmed format publishes versioned dual layout and exact capacity')
    status,r=call(cpu,m,req(1,size=512));assert status==0,(status,r.hex())
    h=r[4:12];pattern=bytes(range(64));m.ram[0x2300:0x2340]=pattern
    assert call(cpu,m,req(4,handle=h,count=64))[0]==0
    m.ram[0x2300:0x2340]=bytes(64)
    assert call(cpu,m,req(3,handle=h,count=64))[0]==0 and m.ram[0x2300:0x2340]==pattern
    assert call(cpu,m,req(3,owner=2,handle=h,count=1))[0]==0x4B
    assert call(cpu,m,req(3,handle=h,count=1,offset=512))[0]==0x44
    assert call(cpu,m,req(3,handle=h,count=1,buffer=META['entry']))[0]==0x44
    assert call(cpu,m,req(2,handle=h))[0]==0
    assert call(cpu,m,req(3,handle=h,count=1))[0]==0x4B
    _,r=call(cpu,m,req(1,size=512));assert r[4:12]!=h
    passed('claim/read/write/release enforce owners, unique tickets, bounds and application-library ownership')
    cpu,m=fresh();a=m.spi.devices[0].data
    _,r=call(cpu,m,req(1,size=512));h=r[4:12]
    # Reload/HOLD retain claims; actual reset clears the resident session latch.
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    install(cpu,m);assert m.ram[0x66AF]==1
    assert call(cpu,m,req(3,handle=h,count=1))[0]==0
    cpu.pc=0xF004;k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    assert m.ram[0x66AF]==0
    install(cpu,m);assert call(cpu,m,req(3,handle=h,count=1))[0]==0x4B
    _,r=call(cpu,m,req(1,size=512));assert r[4:12]!=h
    passed('live claims survive HOLD and library reload; actual RESET invalidates prior epoch handles')
    cpu,m=fresh();a=m.spi.devices[0].data;whole=bytes(a)
    for units in (1,2,3,4):
        status,r=call(cpu,m,req(5,units=units,key=b'RESIZE!!'))
        assert status==0,(units,status)
        assert r[21]==units and int.from_bytes(r[18:21],'little')==0x1FFE0-units*0x4000
    assert a[0x800:]==whole[0x800:]
    assert call(cpu,m,req(5,units=0,key=b'RESIZE!!'))[0]==0x44
    assert call(cpu,m,req(5,units=3,key=b'NO'))[0]==0x44
    # Claims at 10000 remain valid when workspace grows downward.
    _,r=call(cpu,m,req(1,size=512));h=r[4:12]
    assert call(cpu,m,req(5,units=1,key=b'RESIZE!!'))[0]==0
    assert call(cpu,m,req(3,handle=h,count=1))[0]==0
    _,r=call(cpu,m,req(1,size=512));low=r[4:12]
    before=bytes(a);assert call(cpu,m,req(5,units=4,key=b'RESIZE!!'))[0]==0x4A and bytes(a)==before
    assert call(cpu,m,req(2,handle=low))[0]==0
    assert call(cpu,m,req(5,units=4,key=b'RESIZE!!'))[0]==0
    passed('16/32/48/64 KiB partition updates preserve data; growing program region refuses live workspace overlap')
    # Version-1 upgrade preserves saved records and all payload/workspace bytes.
    cpu,m=formatted(fast=True);m.ram[0x2000:0x2020]=bytes(range(32))
    assert store_api(cpu,m,store_request(1))==0
    old=bytes(m.spi.devices[0].data);install(cpu,m)
    assert call(cpu,m,req(1,size=64))[0]==0x49
    assert call(cpu,m,req(7,key=b'UPGRADE!'))[0]==0
    a=m.spi.devices[0].data;assert a[64:576]==old[64:576] and a[0x800:]==old[0x800:]
    install_store(cpu,m);assert store_api(cpu,m,store_request(2))==0
    assert m.ram[0x2000:0x2020]==bytes(range(32))
    assert store_api(cpu,m,store_request(6,key=b'FORMAT!!'))==0x49
    install(cpu,m);assert call(cpu,m,req(5,units=1,key=b'RESIZE!!'))[0]==0
    install_store(cpu,m)
    m.ram[0x2000:0x6000]=bytes([0x77])*0x4000
    assert store_api(cpu,m,store_request(1,'TOOBIG',0x2000,0x5FFF,0))==0x43
    passed('explicit legacy upgrade preserves images; paired SRAM reader obeys variable capacity and refuses legacy format over managed layout')
    # Complete 17-bit capacity, including the last 224 bytes before probe space.
    cpu,m=fresh();a=m.spi.devices[0].data
    assert call(cpu,m,req(5,units=1,key=b'RESIZE!!'))[0]==0
    status,r=call(cpu,m,req(1,size=0x1BFE0));assert status==0
    h=r[4:12];m.ram[0x2300:0x2340]=bytes([0x96])*64
    assert call(cpu,m,req(4,handle=h,offset=0x1BFA0,count=64))[0]==0
    assert a[0x1FFA0:0x1FFE0]==bytes([0x96])*64
    before=bytes(a);assert call(cpu,m,req(1,size=1))[0]==0x43 and bytes(a)==before
    assert call(cpu,m,req(3,handle=h,offset=0x1BFE0,count=1))[0]==0x44
    assert call(cpu,m,req(3,handle=h,count=32,buffer=0x2200))[0]==0x44
    assert call(cpu,m,req(3,handle=h,count=64,buffer=0x64E0))[0]==0x44
    passed('24-bit offsets cover exact 112 KiB workspace capacity through 1FFDF; exhaustion, request overlap and CPU overflow refuse safely')
    # All four claim slots, then release/reuse without reviving an old handle.
    cpu,m=fresh();handles=[]
    for owner in (1,2,3,4):
        status,r=call(cpu,m,req(1,owner=owner,size=64));assert status==0;handles.append(r[4:12])
    assert call(cpu,m,req(1,owner=5,size=1))[0]==0x43
    assert call(cpu,m,req(2,owner=2,handle=handles[1]))[0]==0
    status,r=call(cpu,m,req(1,owner=2,size=64));assert status==0 and r[4:12]!=handles[1]
    assert call(cpu,m,req(3,owner=2,handle=handles[1],count=1))[0]==0x4B
    # A deliberately sealed overlapping claim must be rejected as metadata damage.
    a=m.spi.devices[0].data;active=[(i,bytes(a[0x300+i*32:0x320+i*32])) for i in range(4)]
    i,first=active[0];j,second=active[1];bad=bytearray(second);bad[12:15]=first[12:15]
    bad[28:30]=binascii.crc_hqx(bad[:28],0xFFFF).to_bytes(2,'big');a[0x300+j*32:0x320+j*32]=bad
    before=bytes(a);assert call(cpu,m,req(3,handle=handles[0],count=1))[0]==0x41 and bytes(a)==before
    passed('claim-slot exhaustion/reuse preserves ownership; sealed overlapping claims are refused before data access')
    # Every resize publication byte: old primary remains authoritative until
    # its marker is invalidated, then verified secondary supplies recovery.
    cpu,m=fresh();a=m.spi.devices[0].data;baseline=bytes(a)
    class Cut(Exception):pass
    resize_cuts=[]
    for cut in range(1,134):
        a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x66AF]=1;m.ram[0x66AE]=1
        count=[0]
        def cut_at(address):
            count[0]+=1
            if count[0]==cut:raise Cut()
        m.cut=cut_at
        try:call(cpu,m,req(5,units=3,key=b'RESIZE!!'))
        except Cut:pass
        else:raise AssertionError(('resize cut not reached',cut))
        m.cut=None;install(cpu,m);cpu.sp=0xFF;m.ram[0x66AE]=1
        status,r=call(cpu,m,req(0));assert status==0 and r[21]==(4 if cut<67 else 3),(cut,status,r.hex())
        assert a[0x800:]==baseline[0x800:]
        if r[23]:assert call(cpu,m,req(8,key=b'REPAIR!!'))[0]==0
        resize_cuts.append(cut)
    passed('all 133 resize write-cut points expose one safe boundary; explicit primary repair preserves payload/workspace')
    # Ticket publication before claim completion prevents stale slot aliasing.
    cpu,m=fresh();a=m.spi.devices[0].data;baseline=bytes(a);claim_cuts=[]
    for cut in range(1,101):
        a[:]=baseline;install(cpu,m);cpu.sp=0xFF;m.ram[0x66AF]=1;m.ram[0x66AE]=1;count=[0]
        def claim_cut(address):
            count[0]+=1
            if count[0]==cut:raise Cut()
        m.cut=claim_cut
        try:call(cpu,m,req(1,size=64))
        except Cut:pass
        else:raise AssertionError(('claim cut not reached',cut))
        m.cut=None;install(cpu,m);cpu.sp=0xFF;m.ram[0x66AE]=1
        status,r=call(cpu,m,req(1,size=64));assert status==0
        assert int.from_bytes(r[10:12],'little')==(1 if cut<66 else 2),(cut,r.hex())
        assert a[0x800:]==baseline[0x800:]
        claim_cuts.append(cut)
    passed('all 100 claim/session write-cut points reserve tickets before publishing claims; no overlapping allocation or handle reuse')
    report=dict(passed=True,checks=checks,workspace_sha256=META['sha256'],resident_artifacts=k.REPORT['artifacts'],
        max_stack_bytes=STACK[0],bytes=len(BODY),resize_write_cuts=resize_cuts,claim_write_cuts=claim_cuts,
        hardware_tested=False,board_access=False)
    (OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
