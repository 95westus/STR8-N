"""Model exact B2:8 AUTO/copy tests and accounted original-sector restoration."""
import hashlib,json
from test_v2_storage import cmd,k,OUT
from test_v2_workspace import fresh


def main():
    cpu,m=fresh();cpu.pc=0x7E67;cmd(cpu,m,b'')
    before=[bytes(b) for b in m.banks];ee=bytes(m.bus.ee);rtc=bytes(m.bus.rtc_regs)
    assert before[2][:4096]==b'\xff'*4096
    old_counts=k.model.counts(k.model.latest(m.banks))
    program=bytes.fromhex('EE 00 27 4C 67 7E');m.ram[0x2600:0x2606]=program;m.ram[0x2700]=0
    assert b'SAVE B02:8000' in cmd(cpu,m,b'S 2 AUTO 2600 2605 B23FLASH\r')
    m.ram[0x2600:0x2606]=bytes(6)
    assert b'Done' in cmd(cpu,m,b'R 2 B23FLASH L\r') and m.ram[0x2600:0x2606]==program
    cmd(cpu,m,b'R 2 B23FLASH\r');assert m.ram[0x2700]==1
    assert b'BANK MAINT 1.8' in cmd(cpu,m,b'R MAINT\r')
    assert b'CANCELED' in cmd(cpu,m,b'X 2 B23FLASH S CANCEL\rN\r')
    assert b'Copied and verified' in cmd(cpu,m,b'X 2 B23FLASH S B23COPY\rY\r')
    result=cmd(cpu,m,b'X S B23COPY 2 B23RETURN\rY\r')
    assert b'Destination B02:80' in result and b'Copied and verified' in result,result
    cmd(cpu,m,b'Q\r');m.ram[0x2700]=0
    cmd(cpu,m,b'R 2 B23RETURN\r');assert m.ram[0x2700]==1
    assert bytes(m.banks[2][4096:])==before[2][4096:]
    assert b'B23FLASH' in cmd(cpu,m,b'T 2\r')
    assert b'B23RETURN' in cmd(cpu,m,b'T 2\r')
    # Exact original sector is erased FF; cleanup reuses verified MAINT buffer.
    cmd(cpu,m,b'R MAINT\rR 2 8000-8FFF\rF 0000-0FFF FF\r')
    assert m.ram[0x5000:0x6000]==before[2][:4096]
    protected=cmd(cpu,m,b'W 3 8000\r');assert b'WRITE? TYPE Y>' not in protected
    snapshot=[bytes(b) for b in m.banks]
    assert b'CANCELED' in cmd(cpu,m,b'W 2 8000\rN\r') and [bytes(b) for b in m.banks]==snapshot
    assert b'VERIFIED' in k.model.command(cpu,b'W 2 8000\rY\r',80000000)
    assert bytes(m.banks[2])==before[2]
    counts=old_counts[:];counts[16]+=1
    assert k.model.counts(k.model.latest(m.banks))==counts
    assert [event for event in m.events if event[0]=='erase']==[('erase',2,0x8000,255)]
    assert bytes(m.bus.ee)==ee and bytes(m.bus.rtc_regs)==rtc
    cmd(cpu,m,b'Q\r')
    report=dict(passed=True,artifacts=k.REPORT['artifacts'],program_hex=program.hex(),
                native_auto=True,flash_restore_run=True,maint_both_copy_directions=True,
                original_b2_restored=True,protected_refusal=True,cancel_refusal=True,
                cleanup_erases=[dict(bank=2,sector=8)],erase_delta_index=16,
                rtc_eeprom_unchanged=True,model_only=True)
    (OUT/'flash-roundtrip-model.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS beta23 AUTO/save/restore/run, MAINT flash-SRAM-flash, canceled/protected refusal and exact B2:8 cleanup')


if __name__=='__main__':main()
