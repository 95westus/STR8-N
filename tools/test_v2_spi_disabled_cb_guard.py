"""Execute a narrowly guarded disabled-CB acknowledgment policy in a model."""
import argparse,hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from test_v2_rtc import MPU

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/spi-disabled-cb-guard'

class Memory:
    def __init__(self,body,ifr,ier,pcr,acr,ddr,clear=True,entry=0x2000):
        self.ram=bytearray(65536);self.ram[entry:entry+len(body)]=body
        self.ifr=ifr;self.ier=ier;self.pcr=pcr;self.acr=acr;self.ddr=ddr;self.clear=clear
        self.port_reads=0;self.hardware_writes=[]
    def __getitem__(self,a):
        if a==0x7FCD:return self.ifr
        if a==0x7FCE:return self.ier
        if a==0x7FCC:return self.pcr
        if a==0x7FCB:return self.acr
        if a==0x7FC2:return self.ddr
        if a==0x7FC0:
            self.port_reads+=1
            if self.clear:self.ifr&=~0x18
            return 255
        return self.ram[a]
    def __setitem__(self,a,v):
        if 0x7FC0<=a<=0x7FCF:self.hardware_writes.append((a,v))
        self.ram[a]=v

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path);a=p.parse_args()
    target=OUT;meta=None;entry=0x2000
    if a.build:
        target=ROOT/a.build;meta=json.loads((target/'build.json').read_text());s=meta['status_symbols']
        assert meta['spi_startup_disabled_cb_ack']
        asset=(target/'boot-status/asset.bin').read_bytes();base=meta['status_ram_base']
        body=asset[s['SPI_STARTUP_GUARD']-base:s['SPI_STARTUP_REFUSE']-base+5]
        entry=s['SPI_STARTUP_GUARD']
        source=(target/'storage-status/source/storage-status.asm').read_text()
        scope=source[source.index('        BPL SM_HEADER'):source.index('SPI_STARTUP_DONE:\n')]
        assert 'LDA KIND' in scope and 'BNE SPI_STARTUP_DONE' in scope and 'JSR SPI_STARTUP_GUARD' in scope
        assert source.index('        BPL SM_HEADER') < source.index('        JSR SPI_STARTUP_GUARD') < source.index('BACKUP:')
    else:
        OUT.mkdir(exist_ok=True);(OUT/'asm').mkdir(exist_ok=True);compiler.OUT=OUT;compiler.SOURCE=ROOT/'tools/v2-spi'
        cells,s=compiler.assemble('spi-disabled-cb-guard',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=compiler.SOURCE)
        body=compiler.dense_image(cells,0x2000,s['APP_END'])
    results=[]
    cases=[('observed 2609 idle state',0x1A,0x80,0,0,0,True,0,1,2),
           ('no CB pending; no acknowledgment',2,0x80,0,0,0,True,0,0,2),
           ('CB1 IRQ enabled',0x1A,0x90,0,0,0,True,1,0,0x1A),
           ('CB2 IRQ enabled',0x1A,0x88,0,0,0,True,1,0,0x1A),
           ('CB IRQ owner without pending flag',2,0x90,0,0,0,True,1,0,2),
           ('CB handshake owner',0x1A,0x80,0x80,0,0,True,1,0,0x1A),
           ('independent CB input mode',0x1A,0x80,0x20,0,0,True,1,0,0x1A),
           ('shift-register owner',0x1A,0x80,0,4,0,True,1,0,0x1A),
           ('port B latch owner',0x1A,0x80,0,2,0,True,1,0,0x1A),
           ('SPI pin driven',0x1A,0x80,0,0,4,True,1,0,0x1A),
           ('flags fail to clear',0x1A,0x80,0,0,0,False,1,1,0x1A)]
    for name,ifr,ier,pcr,acr,ddr,clear,status,reads,after in cases:
        for initial_p in (0x20,0x24,0x28,0x2C):
            mem=Memory(body,ifr,ier,pcr,acr,ddr,clear,entry=entry);cpu=MPU(memory=mem,pc=entry)
            cpu.p=initial_p;sp=cpu.sp;cpu.stPushWord(0x1FF)
            for _ in range(500):
                if cpu.pc==0x200:break
                cpu.step()
            else:raise AssertionError('guard did not return')
            assert cpu.sp==sp and cpu.a==status and bool(cpu.p&cpu.CARRY)==(status==0)
            assert cpu.p&0x0C==initial_p&0x0C
            assert mem.ifr==after and mem.port_reads==reads and not mem.hardware_writes
            assert (mem.ier,mem.pcr,mem.acr,mem.ddr)==(ier,pcr,acr,ddr)
        results.append(name)
    if meta:
        for address in (0x6660,0x6669):
            mem=Memory(body,0x1A,0x80,0,0,0,entry=entry);mem.ram[address]=1
            cpu=MPU(memory=mem,pc=entry);cpu.stPushWord(0x1FF)
            for _ in range(500):
                if cpu.pc==0x200:break
                cpu.step()
            assert cpu.pc==0x200 and cpu.a==1 and not(cpu.p&cpu.CARRY)
            assert mem.ifr==0x1A and mem.port_reads==0 and not mem.hardware_writes
        results.append('both resident busy owners refused without acknowledgment')
    executed_cases=len(cases)*4+(2 if meta else 0)
    report=dict(passed=True,executed_cases=executed_cases,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),checks=results,
        active_irq_and_owner_refusals_preserved=True,non_cb_flags_preserved=True,board_access=False,
        installed=False,hardware_qualification_pending=True)
    if meta:report.update(status_asset_sha256=meta['status_asset_sha256'],artifacts=meta['artifacts'],cold_boot_only=True)
    (target/('spi-startup-test-results.json' if meta else 'test-results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('PASS disabled-CB guard:',executed_cases,'executed cases; no hardware register writes, active owners refused')

if __name__=='__main__':main()
