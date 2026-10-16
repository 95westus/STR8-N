"""Focused model-only EDU journal and RAM-worker checks for beta28."""
import json
from beta4_migration import journal
import test_v2_beta28_candidate as t
from test_v2_sram_store import console

def main():
    checks=[];cpu,m=t.fixture();before=t.snapshot(m)
    print('CHECK EDU confirmed mode journal',flush=True)
    text=t.command(cpu,m,b'R EDU\rOFF\rY\rQ\r');assert b'Saved; RESET required.' in text,text[-700:]
    assert journal(m.banks[3])[8+13]==0xA5
    assert t.snapshot(m)[1:]==before[1:]
    m.tx.clear();cpu.pc=0xF004;t.boot(cpu);assert b'EDU OFF' in m.tx,bytes(m.tx[-500:])
    area=bytes(m.ram[0x200:0x6700]);frames=len(m.spi.frames);accesses=len(m.bus.accesses)
    text=t.command(cpu,m,b'R SRAM\r');assert b'SRAM 1.3' not in text and text.endswith(b'B3> '),text[-500:]
    assert bytes(m.ram[0x200:0x6700])==area and len(m.spi.frames)==frames and len(m.bus.accesses)==accesses
    text=t.command(cpu,m,b'R EDU\rON\rY\rQ\r');assert b'Saved; RESET required.' in text and journal(m.banks[3])[8+13]==0,text[-700:]
    assert t.snapshot(m)[1:]==before[1:]
    checks.append('XIP EDU confirmed OFF/ON journal updates, activation at reset, OFF SRAM refusal without device or reclaimed-RAM access')
    print('PASS',checks[-1],flush=True)
    cpu,m=t.fixture();start=t.S['X28_GATE_IMAGE']-0x8000
    m.ram[0x7B90:0x7B90+t.X['ram_gate_bytes']]=m.banks[2][start:start+t.X['ram_gate_bytes']];m.ram[0x7BFA]=3;m.ram[0x7BFB]=3
    m.banks[1][:4096]=bytes(4096);m[0x7FEC]=(m.ram[0x7FEC]&0x11)|0xEC
    print('CHECK MAINT RAM erase worker',flush=True)
    text=console(cpu,m,b'E 1 8\rY\r',entry=t.S['MM_START'],limit=80000000)
    assert b'VERIFIED' in text and m.banks[1][:4096]==b'\xff'*4096,text[-700:]
    assert any(e[0]=='erase' and e[1]==1 and e[2]==0x8000 for e in m.events),m.events[:10]
    assert m.bank==2
    checks.append('MAINT erases simulated B1 through the existing RAM worker and returns to B2; memory model forbids ROM fetch during flash busy')
    print('PASS',checks[-1],flush=True)
    report=dict(passed=True,checks=checks,utility_sha256=t.X['sha256'],board_access=False,boards_flashed=False,hardware_tested=False)
    (t.OUT/'beta28-worker-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
