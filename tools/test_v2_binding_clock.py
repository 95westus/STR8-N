"""Final CLOCK confirmation, full-storage refusal and stale-identity safeguards."""
import json,binascii
from test_v2_binding import boot,accept,launch,OLD,NEW,OUT,CLOCK,CLOCK_META,EQ,k

def main():
    checks=[]
    cpu,m=boot();output=launch(cpu);assert b', unbound' in output
    k.model.command(cpu,b'ACCEPT EUI\rNO\r',20000000);assert not m.events
    # The chip changes after the prompt but before YES: stale acceptance is refused.
    k.model.command(cpu,b'ACCEPT EUI\r',20000000)
    m.bus.ee[0xF2:0xF8]=NEW
    output=k.model.command(cpu,b'YES\r',20000000)
    assert b'acceptance not verified' in output and not m.events
    output=k.model.command(cpu,b'ACCEPT EUI\rYES\rEUI\rSTATUS\r',24000000)
    assert b'EUI remembered.' in output and b'Remembered EUI: 54:10:EC:B6:64:AF' in output
    assert m.ram[EQ['J_BIND_STATUS']]==1
    before=len(m.events);output=k.model.command(cpu,b'ACCEPT EUI\r',18000000)
    assert b'already remembered' in output and len(m.events)==before
    checks.append('final CLOCK requires exact YES, rejects a chip changed after its prompt and skips repeated acceptance')
    print('PASS',checks[-1],flush=True)
    cpu,full=boot(NEW)
    for n in range(32):
        body=b'EI\x01\0'+(n+1).to_bytes(4,'little')+OLD+bytes([255])*14
        record=body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')+b'\xff\0'
        full.banks[3][7168+n*32:7200+n*32]=record
    before=[bytes(b) for b in full.banks];regs=bytes(full.bus.rtc_regs);ee=bytes(full.bus.ee)
    assert accept(cpu,NEW)==EQ['J_BIND_FULL'] and not full.events and not full.bus.writes
    assert [bytes(b) for b in full.banks]==before and bytes(full.bus.rtc_regs)==regs and bytes(full.bus.ee)==ee
    output=launch(cpu);assert b', changed' in output
    output=k.model.command(cpu,b'ACCEPT EUI\rYES\r',22000000)
    assert b'Identity store full; no change.' in output and not full.events
    checks.append('all 32 occupied records cause bounded refusal without erase, code/identity loss or EEPROM/UTC changes')
    print('PASS',checks[-1],flush=True)
    (OUT/'binding-clock-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],clock_sha256=CLOCK_META['sha256'],hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
