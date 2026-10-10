"""Post-reset beta17 hardware readback and preserving smoke checks."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-storage'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());out=a.root/'installed-check';out.mkdir(exist_ok=False);checks=[]
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ');(out/'physical-reset.txt').write_bytes(first)
            if any(t in first for t in (b'CLOCK>',b'BM>',b'EDU>',b'WORK>',b'SRAM>')):link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                data=link.command(text,prompt)
                if label:(out/(label+'.txt')).write_bytes(data)
                return data
            expected=[(a.root/f'upgrade/expected-b{b}.bin').read_bytes() for b in range(4)];hashes=[]
            for b in range(4):
                prompt=f'\r\nB{b}> '.encode();link.command(f'B{b}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096));assert data==expected[b],f'Installed B{b} mismatch'
                (out/f'b{b}.bin').write_bytes(data);hashes.append(sha(data));print('PASS',a.board,'exact installed B'+str(b),flush=True)
            link.command('B3');checks.append('All four flash banks exact, including retained B0, recovery F and EUI tail')
            off=a.board=='2512'
            for slot in ('A','B','A'):
                write(link,0x2300,bytes.fromhex('4C 64 7E'));start=cmd('G 2300',b'Enter default [3s]: ');link.send(slot.encode());data=start+link.until(b'\r\nB3> ');(out/f'boot-{slot}-{time.monotonic_ns()}.txt').write_bytes(data)
                assert b'STR8-N 2.0b17' in data and (b'RAM $0200-$66FF' if off else b'RAM $0200-$64FF') in data
                assert (b'EDU OFF' if off else b'EDU ON') in data
                if off:assert b'RTCC:' not in data and b'SSRAM:' not in data
                else:assert b'RTCC: UTC ' in data and b'RTCC: EUI ' in data and b'SSRAM:' in data
                assert link.dump(0x7D04,0x7D0B)==(b'SV\x01\0\0\0\xff\x66' if off else b'SV\x01\x0f\0\x65\xff\x64')
            checks.append('Both A/B monitor slots, cold software RESET, approved display and correct active RAM/EDU state')
            data=cmd('T 2',label='programs');assert b'DEMO2' not in data and not re.search(rb'\bDEMO\b',data)
            assert all(name in data for name in (b'CLOCK',b'WORK',b'SRAM',b'EDU'));checks.append('Saved utility inventory; DEMO/DEMO2 absent')
            assert b'EDU 1.2' in cmd('R EDU',b'EDU> ',label='edu');cmd('Q')
            assert b'WORK 1.2' in cmd('R WORK',b'WORK> ',label='work');cmd('Q')
            assert b'BANK MAINT 1.8' in cmd('R MAINT',b'BM> ',label='maint');cmd('Q')
            checks.append('EDU, relocated WORK and flash-only MAINT start/return with current versions; no WORK query or resize')
            # A patterned application around the former $4000 load is preserved
            # by the named SRAM loader. Snapshot/restore even this RAM test data.
            original=link.dump(0x3F00,0x503F);pattern=bytes((i*19+i//256)&255 for i in range(len(original)))
            if not off:
                from beta4_migration import s19
                image=out/'preservation-pattern.s19';image.write_bytes(s19(dict(enumerate(pattern,0x3F00)),0x3F00));load_image(link,image)
                try:
                    assert b'SRAM 1.2' in cmd('R SRAM',b'SRAM> ',label='sram');cmd('Q')
                    assert link.dump(0x3F00,0x503F)==pattern
                finally:
                    image=out/'restore-application-ram.s19';image.write_bytes(s19(dict(enumerate(original,0x3F00)),0x3F00));load_image(link,image)
            else:
                before=link.dump(0x6500,0x66FF);assert b'SRAM loader unavailable' in cmd('R SRAM',label='sram-unavailable');assert link.dump(0x6500,0x66FF)==before
            checks.append('Preserving named SRAM loader across former load area, or OFF refusal preserving reclaimed RAM')
            probes=ROOT/'BUILD/v2-board-regression';load_image(link,probes/'abi.s19');assert b'RAM ABI: PASS' in cmd('G 2000',label='abi')
            handlers=link.dump(0x7E00,0x7E1B);load_image(link,probes/'irq.s19');assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in cmd('G 2000',label='irq');assert link.dump(0x7E00,0x7E1B)==handlers
            checks.append('RAM ABI and BRK/VIA1 IRQ regression; vectors/registers/stack restored')
            assert b'CLOCK 1.5' in cmd('R CLOCK',b'CLOCK> ');status=cmd('STATUS',b'CLOCK> ',label='clock-status');history=cmd('HISTORY',b'CLOCK> ',label='history');eui=cmd('EUI',b'CLOCK> ',label='eui');cmd('Q')
            if not off:
                prior=(a.root/'prior/rtc-prior.txt').read_bytes();raw=lambda t:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode())
                assert raw(prior)[7:9]==raw(status)[7:9] and b'Running: yes' in status and b'Backup enabled: yes' in status
                calendar=lambda t:datetime.strptime(re.search(rb'Calendar \(UTC convention\): ([0-9 :\-]+)',t)[1].decode(),'%Y-%m-%d %H:%M:%S')
                assert calendar(status)>=calendar(prior) and raw(status)[3]&7==calendar(status).isoweekday()
                assert history==(a.root/'prior/history-prior.txt').read_bytes() and b', changed' not in eui and b', unbound' not in eui
                load_image(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');cmd('G 2000');ee=link.dump(0x2400,0x2494);(out/'eeprom.bin').write_bytes(ee)
                assert ee[:128]==(a.root/'eeprom-prior/array.bin').read_bytes() and ee[0x80:0x89]==(a.root/'eeprom-prior/status-factory.bin').read_bytes()
            checks.append('CLOCK retained, UTC running forward, trim/backup/DOW/EUI and EEPROM history preserved; no SET/ACK')
            report=dict(passed=True,board=a.board,version='2.0b17',installed_hashes=hashes,checks=checks,clock_set=False,trim_changed=False,demos_installed=False,sram_array_written=False)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',a.board,'beta17 hardware readback, both slots, utility/ABI/IRQ checks and retained clock/history',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
