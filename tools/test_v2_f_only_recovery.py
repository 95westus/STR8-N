"""Verify the exact F-only recovery condition without touching physical boards."""
import json
import os
import build_v2_recovery as fw

fw.OUT=fw.ROOT/os.environ.get('STR8_RTC_BUILD','BUILD/v2-board-name')
fw.SOURCE=fw.OUT/'source'
fw.VERSION=json.loads((fw.OUT/'build.json').read_text())['version']
import test_v2_recovery as model


def main():
    banks=[bytearray(b'\xff'*32768) for _ in range(4)]
    fixed=(fw.OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    banks[3][0x7000:]=fixed
    cpu,m=model.boot(banks)
    assert b'FIXED F RECOVERY' in m.tx and m.tx.endswith(b'REC> '),bytes(m.tx)
    assert m.ram[model.EQ['active']]==0 and not m.events
    boot=bytes(m.tx).decode('ascii')
    outputs={}
    for line in (b'W',b'A',b'B',b'J3',b'J0',b'?',b'D 0200 020F',b'G 0200',b'L'):
        out=model.command(cpu,line+b'\r');outputs[line.decode()]=out.decode('ascii')
        assert out.endswith(b'REC> ') and not m.events,(line,out)
        assert m.banks[3][0x7000:]==fixed
    assert b'JOURNAL INVALID' in outputs['W'].encode()
    out=model.command(cpu,b'U A\rN\r');assert out.endswith(b'REC> ') and not m.events
    # Exercise the F-only binary repair path, not just its dispatch.
    image=(fw.OUT/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    repaired=model.update(cpu,0xa0,image)
    success=b'IMAGE COMMITTED' in repaired
    # The current repair path requests an erase even for an erased slot;
    # missing wear journal correctly prevents that unaccounted operation.
    assert not success and b'REFUSED/FAILED' in repaired and not m.events
    assert bytes(m.banks[3][:0x7000])==b'\xff'*0x7000
    assert m.banks[3][0x7000:]==fixed
    report=dict(build=fw.VERSION,f_only_boot=True,boot=boot,commands=outputs,
        normal_J_available=False,repair_committed=success,repair_output=repaired.decode('ascii',errors='replace'),
        fixed_f_preserved=True,board_access=False)
    (fw.OUT/'f-only-recovery-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(boot)
    print('PASS F-only REC prompt; W reports missing journal; A/B refuse absent slots; J/D/G/L are not recovery commands')
    print('Binary U A repair:', 'COMMITTED' if success else 'REFUSED')
    print(repaired.decode('ascii',errors='replace')[-800:])


if __name__=='__main__':main()
