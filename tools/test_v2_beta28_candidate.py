"""Execute beta28 reference banks offline. Never opens a serial port."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-beta27')
import json,re
from pathlib import Path
from beta4_migration import crc
from test_v2_status import fresh,boot,snapshot
from test_v2_sram_store import console,fast_transfer,request as sreq
from test_v2_spi_resident import k
from test_v2_workspace import req
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-beta28'
META=json.loads((OUT/'build.json').read_text());X=json.loads((OUT/'xip/build.json').read_text());S=X['symbols']
EVIDENCE=ROOT/'output/qualification/beta27-2026-10-15/2609'

def fixture(key=None,corrupt=None):
    cpu,m=fresh();m.banks=[bytearray((OUT/f'candidate/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
    m.spi.devices[0].data[:]=(EVIDENCE/'retained/sram-final/array-0.bin').read_bytes();m.fast=True
    status=(EVIDENCE/'retained/devices-after/status.txt').read_bytes();raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode());m.bus.rtc_regs[:9]=raw
    m.bus.ee[0xF2:0xF8]=m.banks[3][0x1C08:0x1C0E]
    if corrupt=='crc':m.banks[2][0x100]^=1
    if corrupt=='header':
        m.banks[2][0]^=1;m.banks[2][0x57FE:0x5800]=crc(m.banks[2][:0x57FE]).to_bytes(2,'big')
    k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
    if key:m.rx.extend(key)
    boot(cpu);return cpu,m

def command(cpu,m,line):return console(cpu,m,line,limit=80000000)

def api(cpu,m,request,bank=3):
    m.ram[0x2200:0x2220]=request;cpu.a=0;cpu.x=0x22;cpu.p=cpu.UNUSED|cpu.INTERRUPT
    m[0x7FEC]=(m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[bank]
    sp=cpu.sp;cpu.stPushWord(0x1FF);cpu.pc=0x5003
    for _ in range(20000000):
        if cpu.pc==0x200:break
        if cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    else:raise AssertionError(('API timeout',hex(cpu.pc),m.bank))
    assert cpu.sp==sp and m.bank==bank and bool(cpu.p&cpu.CARRY)==(cpu.a==0),(cpu.sp,sp,m.bank,bank,hex(cpu.p),cpu.a)
    return cpu.a,bytes(m.ram[0x2200:0x2220])

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=fixture();assert b'STR8-N 2.0b28' in m.tx and m.ram[0x7D30]==0xA0
    before=snapshot(m)
    assert b'2.0b28' in command(cpu,m,b'VERSION\r')
    assert b'(-05:00)' in command(cpu,m,b'TIME\r')
    passed('beta28 A boots with beta27 B retained; VERSION and TIME work')
    for name,title,query in [('EDU',b'EDU 1.3',b'?\r'),('WORK',b'WORK 1.3',b'?\r'),('SRAM',b'SRAM 1.3',b'T\r'),('MAINT',b'BANK MAINT 2.3',b'?\r')]:
        print('CHECK R',name,flush=True)
        app=bytes(m.ram[0x200:0x6500]);text=command(cpu,m,('R '+name+'\r').encode())
        assert title in text and m.bank==2,(name,text[-500:],m.bank)
        if name in ('SRAM','EDU'):assert bytes(m.ram[0x200:0x6500])==app,name
        if name=='MAINT':assert bytes(m.ram[0x200:0x5000])==app[:0x4E00]
        if name=='WORK':assert bytes(m.ram[0x200:0x5000])==app[:0x4E00] and bytes(m.ram[0x5040:0x6400])==app[0x4E40:0x6200] and bytes(m.ram[0x6440:0x6500])==app[0x6240:]
        text+=command(cpu,m,query);text+=command(cpu,m,b'Q\r');assert text.endswith(b'B3> ') and m.bank==3,(name,text[-500:],m.bank)
        if name=='WORK':assert bytes(m.ram[0x6400:0x6440])==app[0x6200:0x6240]
        assert snapshot(m)==before and not m.events,(name,m.events)
        (OUT/f'candidate-{name}.txt').write_bytes(text)
        passed('R '+name+': sealed XIP launch/query/Q, correct bank return and declared application-RAM preservation')
    text=command(cpu,m,b'APPS\r');assert all(n in text for n in [b'MAINT FLASH B2',b'SRAM FLASH B2',b'WORK FLASH B2',b'EDU FLASH B2']) and text.endswith(b'B3> '),text
    (OUT/'candidate-APPS.txt').write_bytes(text);passed('APPS discovers all four flash utilities and returns through native inventory')
    command(cpu,m,b'B0\r');zp=bytes(m.ram[0xD0:0xE0]);text=command(cpu,m,b'APPS\r')
    assert text.endswith(b'B0> ') and bytes(m.ram[0xD0:0xE0])==zp,text[-500:]
    command(cpu,m,b'B3\r');passed('APPS preserves the selected data-view bank and application zero page')
    text=command(cpu,m,b'R SRAM\rG CLK\r');assert b'CLOCK 1.8' in text and m.bank==3,text[-500:]
    command(cpu,m,b'Q\r');assert snapshot(m)==before and not m.events
    passed('XIP SRAM G CLK restores and executes the actual retained CLOCK image without changing storage')
    # Load WORK bootstrap through its real dispatcher, then call from all banks.
    command(cpu,m,b'R WORK\rQ\r')
    for bank in range(4):
        status,r=api(cpu,m,req(0),bank);assert status==0,(bank,status,r.hex())
    old_array=bytes(m.spi.devices[0].data)
    status,r=api(cpu,m,req(1,size=64))
    if status==0x49:
        assert api(cpu,m,req(7,key=b'UPGRADE!'))[0]==0
        assert bytes(m.spi.devices[0].data[0x800:])==old_array[0x800:]
    status,r=api(cpu,m,req(1,size=64));assert status==0,(status,r.hex())
    handle=r[4:12];pattern=bytes(range(64));m.ram[0x2300:0x2340]=pattern
    assert api(cpu,m,req(4,handle=handle,count=64))[0]==0
    m.ram[0x2300:0x2340]=bytes(64);assert api(cpu,m,req(3,handle=handle,count=64))[0]==0 and bytes(m.ram[0x2300:0x2340])==pattern
    assert api(cpu,m,req(3,handle=handle,count=1,buffer=0x5000))[0]==0x44
    assert api(cpu,m,req(2,handle=handle))[0]==0
    passed('WORK 5003 compatibility stub: all caller banks restored, claim/write/read/release and stub-overlap refusal')
    # Separate model, mutating only simulated B1; fetch-while-busy assertions in
    # the existing memory model ensure flash mutation stays in the RAM worker.
    cpu,m=fixture();pattern=bytes((i*7)&255 for i in range(4096));m.banks[0][:4096]=pattern
    print('CHECK MAINT cross-bank copy and flash worker',flush=True)
    text=command(cpu,m,b'R MAINT\rC 0 8 1 8\rY\r');assert b'VERIFIED' in text and bytes(m.banks[1][:4096])==pattern,text[-700:]
    text=command(cpu,m,b'V 0 8 1 8\r');assert b'MATCH' in text,text[-700:]
    payload=bytes(range(32));record=b'SR\x01\x3f\x00\x22'+len(payload).to_bytes(2,'little')+b'TEST'.ljust(16,b'\0')+payload
    m.banks[1][0x4000:0x4000+len(record)]=record
    text=command(cpu,m,b'X 1 TEST S TESTCOPY\rY\r');assert b'Copied and verified' in text,text[-700:]
    text=command(cpu,m,b'X S TESTCOPY 1 RETURNED\rY\r');assert b'Copied and verified' in text and b'Destination B01:9000' in text,text[-700:]
    assert bytes(m.banks[1][0x1018:0x1018+32])==payload
    before2=[bytes(b) for b in m.banks];text=command(cpu,m,b'E 2 8\r');assert [bytes(b) for b in m.banks]==before2 and b'WRITE?' not in text and (b'PROTECTED' in text or b'CANCELED' in text),text[-700:]
    command(cpu,m,b'Q\r');passed('MAINT cross-bank copy/compare runs with RAM flash workers; executing B2 bundle protected')
    for fault in ('crc','header'):
        print('CHECK sealed bundle refusal',fault,flush=True);cpu,m=fixture(corrupt=fault);before2=snapshot(m)
        text=command(cpu,m,b'R EDU\r');assert b'EDU 1.3' not in text and text.endswith(b'B3> '),text[-500:]
        assert snapshot(m)==before2 and not m.events
    passed('CRC-corrupt and resealed wrong-header bundles refuse execution with no data changes')
    cpu,m=fixture(key=b'B');assert b'2.0b27' in m.tx
    assert b'EDU 1.3' in command(cpu,m,b'R EDU\r');command(cpu,m,b'Q\r')
    passed('preserved beta27 monitor can launch candidate flash utilities through unchanged extension entry points')
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-beta27/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    report=dict(passed=True,checks=checks,utility_sha256=X['sha256'],build_sha256=__import__('hashlib').sha256((OUT/'build.json').read_bytes()).hexdigest(),artifacts=META['artifacts'],board_access=False,boards_flashed=False,hardware_tested=False)
    (OUT/'beta28-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
