"""Execute RC1 r10 recovery console on 65C02 and 65C816 E=1; no ports."""
import argparse,json,sys
from pathlib import Path
import test_f_size as shared
from test_monitor_size import fast_crc
from str8build.formats import save,sha

class Machine(shared.Machine):
    def run(self,stop,limit=6000000):
        for _ in range(limit):
            if stop():return
            c,m=self.cpu,self.m;self.steps+=1
            if getattr(self,'target_timeout',None) and c.pc==self.w['V2W_WAIT'] and m.ram[0xe5]&0xf0==self.target_timeout:
                m.fault='timeout';self.target_timeout=None
            if c.pc==self.sy.get('J_CRC_BYTE') and m.bank==3:
                fast_crc(c,m,0x7d38);continue
            if c.pc==self.w['V2W_BOOT_DELAY_OUTER']:
                c.pc=self.w['V2W_BOOT_DELAY_DONE'];continue
            if m.fault=='timeout' and c.pc==self.w['V2W_POLL']:
                c.stPop();c.pc=self.w['V2W_TIMEOUT'];continue
            op=m[c.pc]
            if self.name=='65c02' and op&15==15:
                pc=c.pc;bit=bool(m[m[(pc+1)&65535]]&(1<<((op>>4)&7)));take=bit if op&128 else not bit;d=m[(pc+2)&65535]
                c.pc=(pc+3+((d if d<128 else d-256) if take else 0))&65535
            else:c.step()
        raise AssertionError(('timeout',self.name,hex(c.pc),bytes(m.tx[-250:])))

def ready(build,cpu,active=0xb0):
    banks=list(map(bytearray,shared.banks_for(build)))
    cfg=bytearray(shared.rt.latest(list(map(bytes,banks)))[2][8:24])
    generation=int.from_bytes((build/'payload/str8n-v2-recovery-slot-b0.bin').read_bytes()[8:12],'little')
    cfg=shared.rt.preference(cfg,0xb0,generation)
    banks[3][0x4000:0x6000]=b'\xff'*8192
    banks[3][0x4000:0x4080]=shared.rt.record(cfg,[1]*32,1)
    h=Machine(build,cpu,list(map(bytes,banks)));h.m.ram[0x7d30]=active
    h.cpu.pc=h.sy['BOOT_RECOVERY'];h.cpu.sp=255
    h.run(lambda:bytes(h.m.tx).endswith(b'REC> '))
    return h

def command(h,data,until=b'REC> '):
    n=len(h.m.tx);h.m.rx.extend(data)
    h.run(lambda:len(h.m.tx)>n and bytes(h.m.tx).endswith(until))
    return bytes(h.m.tx[n:])

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    rows=[]
    for cpu in ('65c02','65c816-e'):
        h=ready(args.build,cpu)
        out=command(h,b'W\r\n')
        assert b'B0:8 000001' in out and b'B3:F 000001' in out and not h.m.events
        rows.append(dict(cpu=cpu,test='wear-read-only',passed=True))
        for ending in (b'\r',b'\n',b'\r\n'):
            for text,expected in ((b'U',b'use A/B/W/U A|B'),(b'U B',b'active slot'),(b'u b',b'active slot'),(b'BADKEYS',b'use A/B/W/U A|B')):
                h=ready(args.build,cpu);out=command(h,text+ending)
                assert text in out and b'REFUSED: '+expected in out,(cpu,ending,text,out)
                assert not h.m.events
                rows.append(dict(cpu=cpu,test='echo-refusal',ending=ending.hex(),input=text.decode(),passed=True))
            for confirm in (b'N',b'YES',b'',b'yY'):
                h=ready(args.build,cpu);out=command(h,b'U A'+ending,b'Y then Enter> ')
                out+=command(h,confirm+ending)
                assert b'cancelled' in out and b'SEND' not in out and not h.m.events,out
                rows.append(dict(cpu=cpu,test='cancel',ending=ending.hex(),input=confirm.decode(),passed=True))
            for confirm in (b'Y',b'y'):
                for first in (0,3,10,13,255):
                    h=ready(args.build,cpu);command(h,b'U A'+ending,b'Y then Enter> ')
                    out=command(h,confirm+ending,b'SEND 4096 BIN\r\n')
                    assert confirm in out and not h.m.events
                    data=bytes([first])+bytes((i%256 for i in range(4095)))
                    # Run only until all raw bytes are staged; malformed image
                    # deliberately avoids any erase/program for framing tests.
                    h.m.rx.extend(data);h.run(lambda:h.cpu.pc==h.sy['BOOT_SLOT_CHECK'])
                    assert bytes(h.m.ram[0x6800:0x7800])==data,(cpu,ending,first)
                    h.run(lambda:bytes(h.m.tx).endswith(b'REC> '))
                    assert b'REFUSED: invalid image/ABI/CRC' in h.m.tx and not h.m.events
                    rows.append(dict(cpu=cpu,test='raw-binary-framing',ending=ending.hex(),confirm=confirm.decode(),first=first,passed=True))
        # Mixed line endings in one session; trailing LF must not cancel Y.
        for cmdend in (b'\r',b'\n',b'\r\n'):
            for yesend in (b'\r',b'\n',b'\r\n'):
                h=ready(args.build,cpu);command(h,b'U A'+cmdend,b'Y then Enter> ')
                command(h,b'Y'+yesend,b'SEND 4096 BIN\r\n')
                assert not h.m.events
                rows.append(dict(cpu=cpu,test='mixed-endings',command=cmdend.hex(),confirmation=yesend.hex(),passed=True))
        current_generation=int.from_bytes((args.build/'payload/str8n-v2-recovery-slot-b0.bin').read_bytes()[8:12],'little')
        for generation in (current_generation-1,current_generation):
            h=ready(args.build,cpu)
            data=bytearray((args.build/'payload/str8n-v2-recovery-slot-a0.bin').read_bytes())
            data[8:12]=generation.to_bytes(4,'little');data[18:20]=shared.rt.crc(data[:18]+data[32:]).to_bytes(2,'little')
            command(h,b'U A\r\n',b'Y then Enter> ');command(h,b'Y\r\n',b'SEND 4096 BIN\r\n')
            out=command(h,data)
            assert b'generation not newer' in out and not h.m.events,out
            rows.append(dict(cpu=cpu,test='stale-generation',generation=generation,passed=True))
        h=ready(args.build,cpu,active=0xa0)
        out=command(h,b'U B\r')
        assert b'preferred slot' in out and not h.m.events
        rows.append(dict(cpu=cpu,test='preferred-slot-protected',passed=True))
        for page in (0xa0,0xb0):
            slot='A' if page==0xa0 else 'B';off=(page-0x80)*256
            for case in ('valid','blank-journal','invalid-journal','wear-full','timeout','erase-verify'):
                h=ready(args.build,cpu,active=0)
                if case in ('blank-journal','invalid-journal'):
                    h.m.banks[3][0x4000:0x6000]=(b'\xff' if case=='blank-journal' else b'\0')*8192
                    h.m.banks[3][off:off+4096]=b'\xff'*4096
                if case=='wear-full':
                    cfg=bytearray(shared.rt.latest(list(map(bytes,h.m.banks)))[2][8:24]);counts=[1]*32;counts[24+(page>>4)-8]=0xffffff
                    h.m.banks[3][0x4000:0x4080]=shared.rt.record(cfg,counts,1)
                upload=(args.build/f'payload/str8n-v2-recovery-slot-{page:02x}.bin').read_bytes()
                command(h,('U '+slot+'\r\n').encode(),b'Y then Enter> ');command(h,b'Y\r\n',b'SEND 4096 BIN\r\n')
                h.m.ram[0xf6]=0x5a
                if case=='timeout':h.target_timeout=page
                if case=='erase-verify':h.m.fault='erase_verify'
                h.m.rx.extend(upload);h.run(lambda:h.cpu.pc in (h.sy['BOOT_MENU'],h.sy['BOOT_RESET']))
                out=bytes(h.m.tx)
                if case in ('valid','blank-journal'):
                    assert b'COMMITTED' in out and bytes(h.m.banks[3][off:off+4096])==upload,(cpu,slot,case,out[-100:])
                else:
                    reason={'invalid-journal':b'journal/wear refused','wear-full':b'journal/wear refused','timeout':b'flash timeout','erase-verify':b'flash verify'}[case]
                    assert b'REFUSED: '+reason in out and b'COMMITTED' not in out,(cpu,slot,case,out[-100:])
                    if case in ('invalid-journal','wear-full'):assert not h.m.events
                rows.append(dict(cpu=cpu,test='upload-safety',slot=slot,case=case,passed=True,flash_events=len(h.m.events)))
    save(args.out,dict(passed=True,checks=len(rows),firmware_sha256=sha((args.build/'firmware.bin').read_bytes()),cases=rows,hardware=False))
    print('PASS',len(rows),'recovery console CPU checks',flush=True)

if __name__=='__main__':main()
