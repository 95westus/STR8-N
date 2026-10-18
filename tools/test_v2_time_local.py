"""No-board instruction tests for one-line TIME and unchanged detailed CLOCK."""
import json,hashlib
from datetime import datetime,timedelta
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_local_time import record
from test_v2_storage import cmd

META=json.loads((OUT/'build.json').read_text())
def content(text,echo=b'TIME'):
    return [line for line in text.split(b'\r\n') if line and line not in (echo,b'B3> ')]
def bcd(n):return n//10*16+n%10

def main():
    assert META['time_local_only'];checks=[]
    cpu,m=fresh(primary=layout());boot(cpu)
    cases=[(datetime(2026,10,9,2,55,20),x) for x in (-720,-300,0,330,345,840)]
    cases += [(datetime(2000,3,1,0,1,2),-300),(datetime(2099,12,31,23,59,58),840)]
    for dt,offset in cases:
        m.bus.rtc_regs[:9]=bytes((0x80|bcd(dt.second),bcd(dt.minute),bcd(dt.hour),0x28|dt.isoweekday(),bcd(dt.day),bcd(dt.month),bcd(dt.year%100),0x80,18))
        m.banks[3][0x1C20:0x1C40]=record(offset)
        before=snapshot(m);scratch=bytes(m.ram[0x6B00:0x6C00]);user=bytes(m.ram[0x200:0x6500]);mode=m.ram[0x7D25]
        text=cmd(cpu,m,b'TIME\r');local=dt+timedelta(minutes=offset);minutes=abs(offset)
        wanted=f'{local:%a %Y-%m-%d %H:%M:%S} ({"-" if offset<0 else "+"}{minutes//60:02d}:{minutes%60:02d})'.encode()
        assert content(text)==[wanted],(offset,text,wanted)
        assert snapshot(m)==before and not m.events
        assert bytes(m.ram[0x200:0x6500])==user and bytes(m.ram[0x6B00:0x6C00])==scratch and m.ram[0x7D25]==mode
    (OUT/'time-local-preview.txt').write_bytes(text)
    checks.append('eight exact one-line TIME cases: UTC/fractional offsets, previous-day/leap/year rollover, and complete preservation')
    print('PASS',checks[-1],flush=True)
    for fault in ('absent','stopped','invalid','edu-off','corrupt-local','corrupt-status'):
        cpu,m=fresh(off=fault=='edu-off',primary=layout());boot(cpu)
        if fault=='absent':m.ram[0x7D2A]=0
        elif fault=='stopped':m.bus.rtc_regs[0]&=0x7F;m.bus.rtc_regs[3]&=~0x20
        elif fault=='invalid':m.bus.rtc_regs[1]=0x7A
        elif fault=='corrupt-local':m.banks[2][META['local_asset_address']-0x8000+40]^=1
        elif fault=='corrupt-status':m.banks[2][META['status_asset_address']-0x8000+40]^=1
        before=snapshot(m);reclaimed=bytes(m.ram[0x6500:0x6700]);accesses=len(m.bus.accesses)
        text=cmd(cpu,m,b'TIME\r');lines=content(text)
        assert len(lines)==1 and not any(x in text for x in (b'UTC ',b'Trim ',b'2026-')),text
        assert snapshot(m)==before and not m.events
        if fault in ('absent','edu-off'):assert len(m.bus.accesses)==accesses
        if fault=='edu-off':assert bytes(m.ram[0x6500:0x6700])==reclaimed
    checks.append('absent/stopped/invalid RTC, EDU OFF and corrupt sealed assets fail concisely without stale dates or writes')
    print('PASS',checks[-1],flush=True)
    cpu,m=fresh(primary=layout());m.banks[3][0x1C20:0x1C40]=record(-300)
    body=(OUT/'clock/clock.bin').read_bytes()
    image=b'SR\x01\x3F\0\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    m.banks[1][0x3000:0x3000+len(image)]=image
    boot(cpu);before=snapshot(m)
    text=cmd(cpu,m,b'R CLOCK\r')
    assert b'\r\nUTC ' in text and b'RTCC: Local' in text and b'54:10:EC:B6:64:AF' in text,text
    (OUT/'clock-detail-preview.txt').write_bytes(text)
    for command,wanted in ((b'STATUS',b'RTC registers (raw):'),(b'TRIM',b'Trim'),(b'EUI',b'54:10:EC:B6:64:AF'),(b'HISTORY',b'No saved event in requested history.'),(b'OFFSET',b'-05:00')):
        reply=cmd(cpu,m,command+b'\r');assert wanted in reply,(command,reply)
        if command==b'STATUS':assert b'Running: yes' in reply and b'Backup enabled: yes' in reply,reply
    assert snapshot(m)==before and not m.events
    old=OUT.parent/'v2-startup-fifo'
    unchanged=['clock/clock.bin','str8n-v2-recovery-f000-ffff.bin','str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin']
    if not META.get('apps_listing_fixed'):unchanged.append('str8n-v2-recovery-e000-efff.bin')
    if META.get('f_only_bootstrap'):
        unchanged=['clock/clock.bin','local-display/asset.bin','boot-status/asset.bin']
        old=OUT.parent/'v2-fix004'
    if META.get('boot_dialog_order'):
        unchanged=['clock/clock.bin','maint/board-name.bin',
            'str8n-v2-recovery-f000-ffff.bin','str8n-v2-recovery-e000-efff.bin',
            'str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin']
        old=OUT.parent/'v2-beta25'
    for name in unchanged:
        assert (OUT/name).read_bytes()==(old/name).read_bytes(),name
    checks.append('R CLOCK retains detailed UTC/local/status/trim/EUI/history/offset; expected unchanged binaries verified')
    print('PASS',checks[-1],flush=True)
    (OUT/'time-local-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],
        local_asset_sha256=META['local_asset_sha256'],status_asset_sha256=META['status_asset_sha256'],board_access=False,boards_flashed=False),indent=2)+'\n')

if __name__=='__main__':main()
