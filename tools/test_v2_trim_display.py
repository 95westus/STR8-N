"""Execute the trim display candidate with signed, absent and coarse cases."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-trim-display')
import hashlib
import json
from fractions import Fraction
from test_v2_status import fresh,boot,layout,OUT
from test_v2_storage import cmd
from beta4_migration import crc


def invoke(cpu, entry):
    sp=cpu.sp;cpu.stPushWord(0x1ff);cpu.pc=entry
    for _ in range(200000):
        if cpu.pc==0x200:break
        cpu.step()
    else:raise AssertionError('formatter did not return')
    assert cpu.sp==sp


def main():
    meta=json.loads((OUT/'build.json').read_text());s=meta['status_symbols']
    assert meta['trim_display'] and meta['status_asset_bytes']==2560
    assert crc((OUT/'boot-status/asset.bin').read_bytes())==0
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(OUT.parent/'v2-storage/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    cpu,m=fresh(primary=layout());boot(cpu)
    assert b'; trim 0' in m.tx
    # Exact rational expected correction for every normal OSCTRIM magnitude.
    for magnitude in range(128):
        for fast in (False,True):
            m.ram[0x66C0]=0;m.ram[0x66C1]=4;m.ram[0x66D2]=0x80
            m.ram[0x66D3]=magnitude|(0x80 if fast else 0);m.ram[s['KIND']]=2
            start=len(m.tx);invoke(cpu,s['TRIM_DISPLAY']);out=bytes(m.tx[start:])
            sign=('+' if fast else '-') if magnitude else ''
            def half_up(value):return (2*value.numerator+value.denominator)//(2*value.denominator)
            ppm=half_up(Fraction(magnitude*100000000,983040))
            day=half_up(Fraction(magnitude*90000,1024))
            expected=f'RTCC: Trim {sign}{magnitude} steps: {sign}{ppm//100}.{ppm%100:02d} ppm, {sign}{day//1000}.{day%1000:03d} s/day correction'.encode()
            assert expected in out,(magnitude,fast,out,expected)
    for raw,expected in [(0,b'Trim 0 steps: 0.00 ppm, 0.000 s/day correction'),(18,b'Trim -18 steps: -18.31 ppm, -1.582 s/day correction'),(0x8E,b'Trim +14 steps: +14.24 ppm, +1.230 s/day correction')]:
        cpu,m=fresh(primary=layout());m.bus.rtc_regs[8]=raw
        pattern=bytes((i*17)&255 for i in range(0x6300));m.ram[0x200:0x6500]=pattern
        before=([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
        boot(cpu)
        sign=('+' if raw&128 else '-') if raw&127 else ''
        assert f'; trim {sign}{raw&127}'.encode() in m.tx
        out=cmd(cpu,m,b'TIME\r');assert expected in out,out
        assert m.ram[0x200:0x6500]==pattern
        assert before==([bytes(b) for b in m.banks],bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
    cpu,m=fresh(primary=layout());m.bus.rtc_regs[7]|=4;boot(cpu)
    assert b'; trim 0 coarse ON' in m.tx
    out=cmd(cpu,m,b'TIME\r');assert b'coarse ON; ppm/day unavailable' in out and b'0.00 ppm' not in out
    cpu,m=fresh(off=True);boot(cpu);out=cmd(cpu,m,b'TIME\r');assert b'Trim' not in out and b'RTCC: unavailable' in out
    cpu,m=fresh(primary=layout());m.bus.devices.pop(0x6F);boot(cpu);out=cmd(cpu,m,b'TIME\r');assert b'Trim' not in out
    cpu,m=fresh(primary=layout());offset=meta['status_asset_address']-0x8000;m.banks[2][offset+100]^=1;boot(cpu)
    assert b'Status unavailable' in m.tx and b'B3> ' in m.tx
    report=dict(passed=True,artifacts=meta['artifacts'],status_asset_sha256=meta['status_asset_sha256'],
        checked_normal_register_values=256,application_ram_preserved=True,flash_rtc_eeprom_sram_preserved=True,
        coarse_numerics_refused=True,off_and_missing_handled=True,corrupt_asset_refused=True,board_access=False)
    (OUT/'trim-display-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS trim display: all 256 signed register encodings, boot/TIME, normal/coarse/OFF/absent, full application and hardware preservation, sealed asset refusal.')

if __name__=='__main__':main()
