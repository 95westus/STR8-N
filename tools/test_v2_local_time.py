"""Execute fixed-offset calendar/display and CLOCK save/failure behavior."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-local-time')
import binascii,hashlib,json
from datetime import datetime,timedelta
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_spi_resident import k
from test_v2_storage import cmd

META=json.loads((OUT/'build.json').read_text())
CM=json.loads((OUT/'clock/build.json').read_text())
def record(offset,seq=1):
    r=bytearray(b'\xff'*32);r[:4]=b'TZ\x01\0';r[4:8]=seq.to_bytes(4,'little')
    r[8:10]=offset.to_bytes(2,'little',signed=True);r[28:30]=binascii.crc_hqx(r[:28],0xFFFF).to_bytes(2,'little');r[31]=0
    return r
def invoke(cpu,entry):
    sp=cpu.sp;cpu.stPushWord(0x1FF);cpu.pc=entry
    for _ in range(3000000):
        if cpu.pc==0x200:break
        cpu.step()
    else:raise AssertionError(('helper timeout',hex(cpu.pc)))
    assert cpu.sp==sp
def launch(cpu,m):
    body=(OUT/'clock/clock.bin').read_bytes();m.ram[0x2000:0x2000+len(body)]=body
    return cmd(cpu,m,b'G 2000\r')
def extra():
    cpu,m=fresh(primary=layout());boot(cpu)
    for raw,coarse,text in ((0,False,b'Trim 0 steps: 0.00 ppm, 0.000 s/day correction'),
        (18,False,b'Trim -18 steps: -18.31 ppm, -1.582 s/day correction'),
        (0x8E,False,b'Trim +14 steps: +14.24 ppm, +1.230 s/day correction'),
        (0,True,b'coarse ON; ppm/day unavailable')):
        m.ram[0x66C0]=0;m.ram[0x66C1]=4;m.ram[0x66D3]=raw;m.ram[0x66D2]=0x84 if coarse else 0x80
        m.ram[META['status_symbols']['KIND']]=2;start=len(m.tx);prior=snapshot(m)
        invoke(cpu,META['status_symbols']['LOCAL_DISPLAY']);out=bytes(m.tx[start:])
        assert text in out and b'RTCC: Local' in out,out
        assert snapshot(m)==prior
    cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m)
    prior=[bytes(b) for b in m.banks]
    out=cmd(cpu,m,b'SET 2026-10-09 02:55:20\rYES\r-05:00\rYES\r')
    assert b'Local UTC offset +/-HH:MM' in out and b'Local UTC offset: -05:00' in out,out[-900:]
    assert any(e[0]=='program' for e in m.events) and not any(e[0]=='erase' for e in m.events)
    assert bytes(m.banks[3][:0x1C00])==prior[3][:0x1C00]
    out=cmd(cpu,m,b'R\r');assert b'RTCC: Local Thu 2026-10-08 21:55:20 (-05:00)' in out,out
    # Exhausted sequence is separate from physical slot exhaustion.
    m.banks[3][0x1C40:0x1C60]=record(-300,0xFFFFFFFF);before=snapshot(m)
    out=cmd(cpu,m,b'OFFSET +05:30\rYES\r');assert b'Offset not saved' in out and snapshot(m)==before
    report=dict(passed=True,artifacts=META['artifacts'],clock_sha256=CM['sha256'],local_asset_sha256=META['local_asset_sha256'],
        setup_save=True,relocated_trim_display=True,sequence_exhaustion=True,board_access=False)
    (OUT/'local-time-extra-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS initial SET offset entry/confirmation, CLOCK local output, relocated signed/coarse trim and sequence exhaustion')
def main():
    checks=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    cpu,m=fresh(primary=layout());before=snapshot(m);boot(cpu)
    prefix=b'RTCC: ' if META.get('compact_boot_local') else b'RTCC: Local '
    assert prefix+b'Thu 2026-10-08 19:53:15 (+00:00)' in m.tx,bytes(m.tx[-600:])
    assert snapshot(m)==before
    passed('no offset record defaults to UTC; cold status reads only')
    # Table-driven actual linked formatter, with independent Python calendar.
    cases=[(datetime(2026,10,9,2,55,20),o) for o in (-720,-330,-300,-1,0,1,330,345,840)]
    cases += [(d,o) for d in (datetime(2000,1,1,0,1,2),datetime(2000,2,29,0,0,3),datetime(2024,3,1,0,0,4),
        datetime(2025,3,1,0,0,5),datetime(2099,12,31,23,59,6),datetime(2026,1,31,23,50,7)) for o in (-720,840)]
    for dt,offset in cases:
        m.banks[3][0x1C20:0x1C40]=record(offset)
        m.ram[0x66C0]=0;m.ram[0x66C1]=4
        m.ram[0x66C2:0x66CA]=dt.year.to_bytes(2,'little')+bytes((dt.month,dt.day,dt.isoweekday(),dt.hour,dt.minute,dt.second))
        m.ram[META['status_symbols']['KIND']]=2
        prior=snapshot(m);scratch=bytes(m.ram[0x6B00:0x6C00]);utc=bytes(m.ram[0x66C2:0x66CA]);start=len(m.tx)
        invoke(cpu,META['status_symbols']['LOCAL_DISPLAY']);out=bytes(m.tx[start:])
        local=dt+timedelta(minutes=offset);sign='-' if offset<0 else '+';minutes=abs(offset)
        expected=f'RTCC: Local {local:%a %Y-%m-%d %H:%M:%S} ({sign}{minutes//60:02d}:{minutes%60:02d})'.encode()
        assert expected in out,(dt,offset,out,expected)
        assert snapshot(m)==prior and bytes(m.ram[0x6B00:0x6C00])==scratch and bytes(m.ram[0x66C2:0x66CA])==utc
    passed('21 fractional/boundary offsets, weekday/month/year rollover, leap years, 1999/2100 edges; UTC and journal scratch preserved')
    # Invalid and uncommitted records must never override a valid setting.
    for offset in (841,-721,32767,-32768):
        m.banks[3][0x1C20:0x1C40]=record(345,1);m.banks[3][0x1C40:0x1C60]=record(offset,2)
        invoke(cpu,META['status_symbols']['LOCAL_DISPLAY'])
        assert b'(+05:45)' in m.tx[-100:]
    bad=record(-300,9);bad[28]^=1;m.banks[3][0x1C40:0x1C60]=bad
    invoke(cpu,META['status_symbols']['LOCAL_DISPLAY']);assert b'(+05:45)' in m.tx[-100:]
    bad=record(-300,9);bad[31]=255;m.banks[3][0x1C40:0x1C60]=bad
    invoke(cpu,META['status_symbols']['LOCAL_DISPLAY']);assert b'(+05:45)' in m.tx[-100:]
    passed('out-of-range, CRC-corrupt and uncommitted TZ records ignored; EI record retained')
    cpu,m=fresh(primary=layout());boot(cpu);prior=snapshot(m);out=launch(cpu,m)
    assert b'CLOCK 1.6' in out and b'Local UTC offset: +00:00' in out,out[-600:]
    assert snapshot(m)==prior
    for line in (b'OFFSET',b'OFFSET ?',b'OFFSET +14:01',b'OFFSET -12:01',b'OFFSET +05:60',b'OFFSET 05:30',b'OFFSET +5:30',b'OFFSET +99:00',b'OFFSET +05:30 X'):
        cmd(cpu,m,line+b'\r');assert snapshot(m)==prior
    cmd(cpu,m,b'OFFSET -05:00\rNO\r');assert snapshot(m)==prior
    cmd(cpu,m,b'OFFSET -05:00\rY\r');assert snapshot(m)==prior
    passed('CLOCK offset query/help, strict HH:MM parser, bounds and cancellation are read-only; exact YES required')
    out=cmd(cpu,m,b'OFFSET -05:00\rYES\r')
    assert b'Local UTC offset: -05:00' in out,out[-800:]
    assert bytes(m.bus.ee)==prior[1] and bytes(m.bus.rtc_regs)==prior[2] and bytes(m.spi.devices[0].data)==prior[3]
    assert bytes(m.banks[3][0x1C00:0x1C20])==prior[0][3][0x1C00:0x1C20]
    assert m.events and not any(e[0]=='erase' for e in m.events)
    saved=[bytes(b) for b in m.banks];events=len(m.events)
    cmd(cpu,m,b'OFFSET -05:00\r');assert len(m.events)==events and [bytes(b) for b in m.banks]==saved
    out=cmd(cpu,m,b'R\r');assert b'RTCC: Local Thu 2026-10-08 14:53:15 (-05:00)' in out,out
    out=cmd(cpu,m,b'Q\rTIME\r');assert b'RTCC: Local Thu 2026-10-08 14:53:15 (-05:00)' in out,out
    # Reboot the same emulated board, preserving its flash settings.
    cpu.pc=0xF004;boot(cpu);assert b'(-05:00)' in m.tx[-600:]
    assert [bytes(b) for b in m.banks]==saved
    passed('confirmed setting appends committed flash record without erasing or touching RTC/EEPROM/SRAM/EUI; repeat does not write; CLOCK/TIME/RESET retain offset')
    # Fill remaining shared slots: fail safely, keep last committed setting.
    for pos in range(0x1C40,0x2000,32):m.banks[3][pos:pos+32]=bytes(32)
    launch(cpu,m);prior=snapshot(m);out=cmd(cpu,m,b'OFFSET +05:30\rYES\r')
    assert b'Offset not saved' in out and snapshot(m)==prior
    cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m);prior=snapshot(m);m.fault='timeout'
    out=cmd(cpu,m,b'OFFSET +05:45\rYES\r');m.fault=None
    assert b'Offset not saved' in out and not any(e[0]=='erase' for e in m.events)
    assert bytes(m.bus.ee)==prior[1] and bytes(m.bus.rtc_regs)==prior[2]
    out=cmd(cpu,m,b'OFFSET ?\r');assert b'+00:00' in out,out
    assert m.ram[0xF4]==0
    passed('full record area and flash timeout refuse without erase or UTC/EEPROM writes; interrupted setting ignored and NMI hold restored')
    # Reuse a loaded foreground CLOCK fixture to cut every programmed byte.
    cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m)
    m.banks[3][0x1C20:0x1C40]=record(-300)
    fixture_ram=bytes(m.ram);fixture_banks=[bytes(b) for b in m.banks]
    def save_fixture(cut=None):
        c,p=fresh(primary=layout());p.ram[:]=fixture_ram
        p.banks=[bytearray(b) for b in fixture_banks];p.spi.banks=p.banks
        p.ram[CM['symbols']['OFFSET_PENDING']:CM['symbols']['OFFSET_PENDING']+2]=(345).to_bytes(2,'little')
        p.cut_after=cut
        return c,p
    cpu,done=save_fixture();invoke(cpu,CM['symbols']['OFFSET_SAVE']);assert cpu.p&cpu.CARRY
    writes=len(done.events);assert writes>0
    for cut in range(1,writes+1):
        cpu,partial=save_fixture(cut)
        try:invoke(cpu,CM['symbols']['OFFSET_SAVE'])
        except k.model.PowerCut:pass
        partial.cut_after=None;cpu.sp=255;partial.ram[0xF4]=0
        invoke(cpu,CM['symbols']['TZ_READ'])
        actual=int.from_bytes(partial.ram[CM['symbols']['TZ_OFFSET']:CM['symbols']['TZ_OFFSET']+2],'little',signed=True)
        assert actual==(345 if cut==writes else -300),(cut,writes,actual)
        assert bytes(partial.banks[3][:0x1C00])==fixture_banks[3][:0x1C00]
        assert bytes(partial.banks[3][0x1C00:0x1C20])==fixture_banks[3][0x1C00:0x1C20]
    passed(f'all {writes} interrupted append checkpoints retain old offset until commit; identity and journal code preserved')
    cpu,m=fresh(primary=layout());boot(cpu);launch(cpu,m);before=snapshot(m)
    out=cmd(cpu,m,b'SET 2026-10-09 02:55:20\rYES\r\r')
    assert b'Local UTC offset +/-HH:MM' in out,out[-800:]
    assert [bytes(b) for b in m.banks]==before[0]
    passed('successful initial UTC SET asks for local offset; Enter retains +00:00 without a settings write')
    cpu,m=fresh(primary=layout());offset=META['local_asset_address']-0x8000;m.banks[2][offset+40]^=1;boot(cpu)
    helper_error=b'Local time unavailable' if META.get('compact_boot_local') else b'Local display unavailable'
    assert helper_error in m.tx and b'B3> ' in m.tx
    cpu,m=fresh(off=True);boot(cpu);assert b'RTCC: Local' not in m.tx and not m.bus.accesses and not m.spi.frames
    passed('corrupt helper asset refused; EDU OFF omits device/local blocks and performs no bus I/O')
    report=dict(passed=True,checks=checks,artifacts=META['artifacts'],local_asset_sha256=META['local_asset_sha256'],clock_sha256=CM['sha256'],board_access=False,boards_flashed=False)
    (OUT/'local-time-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    import sys
    extra() if '--extra' in sys.argv else main()
