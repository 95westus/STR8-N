"""Rehearse 2604's exact foreign-layout repair without hardware access."""
import os,json,binascii
from pathlib import Path
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta25-b24g34'
from test_v2_status import fresh,boot,layout,OUT
from test_v2_storage import cmd
from test_v2_spi_resident import k
from qualify_v2_beta23_power_retention import records

def main():
    root=Path('output/qualification/beta25-recovery-2026-10-14/2604');banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    prior=Path('output/qualification/beta25-fleet-2026-10-14/2604/retained/devices-before/eeprom-0.bin').read_bytes()
    c,m=fresh(primary=layout());m.banks=[bytearray(x) for x in banks];m.spi.banks=m.banks;m.bus.ee[:128]=prior[:128];m.bus.ee[0xFF]=prior[128];m.bus.ee[0xF2:0xF8]=prior[131:137]
    m.bus.rtc_regs[:9]=bytes.fromhex('90 11 02 3C 15 10 26 00 0C');m.bus.rtc_regs[0x18:0x20]=bytes.fromhex('02 22 14 70 03 22 14 70')
    meta=json.loads((OUT/'build.json').read_text());k.model.run(c,lambda:c.pc==meta['boot']['BOOT_STARTUP_DOTS'],30000000);m.rx.extend(b'B');boot(c)
    cmd(c,m,b'R CLOCK\r');assert b'History unavailable/error 90' in cmd(c,m,b'HISTORY\r')
    before=bytes(m.bus.ee);cmd(c,m,b'CLEAR ALL\rNO\r');assert bytes(m.bus.ee)==before
    text=cmd(c,m,b'CLEAR ALL\rDELETE ALL\r');assert b'History cleared.' in text,text
    assert m.bus.rtc_regs[3]&0x10 and not records(m.bus.ee[:128])
    text=cmd(c,m,b'ACK\rYES\r');assert b'latch verified clear' in text,text
    assert not m.bus.rtc_regs[3]&0x10 and list(records(m.bus.ee[:128]).values())==[1]
    assert m.bus.ee[30]==0 and m.bus.rtc_regs[7:9]==b'\0\x0C'
    assert bytes(m.bus.ee[128:])==before[128:] and not m.events and [bytes(b) for b in m.banks]==banks
    (root/'clock-history-model.json').write_text(json.dumps(dict(passed=True,cancel_preserved_foreign_bytes=True,initialized_journal=True,outage_saved_before_ack=True,sequence=1,rtc_control_trim_preserved=True,factory_status_preserved=True,flash_unchanged=True,board_access=False),indent=2)+'\n')
    print('PASS exact foreign history: cancel preserves; initialization then verified outage ACK; UTC/control/trim/factory/flash preserved',flush=True)

if __name__=='__main__':main()
