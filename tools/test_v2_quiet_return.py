"""Execute cold boot, M1 and bank-safe software returns without board access."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-quiet-return')
import hashlib,json
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_storage import cmd

def main():
    meta=json.loads((OUT/'build.json').read_text());checks=[]
    for slot in (b'A',b'B'):
        for off in (False,True):
            cpu,m=fresh(off=off,primary=layout());m.rx.extend(slot+b'\r')
            boot(cpu)
            assert bytes(m.tx).count(b'STR8-N '+meta['version'].encode())==1
            assert b'RAM $0200-' in m.tx
            if meta.get('compact_boot_local'):
                assert (b'RTCC:' in m.tx)==(not off) and b'RTCC: UTC' not in m.tx and b'RTCC: EUI' not in m.tx
            else:assert (b'RTCC: UTC' in m.tx)==(not off)
            before=snapshot(m)
            out=cmd(cpu,m,b'M1\r')
            assert b'B3:8-F protected.' in out and out.endswith(b'B3> '),out
            for text in (b'STR8-N ',b'ABI ',b'RAM $',b'EDU ON',b'EDU OFF',b'RTCC:',b'SSRAM:'):
                assert text not in out,(text,out)
            assert snapshot(m)==before
            # M1 loads MAINT into application RAM. The return itself must
            # preserve application RAM, tested independently through HOLD.
            pattern=bytes((i*17)&255 for i in range(0x6300))
            m.ram[0x200:0x6500]=pattern
            # Public HOLD is the return path used by ordinary applications.
            for bank in range(4):
                m[0x7FEC]=(m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[bank]
                start=len(m.tx);reads=len(m.bus.accesses);frames=len(m.spi.frames)
                cpu.pc=0x7E67;boot(cpu)
                assert bytes(m.tx[start:])==b'\r\nB3> ',bytes(m.tx[start:])
                assert len(m.bus.accesses)==reads and len(m.spi.frames)==frames
                assert snapshot(m)==before and m.ram[0x200:0x6500]==pattern
                assert m.ram[0x7D0A:0x7D0C]==(b'\xff\x66' if off else b'\xff\x64')
            out=cmd(cpu,m,b'TIME\r')
            assert (b'RTCC: UTC' in out)==(not off),out
            checks.append(f'{slot.decode()} EDU {"OFF" if off else "ON"}: cold banner, quiet M1/HOLD in four banks, explicit TIME, preserved RAM/hardware')
    for name in ('str8n-rtc-component-8000-8fff.bin','str8n-journal-9000-9fff.bin','str8n-v2-recovery-f000-ffff.bin'):
        actual=(OUT/name).read_bytes();prior=(OUT.parent/'v2-trim-display'/name).read_bytes()
        if meta.get('weekday_display') and name=='str8n-rtc-component-8000-8fff.bin':
            if meta.get('compact_boot_local'):
                # Private SPI helper addresses relink with the changed banner;
                # public provider ABI remains fixed and is exercised separately.
                assert actual[:4]==prior[:4],name
            else:assert actual[:0x900]==prior[:0x900],name
        elif meta.get('weekday_display') and name=='str8n-journal-9000-9fff.bin':
            assert actual[:4]==prior[:4] and actual[0xC00:]==prior[0xC00:],name
        else:assert actual==prior,name
    pinned=OUT.parents[1]/'output/qualification/trim-display-2026-10-08/flash-schedule.json'
    schedule=json.loads(pinned.read_text());build=OUT.parent/'v2-trim-display'
    assert hashlib.sha256((build/'build.json').read_bytes()).hexdigest()==schedule['build_metadata_sha256']
    report=dict(passed=True,checks=checks,artifacts=meta['artifacts'],pinned_beta18_unchanged=True,board_access=False)
    (OUT/'quiet-return-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    for check in checks:print('PASS',check)

if __name__=='__main__':main()
