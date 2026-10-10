"""Execute EDU reset latch, saved utility, free-RAM guards and failures."""
import hashlib,json
from beta4_migration import metadata,default_config,config_sum,journal
from test_v2_spi_resident import Memory,k,OUT
from test_v2_sram_store import console
from test_v2_workspace import install as load_work,call,req
META=json.loads((OUT/'build.json').read_text());UTILITY=(OUT/'edu/edu.bin').read_bytes()
def boot(off=False,promoted=False,invalid=False,missing=False):
    m=Memory();config=bytearray(default_config());config[13]=0xA5 if off else 0
    if promoted:config[7:13]=b'P\xA0'+META['generation'].to_bytes(4,'little')
    config[14:]=config_sum(config)
    if invalid:config[14]^=1
    m.banks[3][0x4000:0x6000]=metadata(config,[0]*32,1)+b'\xff'*(8192-128)
    if missing:m.bus.devices.pop(0x6F);m.spi.devices.clear()
    cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu;m.spi.cpu=cpu
    k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    return cpu,m
def utility(cpu,m,keys):
    m.ram[0x2000:0x2000+len(UTILITY)]=UTILITY
    return console(cpu,m,keys,entry=0x2000,limit=30000000)
def reset(cpu):
    cpu.pc=0xF004;k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
def saved(m):return journal(bytes(m.banks[3]))[8:24]
def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=boot(off=True);area=bytes(m.ram[0x6500:0x6700])
    assert area==b'\x5A'*512 and m.ram[0x7D04:0x7D0C]==b'SV\x01\0\0\0\xff\x66'
    assert m.ram[0x7D0C]==0 and m.ram[0x7D27:0x7D29]==b'\x02\xA5'
    assert b'EDU: OFF; RAM top $66FF' in bytes(m.tx) and not m.spi.frames
    output=k.model.command(cpu,b'TIME\r');assert b'RTCC: unavailable' in output and bytes(m.ram[0x6500:0x6700])==area
    load_work(cpu,m);m.fast=True;assert call(cpu,m,req(0))[0]==0x80 and bytes(m.ram[0x6500:0x6700])==area
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    passed('cold OFF leaves all 512 bytes untouched, clears service capabilities, publishes 66FF and refuses WORK/TIME safely')
    program=bytes.fromhex('A9 46 20 6D 7E 20 7F 7E 4C 67 7E')
    for i in range(0,len(program),8):assert b'Bad' not in k.model.command(cpu,f'M {0x6500+i:04X} '.encode()+b' '.join(f'{v:02X}'.encode() for v in program[i:i+8])+b'\r')
    output=k.model.command(cpu,b'G 6500\r');assert b'\r\nF\r\n' in output and m.ram[0x6500:0x650B]==program,(output[-400:],m.ram[0x6500:0x650B].hex())
    output=k.model.command(cpu,b'S 2 D000 6500 650A FREERAM\r');assert b'Done' in output,output[-500:]
    m.ram[0x6500:0x650B]=bytes(11)
    assert b'\r\nF\r\n' in k.model.command(cpu,b'R 2 FREERAM\r') and m.ram[0x6500:0x650B]==program
    area=bytes(m.ram[0x6500:0x6700]);output=utility(cpu,m,b'ON\rY\r?\rQ\r')
    assert b'Saved; RESET required.' in output and b'EDU active: OFF' in output and b'EDU saved: ON' in output
    assert bytes(m.ram[0x6500:0x6700])==area and m.ram[0x7D07]==0
    reset(cpu);assert m.ram[0x7D07]==15 and m.ram[0x7D0A:0x7D0C]==b'\xff\x64' and m.ram[0x7D27]==1
    area=bytes(m.ram[0x6500:0x6700]);output=k.model.command(cpu,b'R 2 FREERAM\r')
    assert b'\r\nF\r\n' not in output and bytes(m.ram[0x6500:0x6700])==area
    passed('OFF permits reclaimed-RAM edit/run/flash save/restore; saved ON changes only at RESET and then rejects the high-RAM image')
    for promoted in (False,True):
        cpu,m=boot(promoted=promoted);area=bytes(m.ram[0x6500:0x6700]);flash=[bytes(b) for b in m.banks]
        output=utility(cpu,m,b'OFF\r\rOFF\rNO\rOFF\rYES\rON X\rQ\r')
        assert output.count(b'Canceled.')==3 and [bytes(b) for b in m.banks]==flash
        output=utility(cpu,m,b'OFF\rY\r?\rQ\r');assert b'EDU active: ON' in output and b'EDU saved: OFF' in output
        assert saved(m)[13]==0xA5 and bytes(m.ram[0x6500:0x6700])==area and m.ram[0x7D07]==15
        output=k.model.command(cpu,b'C 0 3 F007 0A\rY\r');assert b'Done' in output and saved(m)[13]==0xA5
        output=k.model.command(cpu,b'P B\r');assert saved(m)[13]==0xA5
        reset(cpu);assert m.ram[0x7D07]==0 and m.ram[0x7D0A:0x7D0C]==b'\xff\x66'
    passed('blank/wrong confirmation cancels; active ON persists until RESET; C edits and P promotion preserve saved mode with/without prior preference')
    cpu,m=boot(off=True,invalid=True);assert m.ram[0x7D27]==1 and m.ram[0x7D0A:0x7D0C]==b'\xff\x64'
    cpu,m=boot(missing=True);assert m.ram[0x7D27]==1 and m.ram[0x7D0A:0x7D0C]==b'\xff\x64'
    passed('invalid configuration checksum and missing RTC/SRAM keep fail-safe ON reservation; hardware failures never release RAM')
    (OUT/'edu-mode-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],utility_sha256=hashlib.sha256(UTILITY).hexdigest(),board_access=False),indent=2)+'\n')
if __name__=='__main__':main()
