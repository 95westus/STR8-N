"""Model identity binding, interrupted flash appends, boot comparison and CLOCK."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-binding')
import json
from pathlib import Path
from beta4_migration import read_s19
from test_v2_journal import Memory,call,EQ,OUT,k
from build_v2_rtc_binding import merge_identity_tail

ROOT=Path(__file__).resolve().parents[1]
OLD=bytes.fromhex('5410ecb664d3');NEW=bytes.fromhex('5410ecb664af')
CLOCK=ROOT/'BUILD/v2-clock-1.4'
CELLS,ENTRY=read_s19(CLOCK/'clock.s19')
CLOCK_META=json.loads((CLOCK/'build.json').read_text())

def boot(identity=OLD,banks=None,absent=False):
    m=Memory()
    if banks is not None:m.banks=[bytearray(b) for b in banks]
    m.bus.ee[0xF2:0xF8]=identity
    if absent:m.bus.devices.pop(0x57);m.bus.devices.pop(0x6F)
    cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu
    k.model.run(cpu,lambda:k.model.waiting(cpu),22000000)
    return cpu,m

def accept(cpu,identity=OLD,key=b'AI'):
    cpu.memory.ram[EQ['J_BIND_REQUEST']:EQ['J_BIND_REQUEST']+6]=identity
    return call(cpu,8,key=key)

def hold(cpu):
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),16000000)

def launch(cpu):
    hold(cpu)
    for a,v in CELLS.items():cpu.memory.ram[a]=v
    return k.model.command(cpu,b'G 2000\r',22000000)

def main():
    checks=[]
    cpu,m=boot();assert b'RTCC: EUI 54:10:EC:B6:64:D3, unbound' in m.tx and not m.events
    before=bytes(m.bus.ee);registers=bytes(m.bus.rtc_regs);code=bytes(m.banks[3][4096:7168])
    assert accept(cpu,key=b'XX')==6 and not m.events
    assert accept(cpu,NEW)==9 and not m.events
    assert accept(cpu)==0
    assert m.ram[EQ['J_BIND_STATUS']]==1 and bytes(m.ram[EQ['J_REMEMBERED']:EQ['J_REMEMBERED']+6])==OLD
    assert all(kind=='program' and bank==3 and 0x9C00<=address<0xA000 for kind,bank,address,value in m.events)
    assert bytes(m.banks[3][4096:7168])==code and bytes(m.bus.ee)==before and bytes(m.bus.rtc_regs)==registers and not m.bus.writes
    count=len(m.events);assert accept(cpu)==0 and len(m.events)==count
    saved=[bytes(b) for b in m.banks]
    cpu,same=boot(banks=saved);assert b', unbound' not in same.tx and b', changed' not in same.tx and not same.events
    cpu,changed=boot(NEW,saved);assert b'RTCC: EUI 54:10:EC:B6:64:AF, changed' in changed.tx and not changed.events
    cpu,missing=boot(banks=saved,absent=True)
    assert b'RTCC: EUI unavailable' in missing.tx and b'RTCC: Time unavailable' in missing.tx and not missing.events
    assert call(cpu,7)==0 and bytes(missing.ram[EQ['J_REMEMBERED']:EQ['J_REMEMBERED']+6])==OLD
    checks.append('unbound/match/changed/unavailable boot states; explicit binding touches only existing-sector tail; repeated acceptance writes nothing')
    print('PASS',checks[-1],flush=True)
    # Every interruption in a replacement append retains the old record until commit.
    cpu,replacement=boot(NEW,saved);assert accept(cpu,NEW)==0;writes=len(replacement.events)
    for cut in range(1,writes+1):
        cpu,partial=boot(NEW,saved);partial.cut_after=cut
        try:accept(cpu,NEW)
        except k.model.PowerCut:pass
        cpu,recovered=boot(NEW,[bytes(b) for b in partial.banks]);assert call(cpu,7)==0
        expected=NEW if cut==writes else OLD
        assert bytes(recovered.ram[EQ['J_REMEMBERED']:EQ['J_REMEMBERED']+6])==expected
        assert bytes(recovered.banks[3][4096:7168])==code and not recovered.events
    cpu,failed=boot(NEW,saved);failed.fault='timeout';assert accept(cpu,NEW)==EQ['J_BIND_WRITE_FAILED']
    assert call(cpu,7)==0 and bytes(failed.ram[EQ['J_REMEMBERED']:EQ['J_REMEMBERED']+6])==OLD
    checks.append('each interrupted append preserves old committed identity; commit switches atomically; timeout cannot damage sealed code')
    print('PASS',checks[-1],flush=True)
    # Tail preservation is explicit for firmware upgrades; old formats initialize fresh.
    candidate=(OUT/'str8n-journal-9000-9fff.bin').read_bytes()
    merged=merge_identity_tail(saved[3][4096:8192],candidate)
    assert merged[:3072]==candidate[:3072] and merged[3072:]==saved[3][7168:8192]
    assert merge_identity_tail((ROOT/'BUILD/v2-rtc-eui/str8n-journal-9000-9fff.bin').read_bytes(),candidate)==candidate
    checks.append('upgrade merge preserves all identity-tail bytes without changing the sealed code prefix')
    print('PASS',checks[-1],flush=True)
    cpu,m=boot(NEW,saved);output=launch(cpu);assert b'CLOCK 1.4' in output and b', changed' in output and b'Remembered EUI: 54:10:EC:B6:64:D3' in output
    k.model.command(cpu,b'ACCEPT EUI\rNO\r',22000000);assert not m.events
    output=k.model.command(cpu,b'ACCEPT EUI\rYES\rEUI\r',22000000)
    assert b'RTCC: EUI remembered.' in output and m.ram[EQ['J_BIND_STATUS']]==1
    before=len(m.events);output=k.model.command(cpu,b'ACCEPT EUI\r',18000000)
    assert b'already remembered' in output and len(m.events)==before
    k.model.command(cpu,b'Q\r',18000000)
    checks.append('CLOCK shows remembered/current EUI, cancels safely, accepts exact YES and skips unchanged identities')
    print('PASS',checks[-1],flush=True)
    (OUT/'binding-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],clock_sha256=CLOCK_META['sha256'],power_cut_points=writes,hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
