"""Separate linked-model qualification of NAME and cold boot; no board access."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-board-name')
import binascii
import json

from test_v2_status import fresh, boot, layout, snapshot, OUT
from test_v2_storage import cmd
from test_v2_local_time import invoke, record as tz_record
from test_v2_spi_resident import k

META=json.loads((OUT/'build.json').read_text())
MAINT=json.loads((OUT/'maint/manifest.json').read_text())
S=MAINT['symbols']


def record(name=b'',seq=1):
    r=bytearray(b'\xff'*32)
    r[:8]=b'BN\x01\0'+seq.to_bytes(4,'little')
    r[8]=len(name);r[9:17]=name.ljust(8,b'\0')
    r[28:30]=binascii.crc_hqx(r[:28],0xFFFF).to_bytes(2,'little');r[31]=0
    return r


def launch(cpu,m):
    body=(OUT/'maint/board-name.bin').read_bytes()
    m.ram[0x2000:0x2000+len(body)]=body
    return cmd(cpu,m,b'G 2000\r')


def cold_power():
    cpu,m=fresh(off=True);boot(cpu);launch(cpu,m)
    out=cmd(cpu,m,b'NAME 2205\rYES\r');assert b'Board: 2205' in out
    retained=[bytes(b) for b in m.banks]
    # Recreate CPU/RAM/device model, retaining only flash, as at power-on.
    cpu,m=fresh(off=True);m.banks=[bytearray(b) for b in retained];m.spi.banks=m.banks
    before=snapshot(m);boot(cpu)
    assert b'Board: 2205\r\n' in m.tx and snapshot(m)==before
    m.tx.clear();cpu.pc=0x7E67;boot(cpu);assert b'Board:' not in m.tx
    # A missing/corrupt RTC provider must not suppress the board label.
    cpu,m=fresh();m.banks[3][0x1C20:0x1C40]=record(b'NO-RTC')
    m.banks[3][0]^=1;before=snapshot(m);boot(cpu)
    assert b'Board: NO-RTC\r\n' in m.tx and snapshot(m)==before,bytes(m.tx)
    check='fresh power-on model retains name; quiet monitor return omits it; corrupt/unavailable RTC provider does not suppress name'
    path=OUT/'board-name-test-results.json';report=json.loads(path.read_text())
    if check not in report['checks']:report['checks'].append(check)
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',check,flush=True)


def main():
    checks=[]
    def passed(text):checks.append(text);print('PASS',text,flush=True)
    for off in (False,True):
        cpu,m=fresh(off=off,primary=layout())
        m.banks[3][0x1C20:0x1C40]=record(b'LAB-2609')
        before=snapshot(m);application=bytes(m.ram[0x200:0x6700]);boot(cpu)
        assert b'Board: LAB-2609\r\n' in m.tx,bytes(m.tx)
        assert snapshot(m)==before and bytes(m.ram[0x200:0x6500])==application[:0x6300]
        if off:
            assert not m.bus.accesses and not m.spi.frames
            assert bytes(m.ram[0x6500:0x6700])==application[0x6300:]
        m.tx.clear();cpu.pc=0xF004;boot(cpu)
        assert b'Board: LAB-2609\r\n' in m.tx and snapshot(m)==before
    passed('eight-character name shown at cold reset with EDU ON/OFF; OFF preserves reclaimed RAM and performs no device I/O')
    cpu,m=fresh(primary=layout());boot(cpu);assert b'Board:' not in m.tx
    launch(cpu,m);before=snapshot(m)
    for line in (b'NAME',b'NAME ',b'NAME 123456789',b'NAME TWO WORD',b'NAME A B',b'NAME X\rNO',b'NAME X\rY'):
        cmd(cpu,m,line+b'\r');assert snapshot(m)==before,line
    passed('query/unset, eight-character limit, whitespace rejection and cancellation do not write; exact YES required')
    m.banks[3][0x1C20:0x1C40]=tz_record(-300)
    before=snapshot(m)
    out=cmd(cpu,m,b'NAME LAB-2609\rYES\r');assert b'Board: LAB-2609' in out,out
    saved=snapshot(m);events=len(m.events)
    cmd(cpu,m,b'NAME LAB-2609\r');assert snapshot(m)==saved and len(m.events)==events
    assert saved[0][:3]==before[0][:3] and saved[1:]==before[1:]
    assert saved[0][3][:0x1C40]==before[0][3][:0x1C40]
    assert not any(e[0]=='erase' for e in m.events)
    out=cmd(cpu,m,b'NAME 2205\rYES\r');assert b'Board: 2205' in out,out
    out=cmd(cpu,m,b'NAME CLEAR\rYES\r');assert b'Board: unnamed' in out,out
    out=cmd(cpu,m,b'Q\r');cpu.pc=0xF004;m.tx.clear();boot(cpu)
    assert b'Board:' not in m.tx and b'(-05:00)' in m.tx,bytes(m.tx)
    passed('set/change/clear append without erase; repeat is read-only; identity, timezone, other flash and RTC/EEPROM/SRAM preserved; clear retained across reset')
    # Boot reader ignores malformed, corrupt, unknown and incomplete records.
    for field,value in ((0,ord('X')),(2,2),(8,9),(9,0x1B),(16,ord('Z')),(28,0),(31,255)):
        cpu,m=fresh(off=True);m.banks[3][0x1C20:0x1C40]=record(b'OLD')
        bad=record(b'NEW',2);bad[field]=value
        if field in (8,9,16):bad[28:30]=binascii.crc_hqx(bad[:28],0xFFFF).to_bytes(2,'little')
        m.banks[3][0x1C40:0x1C60]=bad;boot(cpu)
        assert b'Board: OLD\r\n' in m.tx,(field,bytes(m.tx))
    passed('bad magic/version, excessive length, control characters, invalid padding, bad CRC and missing commit never replace last valid name')
    for scenario in ('full','sequence','format','timeout'):
        cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m)
        m.banks[3][0x1C20:0x1C40]=record(b'OLD',0xFFFFFFFF if scenario=='sequence' else 1)
        if scenario=='full':m.banks[3][0x1C40:0x2000]=bytes(0x3C0)
        if scenario=='format':m.banks[3][0x1000]=0
        before=snapshot(m)
        if scenario=='timeout':m.fault='timeout'
        out=cmd(cpu,m,b'NAME NEW\rYES\r');m.fault=None
        assert b'Name not saved' in out,(scenario,out)
        if scenario!='timeout':assert snapshot(m)==before
        assert snapshot(m)[1:]==before[1:] and not any(e[0]=='erase' for e in m.events)
        out=cmd(cpu,m,b'NAME\r');assert b'Board: OLD' in out,out
        assert m.ram[0xF4]==0
    passed('full tail, sequence exhaustion, incompatible journal and flash timeout refuse safely and retain old name')
    cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m)
    m.banks[3][0x1C20:0x1C40]=record(b'OLD')
    m.banks[3][0x1C40:0x1C60]=tz_record(-300)
    ram=bytes(m.ram);banks=[bytes(b) for b in m.banks]
    def fixture(cut=None):
        c,p=fresh(primary=layout());p.ram[:]=ram
        p.banks=[bytearray(b) for b in banks];p.spi.banks=p.banks
        p.ram[S['BN_PENDING_LENGTH']]=8
        p.ram[S['BN_PENDING']:S['BN_PENDING']+8]=b'LAB-2609'
        p.cut_after=cut
        return c,p
    cpu,done=fixture();invoke(cpu,S['BN_SAVE']);assert cpu.p&cpu.CARRY
    writes=len(done.events);assert writes>0
    for cut in range(1,writes+1):
        cpu,p=fixture(cut)
        try:invoke(cpu,S['BN_SAVE'])
        except k.model.PowerCut:pass
        p.cut_after=None;cpu.sp=255;p.ram[0xF4]=0
        invoke(cpu,S['BN_READ']);n=p.ram[S['BN_LENGTH']]
        assert bytes(p.ram[S['BN_TEXT']:S['BN_TEXT']+n])==(b'LAB-2609' if cut==writes else b'OLD'),cut
        assert bytes(p.banks[3][:0x1C60])==banks[3][:0x1C60]
    passed(f'all {writes} power-cut append checkpoints keep old name until final commit; EI/TZ and journal code preserved')
    result=dict(passed=True,checks=checks,artifacts=META['artifacts'],local_asset_sha256=META['local_asset_sha256'],maint_sha256=MAINT['program_sha256'],board_access=False,boards_flashed=False,soak_untouched=True)
    (OUT/'board-name-test-results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    import sys
    if '--cold-power' not in sys.argv:main()
    cold_power()
