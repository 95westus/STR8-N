"""Qualify a preinstalled frozen beta23 board with backed-up mode changes."""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,journal,metadata,config_sum
from rtc_boards import SERIALS
from qualify_v2_spi_install import load_image

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    banks=[(a.root/f'prior/b{i}.bin').read_bytes() for i in range(4)]
    for page,offset,name in ((0xA0,0x2000,'str8n-v2-recovery-slot-a0.bin'),(0xB0,0x3000,'str8n-v2-recovery-slot-b0.bin')):
        assert banks[3][offset:offset+4096]==(a.build/name).read_bytes()
    record=journal(banks[3]);assert record
    cfg=bytearray(record[8:24]);counts=[int.from_bytes(record[24+3*i:27+3*i],'little') for i in range(32)]
    seq=int.from_bytes(record[4:8],'little');assert cfg[13]!=0xA5,'This run preserves initially ON boards'
    expected=[bytearray(b) for b in banks]
    out=a.root/'reset-notice-check';out.mkdir(exist_ok=False);checks=[];report=dict(passed=False,board=a.board,checks=checks,clock_set=False,trim_changed=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            time.sleep(.3);initial=link.command('',b'> ')
            if any(x in initial for x in (b'CLOCK>',b'BM>',b'EDU>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                r=link.command(text,prompt)
                if label:(out/(label+'.txt')).write_bytes(r)
                return r
            def state(off=False):
                assert link.dump(0x7D04,0x7D0B)==(b'SV\x01\0\0\0\xff\x66' if off else b'SV\x01\x0f\0\x65\xff\x64')
            def cold(slot='A',label='cold'):
                text=cmd('J3',b'Enter default [3s]: ');link.send(slot.encode());text+=link.until(b'\r\nB3> ')
                (out/(label+'.txt')).write_bytes(text);assert b'STR8-N 2.0b23' in text;return text
            state()
            for n,slot in enumerate(('A','B','A')):cold(slot,f'slot-{n}-{slot}');state()
            checks.append('A/B/A J3 startup on exact frozen beta23 slots')
            for turn,target in enumerate(('OFF','ON'),1):
                state(turn==2);cmd('R EDU',b'EDU> ')
                cmd(target,b'Apply after RESET? [y/N]: ');assert b'Saved; RESET required.' not in cmd('N',b'EDU> ')
                cmd(target,b'Apply after RESET? [y/N]: ');assert b'Saved; RESET required.' in cmd('Y',b'EDU> ',f'saved-{target}')
                assert ('RESET required: '+target).encode() in cmd('?',b'EDU> ',f'pending-{target}')
                cmd('Q');state(turn==2);cmd('M1')
                cmd('R EDU',b'EDU> ');assert ('RESET required: '+target).encode() in cmd('?',b'EDU> ');cmd('Q')
                cold(label=f'activate-{target}');state(target=='OFF')
                cmd('R EDU',b'EDU> ');assert b'RESET required:' not in cmd('?',b'EDU> ',f'cleared-{target}');cmd('Q')
                cfg[13]=0xA5 if target=='OFF' else 0;cfg[14:]=config_sum(cfg)
                old_end=max(i for i in range(0,4096,128) if expected[3][0x4000+i:0x4000+i+128]!=b'\xff'*128)+128
                assert old_end<4096;start=0x4000+old_end
                expected[3][start:start+128]=metadata(cfg,counts,seq+turn)
                if target=='OFF':
                    saved=link.dump(0x6500,0x66FF);pattern=bytes((i*13+17)&255 for i in range(512));link.write_ram(0x6500,pattern)
                    assert link.dump(0x6500,0x66FF)==pattern;link.write_ram(0x6500,saved)
            checks.append('Confirmed/canceled ON-OFF-ON; pending notice persists through ordinary return; J3 activation/clearance and reclaimed RAM; original ON restored')
            probes=ROOT/'BUILD/v2-board-regression'
            pm=json.loads((probes/'build.json').read_text())['probes']
            assert load_image(link,probes/'abi.s19')==pm['abi']['sha256'];assert b'RAM ABI: PASS' in cmd('G 2000',label='abi')
            pointers=link.dump(0x7E00,0x7E1B)
            assert load_image(link,probes/'irq.s19')==pm['irq']['sha256']
            assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in cmd('G 2000',label='irq')
            assert link.dump(0x7E00,0x7E1B)==pointers
            checks.append('RAM ABI and actual BRK/VIA1 IRQ, registers/stack/vectors restored')
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                assert data==expected[bank],f'B{bank} differs from exact modeled mode appends'
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest())
            link.command('B3');report.update(passed=True,final_flash_hashes=hashes,original_mode_restored=True,configuration_changes=2,physical_nmi_pending=True)
        except Exception as e:report['error']=repr(e);raise
        finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()
    print('PASS',a.board,'A/B/J3, EDU modes/notices, reclaimed RAM, ABI/IRQ and exact final flash')


if __name__=='__main__':main()
