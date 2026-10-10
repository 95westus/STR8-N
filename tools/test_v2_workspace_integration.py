"""Real resident SPI integration, runnable cache example and transfer costs."""
import hashlib,json
from test_v2_workspace import fresh,install,call,req,OUT,META,ROOT,k,STACK
from test_v2_sram_store import console

def main():
    cpu,m=fresh(fast=False);before=[bytes(b) for b in m.banks];ee=bytes(m.bus.ee);rtc=bytes(m.bus.rtc_regs)
    measurements=[]
    def measured(r,label):
        cycles=cpu.processorCycles;frames=len(m.spi.frames)
        status,result=call(cpu,m,r,limit=30000000)
        measurements.append(dict(operation=label,cycles=cpu.processorCycles-cycles,
            frames=len(m.spi.frames)-frames,clocked_bytes=sum(len(f['tx']) for f in m.spi.frames[frames:])))
        assert status==0,(label,status)
        return result
    h=measured(req(1,owner=0xBEEF,size=64),'claim64')[4:12]
    m.ram[0x2300:0x2310]=bytes(range(16))
    measured(req(4,owner=0xBEEF,handle=h,count=16),'verified_write16')
    m.ram[0x2300:0x2310]=bytes(16)
    measured(req(3,owner=0xBEEF,handle=h,count=16),'read16')
    assert m.ram[0x2300:0x2310]==bytes(range(16))
    measured(req(2,owner=0xBEEF,handle=h),'release')
    for bank,bits in enumerate((0xCC,0xCE,0xEC,0xEE)):
        pcr=(m.ram[0x7FEC]&0x11)|bits;m[0x7FEC]=pcr
        measured(req(0),f'query_bank{bank}')
        assert m.ram[0x7FEC]==pcr
    m[0x7FEC]=(m.ram[0x7FEC]&0x11)|0xEE
    if META['entry']==0x5000:
        program=bytes((i*37+i//256)&255 for i in range(0x4E00));m.ram[0x200:0x5000]=program
        measured(req(0),'query_with_full_lower_application')
        assert m.ram[0x200:0x2200]==program[:0x2000]
        assert m.ram[0x2220:0x5000]==program[0x2020:]
        print('PASS WORK query preserves $0200-$4FFF except its explicit caller request block',flush=True)
    print('PASS actual resident SPI claim, verified WRITE, READ and release',flush=True)
    example=OUT/'example';em=json.loads((example/'build.json').read_text());body=(example/'example.bin').read_bytes()
    m.ram[0x2000:0x2000+len(body)]=body;cycles=cpu.processorCycles;f=len(m.spi.frames)
    output=console(cpu,m,entry=0x2000,limit=100000000)
    assert b'W: 00' in output and b'B3> ' in output,output[-300:]
    table=em['symbols']['TABLE'];expected=m.ram[table:table+64]
    assert m.spi.devices[0].data[0x10000:0x10040]==expected
    assert m.ram[0x2500:0x2510]==expected[48:64]
    measurements.append(dict(operation='cache_example_4writes_4reads',cycles=cpu.processorCycles-cycles,
        frames=len(m.spi.frames)-f,clocked_bytes=sum(len(frame['tx']) for frame in m.spi.frames[f:])))
    assert before==[bytes(b) for b in m.banks] and ee==bytes(m.bus.ee) and rtc==bytes(m.bus.rtc_regs)
    assert not m.ram[0x6660] and not m.ram[0x6669] and m.ram[0x66AE]==1
    old=bytes(m.spi.devices[0].data);install(cpu,m)
    output=console(cpu,m,b'?\rP 32\rNO\rF\rYES\rQ\r',entry=META['entry'],limit=30000000)
    assert b'Programs: 64 KiB; workspace: 65504 bytes' in output and output.count(b'Canceled.')==2 and b'B3> ' in output
    assert bytes(m.spi.devices[0].data)==old
    print('PASS runnable two-row RAM cache backed by eight-row SPI metadata table; flash/RTC/EEPROM preserved',flush=True)
    report=dict(passed=True,workspace_sha256=META['sha256'],example_sha256=em['sha256'],resident_artifacts=k.REPORT['artifacts'],
        measurements=measurements,max_stack_bytes=STACK[0],cache_bytes=16,request_bytes=32,example_bytes=len(body),hardware_tested=False,board_access=False)
    (OUT/'integration-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
