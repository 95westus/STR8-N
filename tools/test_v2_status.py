"""Execute unflashed boot/R EDU status, readonly layouts and corrupt assets."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-status')
import binascii,hashlib,json
from beta4_migration import default_config,config_sum,metadata
from test_v2_spi_resident import Memory,k,OUT
from test_v2_sram_store import console
META=json.loads((OUT/'build.json').read_text());EDU=(OUT/'edu/edu.bin').read_bytes()
EDU_VERSION=json.loads((OUT/'edu/build.json').read_text())['version']
ID=bytes.fromhex('5410ecb664af')
def layout(units=4,version=2,revision=1):
    r=bytearray(64);r[:5]=b'SS'+bytes((version,8,8));r[5:7]=(units*64).to_bytes(2,'little')
    if version==2:r[8:12]=revision.to_bytes(4,'little')
    r[60:62]=binascii.crc_hqx(r[:60],0xFFFF).to_bytes(2,'big');r[63]=0xA5;return r
def fresh(off=False,primary=None,secondary=None,**spi):
    m=Memory(**spi);cfg=bytearray(default_config());cfg[13]=0xA5 if off else 0;cfg[14:]=config_sum(cfg)
    m.banks[3][0x4000:0x6000]=metadata(cfg,[0]*32,1)+b'\xff'*(8192-128)
    m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2C 08 10 26 80 00');m.bus.ee[0xF2:0xF8]=ID
    binding=bytearray(b'\xff'*32);binding[:8]=b'EI\x01\0\x01\0\0\0';binding[8:14]=ID;binding[28:30]=binascii.crc_hqx(binding[:28],0xFFFF).to_bytes(2,'little');binding[31]=0
    m.banks[3][0x1C00:0x1C20]=binding
    if 0 in m.spi.devices:
        a=m.spi.devices[0].data;a[:64]=b'\xff'*64 if primary is None else primary
        a[0x240:0x280]=b'\xff'*64 if secondary is None else secondary
    cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu;m.spi.cpu=cpu;return cpu,m
def boot(cpu,hook=None):
    if hook is None:k.model.run(cpu,lambda:k.model.waiting(cpu),30000000);return
    for _ in range(30000000):
        if k.model.waiting(cpu):return
        if not hook(cpu):cpu.step()
    raise AssertionError('hooked model timeout')
def hold(cpu):cpu.pc=0x7E67;boot(cpu)
def run_edu(cpu,m,keys):
    m.ram[0x2000:0x2000+len(EDU)]=EDU;return console(cpu,m,keys,entry=0x2000,limit=35000000)
def snapshot(m):return ([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data) if 0 in m.spi.devices else None)
def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=fresh(primary=layout());before=snapshot(m);boot(cpu);out=bytes(m.tx)
    wanted=b'ABI 65C02 | 816E | 816N-VEC\r\n\r\nRAM $0200-$64FF\r\n\r\nEDU ON\r\n\r\nRTCC: UTC 2026-10-08 19:53:15\r\nRTCC: EUI 54:10:EC:B6:64:AF\r\n\r\nSSRAM: PROGRAM payload 63488 bytes\r\nSSRAM: WORKSPACE 65504 bytes\r\n'
    assert wanted in out,out[-700:]
    assert snapshot(m)==before and m.ram[0x6400:0x6440]==b'\x5A'*64 and m.ram[0x66AF]==0
    assert not m.bus.writes and not m.events
    (OUT/'boot-status/boot-on.txt').write_bytes(out)
    passed('exact approved ON spacing/order/prefixes/capacities; full flash/EEPROM/RTC/SRAM and transfer window preserved')
    for units,payload,workspace in ((1,14336,114656),(2,30720,98272),(3,47104,81888),(4,63488,65504)):
        for mode in ((0,0x40,0x80) if units==4 else (0x40,)):
            cpu,m=fresh(primary=layout(units),mode=mode);before=snapshot(m);boot(cpu)
            assert f'SSRAM: PROGRAM payload {payload} bytes'.encode() in m.tx and f'SSRAM: WORKSPACE {workspace} bytes'.encode() in m.tx
            assert snapshot(m)==before and m.spi.devices[0].mode==mode and m.ram[0x66AF]==0
    passed('all four saved splits and byte/page/sequential SRAM modes report exact capacities without initialization, probe writes or handle epoch changes')
    cpu,m=fresh(off=True,primary=layout());before=snapshot(m);boot(cpu);out=bytes(m.tx)
    assert b'\r\n\r\nRAM $0200-$66FF\r\n\r\nEDU OFF\r\n' in out and b'RTCC:' not in out and b'SSRAM:' not in out
    assert not m.spi.frames and not m.bus.accesses and snapshot(m)==before and m.ram[0x6500:0x6700]==b'\x5A'*512
    result=run_edu(cpu,m,b'?\rON\r\rQ\r');assert ('EDU '+EDU_VERSION).encode() in result and b'RAM $0200-$66FF' in result and b'Canceled.' in result
    assert snapshot(m)==before and m.ram[0x6500:0x6700]==b'\x5A'*512
    (OUT/'boot-status/boot-off.txt').write_bytes(out)
    passed('OFF omits device blocks, does no bus I/O and preserves every reclaimed byte; R EDU displays status before its first prompt')
    bad=layout();bad[60]^=1
    for primary,secondary,text in ((None,None,b'Allocation uninitialized'),(bytes(64),layout(2),b'Layout needs repair'),(bad,None,b'Layout invalid'),(layout(version=1),None,b'PROGRAM payload 63488 bytes')):
        cpu,m=fresh(primary=primary,secondary=secondary);before=snapshot(m);boot(cpu)
        assert text in m.tx,(text,bytes(m.tx[-300:]))
        assert snapshot(m)==before and m.ram[0x6400:0x6440]==b'\x5A'*64 and m.ram[0x66AF]==0
    cpu,m=fresh(present=False);before=snapshot(m);boot(cpu);assert b'SSRAM: Unavailable' in m.tx and snapshot(m)==before
    passed('uninitialized, valid secondary recovery, corrupt primary, legacy layout and missing SRAM are distinguished read-only')
    for status,count in ((0,12),(7,5)):
        cpu,m=fresh(primary=layout());before=snapshot(m)
        def partial(c):
            if c.pc!=0x66A6:return False
            m.ram[0x6400:0x6400+count]=b'\x96'*count;m.ram[0x6658:0x665A]=bytes((status,count))
            c.a=status;c.p=(c.p&~c.CARRY)|(c.CARRY if status==0 else 0);c.pc=(c.stPopWord()+1)&0xFFFF;return True
        boot(cpu,partial);assert b'SSRAM: Unavailable' in m.tx and m.ram[0x6400:0x6440]==b'\x5A'*64 and snapshot(m)==before and m.ram[0x66AF]==0
    passed('short successful transfer and partial failed READ restore every caller byte and refuse capacity figures')
    cpu,m=fresh(primary=layout());boot(cpu);m.ram[0x66AF]=1;before=snapshot(m);window=bytes(range(64));m.ram[0x6400:0x6440]=window
    m.bus.rtc_regs[3]|=0x10;pf_before=snapshot(m)
    result=run_edu(cpu,m,b'?\rQ\r');assert b'EDU ON' in result and b'SSRAM: WORKSPACE 65504 bytes' in result
    assert snapshot(m)==pf_before and m.ram[0x66AF]==1 and m.ram[0x6400:0x6440]==window
    passed('R EDU automatic/? queries preserve latched outage evidence, live workspace epoch and caller transfer bytes on monitor return')
    cpu,m=fresh(primary=layout());boot(cpu)
    result=run_edu(cpu,m,b'OFF\rY\r?\rQ\r');assert b'Saved; RESET required.' in result and b'EDU ON\r\nEDU after RESET: OFF' in result
    assert m.ram[0x7D0A:0x7D0C]==b'\xff\x64' and m.ram[0x7D27]==1
    (OUT/'boot-status/edu-pending.txt').write_bytes(result)
    cpu.pc=0xF004;boot(cpu);assert m.ram[0x7D0A:0x7D0C]==b'\xff\x66'
    passed('new utility preserves confirmed saved changes, displays pending mode independently, and activates only at RESET')
    for corrupt in (False,True):
        cpu,m=fresh(primary=layout());before=snapshot(m)
        offset=META['status_asset_address']-0x8000
        if corrupt:m.banks[2][offset+10]^=1
        else:m.banks[2][offset:offset+META['status_asset_bytes']]=b'\xff'*META['status_asset_bytes']
        before=snapshot(m);boot(cpu)
        assert b'Status unavailable' in m.tx and b'B3> ' in m.tx
        assert snapshot(m)==before and not m.spi.frames and not m.bus.accesses
    passed('missing/corrupt formatter never executes; sealed loader fails boundedly with normal monitor and service reservation intact')
    report=dict(passed=True,checks=checks,artifacts=META['artifacts'],asset_sha256=META['status_asset_sha256'],edu_sha256=hashlib.sha256(EDU).hexdigest(),board_access=False,boards_flashed=False)
    (OUT/'status-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
