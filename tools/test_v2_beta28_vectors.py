"""Validate provider vectors and bind unchanged XIP-core qualification by bytes."""
import argparse,json
from pathlib import Path
import test_v2_beta28_candidate as t
from build_v2_spi_resident import sha

def main(prior):
    core=json.loads((prior/'beta28-test-results.json').read_text());workers=json.loads((prior/'beta28-worker-test-results.json').read_text())
    assert core['passed'] and workers['passed'] and core['utility_sha256']==workers['utility_sha256']==t.X['sha256']
    old=[(prior/f'b{i}.bin').read_bytes() for i in range(4)]
    new=[(t.OUT/f'candidate/b{i}.bin').read_bytes() for i in range(4)]
    for i in range(4):
        if i==2:
            assert new[i][:0x7FF6]==old[i][:0x7FF6]
        else:assert new[i]==old[i]
    checks=['All four candidate banks equal the fully model-qualified core image except B2:FFF6-FFFF vector/seal padding; complete utility bundle identical']
    print('CHECK final provider vectors and VERSION seal',flush=True)
    cpu,m=t.fixture();assert b'2.0b28' in m.tx
    assert b'2.0b28' in t.command(cpu,m,b'VERSION\r')
    text=t.command(cpu,m,b'R EDU\r');assert b'EDU 1.3' in text and m.bank==2
    m.rx.extend(b'?\r')
    for _ in range(60000000):
        if m.bank==2 and cpu.pc==t.S['ED_PROMPT']:break
        cpu.step()
    else:raise AssertionError('No XIP interrupt checkpoint')
    checkpoint=(cpu.pc,cpu.sp,cpu.a,cpu.x,cpu.y,cpu.p)
    for held in (0,1):
        m.ram[0xF4]=held;cpu.nmi();assert cpu.pc==t.META['vectors']['V2V_NMI']
        t.k.model.run(cpu,lambda:cpu.pc==checkpoint[0],1000)
        assert (cpu.sp,cpu.a,cpu.x,cpu.y)==checkpoint[1:5] and m.bank==2
    m.ram[0xF4]=0;cpu.p&=~cpu.INTERRUPT;cpu.irq();assert cpu.pc==t.META['vectors']['V2V_IRQ_BRK']
    t.k.model.run(cpu,lambda:cpu.pc==checkpoint[0],1000)
    assert cpu.sp==checkpoint[1] and m.bank==2
    cpu.p=checkpoint[5]
    # BRK must distinguish the software-interrupt frame and return to PC+2.
    m.ram[0x200:0x202]=b'\x00\xEA';cpu.pc=0x200;cpu.step()
    assert cpu.pc==t.META['vectors']['V2V_IRQ_BRK']
    t.k.model.run(cpu,lambda:cpu.pc==0x202,1000);assert cpu.sp==checkpoint[1] and m.bank==2
    cpu.pc=checkpoint[0];cpu.p=checkpoint[5]
    t.command(cpu,m,b'Q\r');assert m.bank==3
    checks.append('Actual B2 vector fetches dispatch NMI, held NMI, IRQ and BRK through initialized RAM handlers and resume XIP correctly')
    print('PASS',checks[-1],flush=True)
    # Warm reset from the provider bank routes through the initialized RAM ABI
    # and selects B3 before entering fixed recovery. B2 is not a cold boot bank.
    m[0x7FEC]=(m.ram[0x7FEC]&0x11)|0xEC;m.tx.clear();cpu.start_pc=None;cpu.reset()
    assert cpu.pc==t.META['vectors']['V2V_RAM_RESET_ENTRY']
    t.boot(cpu)
    assert b'2.0b28' in m.tx and m.bank==3
    checks.append('B2 reset vector reaches initialized RAM reset gateway, selects B3, and boots beta28')
    report=dict(passed=True,checks=checks,build_sha256=sha((t.OUT/'build.json').read_bytes()),utility_sha256=t.X['sha256'],prior_core_receipt_sha256=sha((prior/'beta28-test-results.json').read_bytes()),prior_worker_receipt_sha256=sha((prior/'beta28-worker-test-results.json').read_bytes()),board_access=False,boards_flashed=False,hardware_tested=False)
    (t.OUT/'beta28-vector-test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    qualification=dict(passed=True,version='2.0b28',candidate_only=True,build_sha256=report['build_sha256'],artifacts=t.META['artifacts'],core_regression_receipt=str((prior/'beta28-test-results.json').resolve()),worker_regression_receipt=str((prior/'beta28-worker-test-results.json').resolve()),unchanged_core_verified_by_exact_bank_comparison=True,vector_receipt='beta28-vector-test-results.json',board_access=False,boards_flashed=False,hardware_tested=False)
    (t.OUT/'beta28-qualification.json').write_text(json.dumps(qualification,indent=2)+'\n')
    for check in checks:print('PASS',check,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',type=Path,required=True);main(p.parse_args().prior)
