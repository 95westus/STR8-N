"""CPU/NOR tests of linked prototype components; no device or serial module."""
import argparse,binascii,json,sys
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816')]
from py65.devices.mpu65c02 import MPU as CPU02
from py65816.devices.mpu65c816 import MPU as CPU816
from installer.flash_model import Memory as NOR
from test_monitor_size import fast_crc
from str8build.formats import save,sha
from prepare_monitor_size import offline,ATTEMPTS
offline()
GENERATION=0x80000001

def crc(data):return binascii.crc_hqx(bytes(data),65535)
def record(seq=1,target='S',counts=None,mask=15,pages=(8,8,8,8)):
    r=bytearray(b'\xff'*256);r[:8]=b'SNBT\x01\x20\0'+target.encode();r[8:12]=seq.to_bytes(4,'little')
    r[12:18]=bytes([30,mask,*pages]);r[18:22]=GENERATION.to_bytes(4,'little');r[22:30]=bytes(8)
    r[32:48]=bytes([1,0,3,7,240,10,0,ord('P'),0xb0,1,0,0,128,0xa5,0,0])
    for n,v in enumerate(counts or [1]*32):r[64+3*n:67+3*n]=v.to_bytes(3,'little')
    r[160:168]=bytes(8)
    return seal(r)
def seal(r):
    r=bytearray(r);r[30:32]=crc(r[:30]).to_bytes(2,'little');r[252:254]=crc(r[:252]).to_bytes(2,'little');r[255]=0;return bytes(r)
class Memory(NOR):
    def __init__(self,banks,dual=False):
        super().__init__(banks);self.snapshots=[];self.dual=dual
        self.acia_rx=deque();self.acia_tx=bytearray();self.acia_writes=[];self.acia_wire=deque();self.acia_latch=None;self.acia_error=0;self.acia_overruns=0
        self.ft_tx_blocked=False;self.acia_tx_blocked=False
        self.ft_block_after=None
        self.acia_tdre=0
    def acia_tick(self):
        while self.acia_wire and self.cpu.processorCycles>=self.acia_wire[0][0]:
            _,byte,error=self.acia_wire.popleft()
            if self.acia_latch is None:self.acia_latch=byte;self.acia_error|=error
            else:self.acia_error|=4;self.acia_overruns+=1
    def __getitem__(self,a):
        if self.dual:
            if a==0x7fe0:
                value=super().__getitem__(a)
                return value|(1 if self.ft_tx_blocked or not self.usb else 0)
            if a==0x7f81:
                self.acia_tick()
                return self.acia_tdre|self.acia_error|(8 if self.acia_rx or self.acia_latch is not None else 0)
            if a==0x7f80:
                self.acia_tick()
                value=self.acia_latch if self.acia_latch is not None else (self.acia_rx.popleft() if self.acia_rx else 0)
                self.acia_latch=None;self.acia_error=0;return value
        return super().__getitem__(a)
    def __setitem__(self,a,v):
        if self.dual:
            if a==0x7f81:self.acia_error=0
            if a==0x7f80:
                cycle=self.cpu.processorCycles
                if self.acia_writes:assert cycle-self.acia_writes[-1][0]>=4167,'ACIA transmit pacing too short'
                self.acia_writes.append((cycle,v&255))
                if not self.acia_tx_blocked:self.acia_tx.append(v&255)
                self.ram[a]=v&255;return
        super().__setitem__(a,v)
        if self.dual and self.ft_block_after is not None and len(self.tx)>=self.ft_block_after:self.ft_tx_blocked=True
    def mutated(self,kind,address,value):
        assert self.bank==3 and 0xc000<=address<0xe000,(kind,self.bank,hex(address))
        if kind=='erase':
            valid=[]
            for page in range(0xc0,0xe0):
                r=bytes(self.banks[3][(page-0x80)*256:(page-0x80)*256+256])
                if r[255]==0 and crc(r[:252])==int.from_bytes(r[252:254],'little'):valid.append(r)
            latest=max(valid,key=lambda r:int.from_bytes(r[8:12],'little'));index=24+(address>>12)-8
            assert int.from_bytes(latest[64+index*3:67+index*3],'little')>=2,'Erase lacked a durable attempt reservation'
        self.events.append((kind,self.bank,address,value));self.snapshots.append(bytes(self.banks[3][0x4000:0x6000]))
class Machine:
    def __init__(self,build,cpu,rows=(),ram_config=False,opaque=False):
        self.sy=json.loads((build/'symbols.json').read_text());self.b=self.sy['core/str8n-v2-boot'];self.w=self.sy['core/str8n-v2-worker'];self.name=cpu
        banks=[bytearray(b'\xff'*32768) for _ in range(4)]
        if not opaque:
            base=(ROOT/'BUILD/rc1-r10p2-g0034/firmware.bin').read_bytes()
            for n in range(3):banks[n+1][:]=base[n*32768:(n+1)*32768]
            # Other components have not been relinked to the new private ABI.
            banks[2][:]=b'\xff'*32768
            banks[3][0x6000:0x7000]=b'\xff'*4096
            for page in (0xa0,0xb0):banks[3][(page-0x80)*256:(page-0x70)*256]=(build/f'payload/monitor-{page:02x}-offline-component.bin').read_bytes()
        banks[3][0x4000:0x6000]=b'\xff'*8192
        for address,row in rows:banks[3][address-0x8000:address-0x8000+256]=row
        banks[3][-4096:]=(build/'payload/f-offline-component.bin').read_bytes()
        build_info=json.loads((build/'prototype-report.json').read_text());self.dual=build_info.get('dual_console',False);self.bench=build_info.get('bench_core',False);self.startup=build_info.get('startup_drain',False)
        self.m=Memory(list(map(bytes,banks)),dual=self.dual);self.c=(CPU02 if cpu=='65c02' else CPU816)(memory=self.m,pc=0xf004);self.m.cpu=self.c;self.c.p=0x24;self.c.sp=255
        self.accelerate_crc=True;self.accelerate_acia=True
        self.steps=0;self.run(lambda:self.c.pc==self.b['BOOT_START_CHOICES'])
        self.m.ram[0xf3]=3
        if ram_config:self.m.ram[0x2000:0x2000+(build/'payload/ram-config-offline.bin').stat().st_size]=(build/'payload/ram-config-offline.bin').read_bytes()
    def run(self,stop,limit=4000000):
        for _ in range(limit):
            if stop():return
            c,m=self.c,self.m;self.steps+=1
            # Non-timing regression shortcut, only for a completely empty
            # receiver. The dedicated startup suite executes every opcode and
            # checks this exact empty-path cycle count and register result.
            if (self.startup and c.pc==self.b['BOOT_DRAIN_BEGIN'] and not m.rx
                    and not m.acia_rx and not m.acia_wire and m.acia_latch is None):
                c.processorCycles+=8000495;c.a=c.x=c.y=0;c.p=(c.p&~0xC2)|2|(m[0x7fe0]&0x40)
                m.ram[self.b['BR_TICKS']]=0;c.pc=self.b['BOOT_DRAIN_DONE'];continue
            if c.pc==self.b['J_CRC_BYTE'] and m.bank==3 and self.accelerate_crc:fast_crc(c,m,0x7d38);continue
            if self.dual and self.accelerate_acia and c.pc==self.w['V2W_ACIA_DELAY_OUTER']:
                c.processorCycles+=4183;c.a=0;c.p=(c.p&~0x82)|2;c.pc=self.w['V2W_ACIA_SEND']+14;continue
            if c.pc==self.w['V2W_BOOT_DELAY_OUTER']:c.pc=self.w['V2W_BOOT_DELAY_DONE'];continue
            op=m[c.pc]
            if self.name=='65c02' and op&15==15:
                pc=c.pc;bit=bool(m[m[(pc+1)&65535]]&(1<<((op>>4)&7)));take=bit if op&128 else not bit;d=m[(pc+2)&65535];c.pc=(pc+3+((d if d<128 else d-256) if take else 0))&65535
            else:c.step()
        raise AssertionError(('timeout',self.name,hex(c.pc),bytes(m.tx[-160:])))
    def call(self,entry,a=0):
        self.c.pc=entry;self.c.a=a;self.c.sp=255;self.c.p=0x24;self.c.stPushWord(0x1ff)
        self.run(lambda:self.c.pc==0x200);return bool(self.c.p&1)
    def recovery(self):
        self.c.pc=self.b['BOOT_RECOVERY'];self.run(lambda:bytes(self.m.tx).endswith(b'REC> '))
    def command(self,data,ending=b'REC> '):
        n=len(self.m.tx);self.m.rx.extend(data);self.run(lambda:len(self.m.tx)>n and bytes(self.m.tx).endswith(ending));return bytes(self.m.tx[n:])
    def port_command(self,port,data,ending=b'REC> ',timed=False):
        tx=self.m.tx if port==1 else self.m.acia_tx;n=len(tx)
        if timed:
            now=self.c.processorCycles+200
            self.m.acia_wire.extend((now+i*4167,v,0) for i,v in enumerate(data))
        else:(self.m.rx if port==1 else self.m.acia_rx).extend(data)
        self.run(lambda:len(tx)>n and bytes(tx).endswith(ending));return bytes(tx[n:])

def header(body,address=0x2000,entry=None):
    h=b'RLP1\x01\x01'+address.to_bytes(2,'little')+len(body).to_bytes(2,'little')+(address if entry is None else entry).to_bytes(2,'little')+crc(body).to_bytes(2,'little')
    return h+crc(h).to_bytes(2,'little')

def console_tests(build,cpu,passed):
    # Every monitor thunk and direct F entry uses the same contract. Compare
    # parsers to the actual previous linked instructions, including failures.
    baseline=ROOT/'BUILD/boot-record-v2-prototype-final'
    for module in ('core/str8n-v2-boot','core/monitor-a0','core/monitor-b0'):
        h=Machine(build,cpu,opaque=module.endswith('boot'));before=bytes(h.m.ram[0x200:0x6500])
        old=Machine(baseline,cpu);newsy=h.sy[module];oldsy=old.sy['core/monitor-a0']
        for parser in ('HEX_WORD','HEX_BYTE','SKIP_SPACES'):
            name=('BOOT_API_' if module.endswith('boot') else 'V2_')+('SKIP' if parser=='SKIP_SPACES' and module.endswith('boot') else parser)
            comparisons=0
            for token in (b'',b'0',b'F',b'00FF',b'FFFF',b'1234 ',b'12345',b'100',b'0x10',b'G',b' 12 Z',b'   ',b'ffff'):
                for offset in (0,2):
                    line=b'Z '*bool(offset)+token+b'\0'
                    for machine,entry in ((h,newsy[name]),(old,oldsy['V2_'+parser])):
                        machine.m.ram[0x7c00:0x7c00+len(line)]=line;machine.m.ram[0xe8:0xea]=b'\x5a\xa5';machine.c.x=offset
                        ok=machine.call(entry)
                        result=(ok,machine.c.x,bytes(machine.m.ram[0xe8:0xea]))
                        if machine is h:actual=result
                        else:assert actual==result,(cpu,module,parser,line,actual,result)
                    comparisons+=1
            passed(cpu,'shared-'+module.rsplit('/',1)[1]+'-'+parser,comparisons=comparisons)
        assert before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
        line_entry=newsy['BOOT_API_LINE' if module.endswith('boot') else 'V2_READ_LINE']
        cases=[('CR',b'ab\r',b'AB',b'ab\r\n',0),('LF',b'ab\n',b'AB',b'ab\r\n',0),('CRLF',b'ab\r\n',b'AB',b'ab\r\n',0),('editing',b'ab\x08c\x7fd\t1\r',b'AD 1',b'ab\x08 \x08c\x08 \x08d 1\r\n',0),('full',b'x'*40+b'\r',b'X'*40,b'x'*40+b'\r\n',0),('overflow',b'x'*41+b'\r',b'X'*40,b'x'*40+b'\r\n',1),('invalid-control',b'L\x01junk\r',b'L',b'L\r\n',2),('invalid-high',b'L\xffjunk\r',b'L',b'L\r\n',2),('escape',b'ab\x1b',b'',b'ab\r\n',3),('ctrl-C',b'ab\x03',b'',b'ab\r\n',3)]
        for label,data,want,echo,status in cases:
            h.m.rx.clear();h.call(h.w['V2W_RX_RESET']);h.m.ram[0xec]=0 # V2_SKIP_LF
            h.m.rx.extend(data);n=len(h.m.tx);ok=h.call(line_entry)
            assert ok==(status==0) and h.c.y==status,(module,label,ok,h.c.y)
            assert h.c.x==len(want) and bytes(h.m.ram[0x7c00:0x7c01+len(want)])==want+b'\0'
            assert bytes(h.m.tx[n:])==echo,(module,label,bytes(h.m.tx[n:]),echo)
            assert before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
            passed(cpu,'shared-'+module.rsplit('/',1)[1]+'-line-'+label)
        h.m.rx.clear();h.call(h.w['V2W_RX_RESET']);h.m.rx.extend(b'a\r\nb\nc\r\n')
        for expected in (b'A',b'B',b'C'):
            assert h.call(line_entry);assert bytes(h.m.ram[0x7c00:0x7c02])==expected+b'\0'
        passed(cpu,'shared-'+module.rsplit('/',1)[1]+'-paired-line-endings')
        h.m.rx.clear();h.call(h.w['V2W_RX_RESET']);h.m.ram[0xec]=0;h.m.ram[0xf1]=1 # V2_RX_BAD
        h.m.rx.extend(b'L\r');assert not h.call(line_entry) and h.c.y==2 and h.m.ram[0xf1]==0
        assert h.m.ram[0x7c00]==0 and before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
        passed(cpu,'shared-'+module.rsplit('/',1)[1]+'-sticky-RX-error')
    # Reject complete malformed lines, never a prefix that could run a command.
    h=Machine(build,cpu,opaque=True);h.recovery()
    for malformed in (b'L'+b'x'*40+b'\r',b'L\x01\r',b'L\xff\r',b'R\x1b'):
        out=h.command(malformed);assert b'REFUSED: command' in out and b'SEND HEADER' not in out and not h.m.events
    passed(cpu,'shared-recovery-rejects-malformed-prefixes',comparisons=4)
    h=Machine(build,cpu,ram_config=True,opaque=True);h.c.pc=0x2000;prompt=b'CONFIG prototype I(blank only) W C target Q> '
    h.run(lambda:bytes(h.m.tx).endswith(prompt))
    for malformed in (b'I'+b'x'*40+b'\r',b'I\x01\r',b'I\xff\r',b'I\x1b'):
        out=h.command(malformed,prompt);assert b'REFUSED' in out and not h.m.events
    passed(cpu,'shared-CONFIG-rejects-malformed-prefixes',comparisons=4)
    # These services execute from RAM: F may be completely invisible.
    for bank,bits in enumerate((0xcc,0xce,0xec,0xee)):
        h=Machine(build,cpu,opaque=True);before=bytes(h.m.ram[0x200:0x6500]);h.m[0x7fec]=(h.m.ram[0x7fec]&0x11)|bits;pcr=h.m.ram[0x7fec]
        def call(address,a=0):
            h.c.x=0x35;h.c.y=0x79;ok=h.call(address,a)
            assert h.c.x==0x35 and h.c.y==0x79 and h.m.bank==bank and h.m.ram[0x7fec]==pcr
            return ok
        call(0x7e6a);call(0x7e79);n=len(h.m.tx);call(0x7e6d,ord('z'));assert bytes(h.m.tx[n:])==b'z'
        h.m.rx.extend(b'x');call(0x7e70);assert h.c.a==ord('x')
        assert not call(0x7e73)
        for byte in (0,3,10,13,255):
            h.m.rx.append(byte);assert call(0x7e73) and h.c.a==byte
        h.m.rx.extend(b'queued\x03');assert call(0x7e76);call(0x7e70);assert h.c.a==3
        assert not call(0x7e76)
        h.m.rx.extend(b'queued');assert not call(0x7e76);call(0x7e79)
        h.m.rx.append(ord('Q'));call(0x7e70);assert h.c.a==ord('Q')
        n=len(h.m.tx);call(0x7e7f);assert bytes(h.m.tx[n:])==b'\r\n'
        assert before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
        passed(cpu,'RAM-console-visible-bank-'+str(bank),services=['CON_INIT','PUTC','GETC','RAW_POLL','CHECK_CANCEL','RX_RESET','NEWLINE'])

def dual_tests(build,cpu,passed):
    def fresh():
        h=Machine(build,cpu,opaque=True);h.recovery();h.run(lambda:h.c.pc==h.w['V2W_GETC'])
        assert h.m.ram[0x7d02]==3 and bytes(h.m.tx)==bytes(h.m.acia_tx)
        assert h.m.ram[0x7f82:0x7f84]==bytes([0x0b,0x1f])
        return h
    h=fresh();passed(cpu,'dual-startup-both-initialized-and-mirrored')
    h=Machine(build,cpu,opaque=True);h.run(lambda:bytes(h.m.tx).endswith(b'REC> ') and bytes(h.m.acia_tx).endswith(b'REC> '))
    assert bytes(h.m.tx)==bytes(h.m.acia_tx) and b'OFFLINE PROTOTYPE' in h.m.tx and not h.m.events
    passed(cpu,'dual-actual-startup-choice-and-recovery-output-both')
    for port in (1,2):
        h=fresh();before=bytes(h.m.ram[0x200:0x6500]);queue=h.m.rx if port==1 else h.m.acia_rx
        queue.extend(b'abc\r\ndef\n')
        for expected in (b'ABC',b'DEF'):
            assert h.call(h.b['BOOT_API_LINE']) and bytes(h.m.ram[0x7c00:0x7c04])==expected+b'\0'
        assert bytes(h.m.tx)==bytes(h.m.acia_tx) and before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
        passed(cpu,'dual-text-and-echo-port-'+str(port))
        h=fresh();queue=h.m.rx if port==1 else h.m.acia_rx;queue.extend(b'ab')
        assert h.call(h.w['V2W_CHKC']) and h.m.ram[0xf9]==1
        assert h.call(h.w['V2W_CHKC']) and h.m.ram[0xf9]==2
        assert h.call(h.w['V2W_CON_POLL']) and h.c.a==ord('a')
        h.call(h.w['V2W_GETC']);assert h.c.a==ord('b')
        assert not h.call(h.w['V2W_CHKC']) and not h.call(h.w['V2W_CON_POLL'])
        passed(cpu,'dual-CHKC-POLL-GETC-port-'+str(port))
    h=fresh();h.m.rx.extend(b'a\r')
    for expected in b'a\r':h.call(h.w['V2W_GETC']);assert h.c.a==expected
    h.m.acia_rx.extend(b'b\r')
    for expected in b'b\r':h.call(h.w['V2W_GETC']);assert h.c.a==expected
    passed(cpu,'dual-bare-GETC-line-boundary-port-handoff')
    h=fresh();h.m.rx.extend(b'x'*70+b'\r')
    for _ in range(65):h.call(h.w['V2W_CHKC'])
    assert h.m.ram[0xf1]==1 and not h.call(h.b['BOOT_API_LINE']) and h.c.y==2
    assert not h.m.events
    passed(cpu,'dual-software-queue-overflow-drains-and-refuses-line')
    for bank,bits in enumerate((0xcc,0xce,0xec,0xee)):
        h=fresh();h.m[0x7fec]=(h.m.ram[0x7fec]&0x11)|bits
        assert bytes(h.m.ram[0x7e5e:0x7e60])==b'DC'
        h.m.acia_rx.append(ord('z'));h.c.x=0x25;h.c.y=0x73
        assert h.call(0x7e5b) and h.c.x==0x25 and h.c.y==0x73
        assert h.call(0x7e58) and h.c.a==ord('z') and h.c.x==0x25 and h.c.y==0x73 and h.m.bank==bank
        assert h.call(0x7e85) and (h.c.a,h.c.x,h.c.y)==(1,0x17,4) and h.m.bank==bank
        h.c.pc=0x7e64;h.run(lambda:h.m.bank==3 and h.c.pc==h.b['BOOT_START_CHOICES'])
        assert h.m.ram[0x7d02]==3 and not h.m.events
        passed(cpu,'dual-public-POLL-CHKC-and-reset-bank-'+str(bank))
    for first in (1,2):
        h=fresh();h.m.ram[0x7c2c]=0 if first==1 else 1
        (h.m.rx if first==1 else h.m.acia_rx).extend(b'ab\r')
        (h.m.acia_rx if first==1 else h.m.rx).extend(b'xyz\r')
        assert h.call(h.b['BOOT_API_LINE']);assert bytes(h.m.ram[0x7c00:0x7c03])==b'AB\0'
        assert bytes(h.m.tx)==bytes(h.m.acia_tx) and not h.m.events
        passed(cpu,'dual-simultaneous-line-owner-'+str(first))
        h=fresh();(h.m.rx if first==1 else h.m.acia_rx).extend(b'ab')
        h.c.pc=h.b['BOOT_API_LINE'];h.c.sp=255;h.c.stPushWord(0x1ff)
        h.run(lambda:h.m.ram[0x7c00:0x7c02]==b'AB' and h.c.pc==h.w['V2W_GETC'])
        (h.m.acia_rx if first==1 else h.m.rx).append(3)
        h.run(lambda:h.c.pc==0x200);assert not h.c.p&1 and h.c.y==3 and not h.m.events
        passed(cpu,'dual-cancel-from-other-port-owner-'+str(first))
    for mode in (1,2,3):
        h=fresh();assert h.call(h.b['BOOT_CON_SELECT'],mode)
        before=[len(h.m.tx),len(h.m.acia_tx)];h.call(h.w['V2W_PUTC'],ord('Z'))
        assert len(h.m.tx)-before[0]==bool(mode&1) and len(h.m.acia_tx)-before[1]==bool(mode&2)
        for port in (1,2):
            if not mode&port:continue
            (h.m.rx if port==1 else h.m.acia_rx).append(ord('q'))
            assert h.call(h.w['V2W_RAW_POLL']) and h.c.a==ord('q') and h.m.ram[0x7c2a]==port
        assert h.m.ram[0x7d02]==mode
        for invalid in (0,4,255):assert not h.call(h.b['BOOT_CON_SELECT'],invalid) and h.m.ram[0x7d02]==mode
        passed(cpu,'dual-explicit-mode-'+str(mode),invalid_selections=3)
    h=fresh();before=bytes(h.m.ram[0x200:0x6500]);h.port_command(2,b'C2\r');assert h.m.ram[0x7d02]==2
    h.port_command(2,b'C3\r');assert h.m.ram[0x7d02]==3
    h.port_command(1,b'C1\r');assert h.m.ram[0x7d02]==1
    assert not h.m.events and before==bytes(h.m.ram[0x200:0x6500])
    passed(cpu,'dual-recovery-C1-C2-C3-runtime-selection')
    h=fresh();h.m.ft_tx_blocked=True;n=len(h.m.acia_tx)
    out=h.port_command(2,b'Z\r');assert b'REFUSED: command' in out and h.m.ram[0x7c2e]&1
    assert len(h.m.acia_tx)>n and not h.m.events
    passed(cpu,'dual-blocked-FT245-text-keeps-ACIA-working')
    h=fresh();h.m.usb=False;out=h.port_command(2,b'Z\r');assert b'REFUSED' in out and not h.m.events
    passed(cpu,'dual-absent-FT245-keeps-ACIA-working')
    h=fresh();h.m.acia_tx_blocked=True;n=len(h.m.tx);h.command(b'Z\r')
    assert b'REFUSED' in h.m.tx[n:] and h.m.acia_writes and not h.m.events
    passed(cpu,'dual-stalled-ACIA-wire-keeps-FT245-working',limitation='CTS/wire blockage is not software-detectable in this polling driver; timed writes continue.')
    h=fresh();h.m.ft_tx_blocked=True;h.m.rx.extend(b'D\r');n=len(h.m.acia_tx)
    h.run(lambda:bytes(h.m.acia_tx[n:]).endswith(b'REC> '))
    assert b'REFUSED: TX blocked' in h.m.acia_tx[n:] and h.m.ram[0x7c2b]==0 and not h.m.events
    passed(cpu,'dual-blocked-FT245-binary-aborts-and-restores-text')
    h=fresh();body=bytes(range(64));h.port_command(1,b'L\r',b'SEND HEADER+BIN\r\n');h.port_command(1,header(body)+body);h.run(lambda:h.c.pc==h.w['V2W_GETC'])
    n=len(h.m.tx);other=len(h.m.acia_tx);h.m.ft_block_after=n+3+17;h.m.rx.extend(b'V\r')
    h.run(lambda:bytes(h.m.acia_tx[other:]).endswith(b'REC> '))
    assert bytes(h.m.tx[n:])==b'V\r\n'+body[:17] and b'REFUSED: TX blocked' in h.m.acia_tx[other:]
    assert h.m.ram[0x7c2b]==0 and h.m.ram[0x7c78]==1
    h.m.ft_block_after=None;h.m.ft_tx_blocked=False;out=h.port_command(1,b'V\r')
    assert out==b'V\r\n'+body+crc(body).to_bytes(2,'little')+b'REC> ' and not h.m.events
    passed(cpu,'dual-mid-binary-FT245-block-aborts-then-retry-succeeds',bytes_before_block=17)
    for port in (1,2):
        for ending in (b'\r',b'\n',b'\r\n'):
            h=fresh();body=bytes(range(256))*16;original=bytes(h.m.ram[0x200:0x6500])
            h.port_command(port,b'L'+ending,b'SEND HEADER+BIN\r\n')
            other=h.m.acia_rx if port==1 else h.m.rx;noise=b'R\rC1\r\x03\x00\xff';other.extend(noise)
            out=h.port_command(port,header(body)+body)
            assert b'LOADED;' in out and h.m.ram[0x7c78]==1 and bytes(h.m.ram[0x2000:0x3000])==body
            assert bytes(other)==noise,'Binary receiver consumed the other port'
            other.clear();h.run(lambda:h.c.pc==h.w['V2W_GETC'])
            alt=h.m.acia_tx if port==1 else h.m.tx;n=len(alt)
            out=h.port_command(port,b'V'+ending)
            assert out==b'V\r\n'+body+crc(body).to_bytes(2,'little')+b'REC> ',(port,ending,out[:20],out[-40:])
            h.run(lambda:h.c.pc==h.w['V2W_GETC']);assert bytes(alt[n:])==b'V\r\nREC> '
            assert h.m.ram[0x7c2b]==0 and h.m.ram[0x7d02]==3
            assert bytes(h.m.ram[0x200:0x2000])==original[:0x1e00] and bytes(h.m.ram[0x3000:0x6500])==original[0x2e00:] and not h.m.events
            passed(cpu,'dual-exclusive-4K-binary-port-'+str(port)+'-'+ending.hex(),payload_bytes=4096,all_byte_values=True)
        for label,hdr,body in [('bad-header',bytes(16),bytes(8)),('bad-body-CRC',header(bytes([1])*8),bytes(8))]:
            h=fresh();h.port_command(port,b'L\r',b'SEND HEADER+BIN\r\n');out=h.port_command(port,hdr+body)
            assert b'REFUSED' in out and h.m.ram[0x7c78]==0 and h.m.ram[0x7c2b]==0 and not h.m.events
            passed(cpu,'dual-binary-'+label+'-port-'+str(port))
    h=fresh();h.port_command(2,b'L\r',b'SEND HEADER+BIN\r\n');h.accelerate_crc=False;h.accelerate_acia=False;body=bytes(range(256))
    out=h.port_command(2,header(body)+body,timed=True)
    assert b'LOADED;' in out and h.m.acia_overruns==0 and bytes(h.m.ram[0x2000:0x2100])==body
    passed(cpu,'dual-ACIA-19200-paced-input-real-CRC',bytes=len(body),cycles_per_serial_byte=4167,overruns=h.m.acia_overruns)
    for error in (1,2,4):
        h=fresh();h.port_command(2,b'L\r',b'SEND HEADER+BIN\r\n');h.m.acia_error=error;body=bytes(range(64))
        out=h.port_command(2,header(body)+body);assert b'REFUSED' in out and h.m.ram[0x7c78]==0 and not h.m.events
        passed(cpu,'dual-ACIA-binary-rejects-error-'+str(error))
    h=fresh();now=h.c.processorCycles;h.m.acia_wire.extend([(now,ord('x'),0),(now,ord('y'),0)]);h.m.acia_rx.append(13)
    assert not h.call(h.b['BOOT_API_LINE']) and h.c.y==2 and h.m.acia_overruns==1 and not h.m.events
    passed(cpu,'dual-ACIA-latched-receive-overrun-rejects-line')
    for tdre in (0,16):
        h=fresh();h.accelerate_acia=False;h.call(h.b['BOOT_CON_SELECT'],2);h.m.acia_tdre=tdre
        start=len(h.m.acia_writes)
        for byte in (0x55,0xaa):h.call(h.w['V2W_PUTC'],byte)
        spacing=h.m.acia_writes[start+1][0]-h.m.acia_writes[start][0];assert 4167<=spacing<=4500
        passed(cpu,'dual-ACIA-transmit-real-instruction-pacing-TDRE-'+str(tdre),spacing_cycles=spacing,microseconds_at_8MHz=spacing/8)
    h=fresh();h.m.ram[0xf5]=1;before=bytes(h.m.ram[0x200:0x6500]);assert h.call(h.w['V2W_MUTATE'])
    assert h.m.ram[0xf6]==3 and not h.m.events and before==bytes(h.m.ram[0x200:0x6500])
    passed(cpu,'dual-legacy-self-mutation-explicitly-refused')
    for target in ('A','B'):
        h=Machine(build,cpu,[(0xc000,record(target=target))]);h.run(lambda:bytes(h.m.tx).endswith(b'B3> '));h.run(lambda:h.c.pc==h.w['V2W_GETC'])
        expected_brk=(h.sy['core/str8n-v2-vectors']['V2V_DEFAULT'].to_bytes(2,'little') if h.bench else b'\x50\x7c')
        assert bytes(h.m.ram[0x7e02:0x7e04])==expected_brk and bytes(h.m.ram[0x7c50:0x7c5f])==bytes.fromhex('48DA5AADEC7F48A9012048784C10A0')
        # Real tagged BRK flash writer must return through the unchanged
        # debugger fast-return scratch without corrupting the relocated stub.
        h.command(b'C A\r',b' Y?');h.command(b'Y\r',b'B3> ');assert h.m.events
        assert bytes(h.m.ram[0x7c50:0x7c5f])==bytes.fromhex('48DA5AADEC7F48A9012048784C10A0')
        passed(cpu,('bench-default-BRK-handler-monitor-' if h.bench else 'dual-relocated-debugger-trampoline-monitor-')+target)
        events=list(h.m.events);before=bytes(h.m.ram[0x200:0x6500])
        h.port_command(2,b'J3\r',b'OFFLINE PROTOTYPE S A B 0 1 2 3\r\n');h.port_command(2,b'S',b'REC> ')
        assert h.m.events==events and before==bytes(h.m.ram[0x200:0x6500])
        passed(cpu,'dual-monitor-'+target+'-ACIA-J3-S-software-restart')

def main():
    global GENERATION
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);args=p.parse_args();build=args.build.resolve();rows=[]
    report=json.loads((build/'prototype-report.json').read_text());GENERATION=report.get('experimental_generation',0x80000001)
    def passed(cpu,case,**kw):rows.append(dict(cpu=cpu,case=case,passed=True,**kw));print('PASS',cpu,case,flush=True)
    for cpu in ('65c02','65c816-e'):
        if report.get('dual_console'):dual_tests(build,cpu,passed)
        if report.get('shared_console'):console_tests(build,cpu,passed)
        # Check the actual linked CRC instructions before using the fast hook.
        h=Machine(build,cpu,opaque=True)
        for seed in (0,65535,0x1234,0x8000):
            for byte in (0,1,127,128,255):
                h.m.ram[0x7d38:0x7d3a]=seed.to_bytes(2,'little');h.c.pc=h.b['J_CRC_BYTE'];h.c.a=byte;h.c.sp=255;h.c.stPushWord(0x1ff)
                while h.c.pc!=0x200:h.c.step()
                assert int.from_bytes(h.m.ram[0x7d38:0x7d3a],'little')==binascii.crc_hqx(bytes([byte]),seed)
        passed(cpu,'linked-CRC-instructions',comparisons=20)
        h.c.pc=h.b['BR_TENTH'];h.c.sp=255;h.c.stPushWord(0x1ff);start_cycles=h.c.processorCycles
        while h.c.pc!=0x200:h.c.step()
        cycles=h.c.processorCycles-start_cycles
        assert 799000<=cycles<=801000,(cpu,cycles)
        passed(cpu,'nominal-tenth-timing',cycles=cycles,milliseconds_at_8MHz=cycles/8000)
        fixtures=[('blank',[],False),('one',[(0xc000,record())],True),('new-peer',[(0xc000,record()),(0xd000,record(3,'A'))],True),('identical-duplicate',[(0xc000,record()),(0xd000,record())],True),('conflict',[(0xc000,record()),(0xd000,record(target='A'))],False)]
        bad=bytearray(record(2));bad[255]=255;fixtures.append(('torn',[(0xc000,record()),(0xc100,bad)],True))
        bad=bytearray(record(2));bad[12]=0;bad=seal(bad);fixtures.append(('invalid-fields',[(0xc000,record()),(0xc100,bad)],True))
        for label,recs,ok in fixtures:
            h=Machine(build,cpu,recs);result=h.call(h.b['BOOT_READ_RECORD']);assert result==ok,(label,result)
            if label in ('torn','invalid-fields'):assert h.m.ram[0x7d35]==0xc0
            assert not h.m.events;passed(cpu,'boot-record-'+label)
        for module in ('core/monitor-a0','core/monitor-b0','core/ram-config'):
            sy=json.loads((build/'symbols.json').read_text())[module]
            for action in ('read','default-A','promote-A','count','saturated','bad-body','init','rollover','no-reservation','bad-target-rollover'):
                counts=[1]*32
                if action=='saturated':counts[5]=0xffffff
                recs=[] if action=='init' else [(0xc000,record(counts=counts))]
                if action in ('rollover','no-reservation','bad-target-rollover'):
                    recs=[(0xc000+i*256,record(i+1)) for i in range(15 if action=='rollover' else 16)]+[(0xd000,record(0))]
                if action=='bad-body':
                    bad=bytearray(record());bad[64]^=1;recs=[(0xc000,bad)]
                h=Machine(build,cpu,recs,ram_config=module.endswith('ram-config'))
                h.m.ram[0x7c60:0x7c62]=sy['JE_ENTER'].to_bytes(2,'little');h.m.ram[0x7c62]=ord('A');h.m.ram[0x7d3c]=5
                if action=='bad-target-rollover':h.m.ram[0x7c62]=ord('Z')
                h.m.ram[0x7d80:0x7d90]=record()[32:48];h.m.ram[0x7d88]=0xa0
                mode={'read':0,'default-A':1,'promote-A':3,'count':2,'saturated':2,'bad-body':2,'init':5,'rollover':1,'no-reservation':1,'bad-target-rollover':1}[action]
                original_ram=bytes(h.m.ram[0x200:0x6500]);ok=h.call(sy['JE_ENTER'],mode)
                assert ok==(action not in ('saturated','bad-body','no-reservation','bad-target-rollover')),(module,action,ok,hex(h.c.pc))
                assert bytes(h.m.ram[0x200:0x6500])==original_ram
                if action in ('read','saturated','bad-body','no-reservation','bad-target-rollover'):assert not h.m.events
                if ok and action!='read':
                    assert h.call(h.b['BOOT_READ_RECORD']);page=h.m.ram[0x7d35];actual=bytes(h.m.banks[3][(page-0x80)*256:(page-0x80)*256+256]);assert actual==seal(actual)
                    if action in ('default-A','promote-A','rollover'):assert actual[7]==ord('A')
                    if action=='count':assert int.from_bytes(actual[79:82],'little')==2
                    if action=='rollover':assert page==0xd0 and int.from_bytes(actual[64+29*3:67+29*3],'little')==2
                passed(cpu,'writer-'+module.rsplit('/',1)[1]+'-'+action,events=len(h.m.events))
        # Real MON reset/entry with both newly linked slots.
        for target in ('A','B'):
            h=Machine(build,cpu,[(0xc000,record(target=target))]);h.run(lambda:bytes(h.m.tx).endswith(b'B3> '))
            assert report.get('banner','2.0proto b01').encode() in h.m.tx;assert not h.m.events;passed(cpu,'cold-monitor-'+target)
            if report.get('shared_console'):
                before=bytes(h.m.ram[0x200:0x6500]);out=h.command(b'd 0200 0201\r',b'B3> ')
                assert b'0200:' in out and before==bytes(h.m.ram[0x200:0x6500]) and not h.m.events
                passed(cpu,'monitor-'+target+'-shared-hex-D-command')
            original_ram=bytes(h.m.ram[0x200:0x6500]);h.command(b'C A\r',b' Y?');out=h.command(b'Y\r',b'B3> ')
            assert b'Done' in out and h.m.events and bytes(h.m.ram[0x200:0x6500])==original_ram;passed(cpu,'monitor-'+target+'-C-default-write')
            events=list(h.m.events);out=h.command(b'W\r',b'B3> ');assert b'B0:8 000001' in out and h.m.events==events;passed(cpu,'monitor-'+target+'-W-read-only')
            h.command(b'J3\r',b'OFFLINE PROTOTYPE S A B 0 1 2 3\r\n');h.command(b'S',b'REC> ');assert h.m.events==events;passed(cpu,'monitor-'+target+'-J3-S')
        # Opaque selections do not require MON or any other firmware sector.
        for bank in range(4):
            h=Machine(build,cpu,[(0xc000,record(target=str(bank)))],opaque=True)
            h.run(lambda:h.m.bank==bank and h.c.pc==0x8000);assert not h.m.events;passed(cpu,'opaque-default-'+str(bank))
        # RAM loader framing/CRC/range and explicit run, with no MON at all.
        for ending in (b'\r',b'\n',b'\r\n'):
            for first in (0,3,10,13,255):
                body=bytes([first])+bytes(range(1,64));h=Machine(build,cpu,opaque=True);h.recovery()
                h.command(b'L'+ending,b'SEND HEADER+BIN\r\n');out=h.command(header(body)+body)
                assert b'LOADED;' in out and bytes(h.m.ram[0x2000:0x2040])==body
                out=h.command(b'V\r');assert out.startswith(b'V\r\n'+body+crc(body).to_bytes(2,'little'))
                assert not h.m.events;passed(cpu,'RAM-raw-'+ending.hex()+'-'+str(first))
        for label,body,hdr in [('bad-header',bytes(8),bytes(16)),('bad-CRC',bytes(8),header(bytes([1])*8)),('low-range',bytes(8),header(bytes(8),0x1fff)),('high-range',bytes(8),header(bytes(8),0x5fff)),('bad-entry',bytes(8),header(bytes(8),entry=0x2008))]:
            h=Machine(build,cpu,opaque=True);h.recovery();h.command(b'L\r',b'SEND HEADER+BIN\r\n');out=h.command(hdr+body);assert b'REFUSED' in out and h.m.ram[0x7c78]==0;assert not h.m.events;passed(cpu,'RAM-'+label)
        h=Machine(build,cpu,opaque=True);h.recovery();before=bytes(h.m.ram[0x2000:0x6000]);out=h.command(b'D\r');assert out==b'D\r\n'+before+crc(before).to_bytes(2,'little')+b'REC> ';passed(cpu,'RAM-preload-escrow')
        config=(build/'payload/ram-config-offline.bin').read_bytes();h=Machine(build,cpu,opaque=True);h.recovery();h.command(b'L\r',b'SEND HEADER+BIN\r\n');h.command(header(config)+config);h.command(b'R\r',b'CONFIG prototype I(blank only) W C target Q> ')
        out=h.command(b'I\r',b'CONFIG prototype I(blank only) W C target Q> ');assert b'OK\r\n' in out and h.m.events;passed(cpu,'MON-free-CONFIG-load-run-init',events=len(h.m.events))
        out=h.command(b'W\r',b'CONFIG prototype I(blank only) W C target Q> ');assert b'UNKNOWN HISTORY' in out;passed(cpu,'unknown-history-visible')
        # Examine every observed program/erase boundary from append and rotation.
        for scenario in ('append','rollover'):
            recs=[(0xc000,record())] if scenario=='append' else [(0xc000+i*256,record(i+1)) for i in range(15)]+[(0xd000,record(0))]
            h=Machine(build,cpu,recs,ram_config=True);sy=h.sy['core/ram-config'];h.m.ram[0x7c62]=ord('A')
            assert h.call(sy['JE_ENTER'],1)
            for cut,snapshot in enumerate(h.m.snapshots,1):
                reboot=Machine(build,cpu,opaque=True);reboot.m.banks[3][0x4000:0x6000]=snapshot
                assert reboot.call(reboot.b['BOOT_READ_RECORD']),(cpu,scenario,cut)
                assert reboot.m.ram[0x6707] in (ord('S'),ord('A'))
                assert not reboot.m.events
            passed(cpu,'all-mutation-prefixes-'+scenario,prefixes=len(h.m.snapshots))
    assert all(sha((ROOT/name).read_bytes())==digest for name,digest in report['selected_source_hashes'].items()),'Selected source changed during testing'
    save(build/'cpu-tests.json',dict(passed=True,checks=len(rows),failures=0,hardware=False,serial_access=False,device_or_network_attempts=ATTEMPTS,selected_source_unchanged=True,mutation_prefixes=sum(r.get('prefixes',0) for r in rows),cases=rows,component_hashes={p.name:sha(p.read_bytes()) for p in (build/'payload').glob('*-offline*.bin')}));print('PASS total',len(rows),flush=True)

if __name__=='__main__':main()
