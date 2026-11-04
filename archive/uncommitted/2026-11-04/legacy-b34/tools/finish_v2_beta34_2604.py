"""Repair installer return-bank selection and resume after the verified CLOCK step."""
import argparse
from pathlib import Path

import deploy_v2_beta34_fleet as f


def patched(stage):
    plan=f.read(stage/'upgrade/plan.json')
    cells,entry=f.m.read_s19(stage/'upgrade/installer.s19')
    at=plan['success_checkpoint']
    assert bytes(cells[at+i] for i in range(3))==b'\x4C\x04\xF0'
    select=f.read(f.BUILD/'migrator/manifest.json')['symbols']['V2W_SELECT']
    cells.update(dict(enumerate(b'\xA9\x03\x20'+select.to_bytes(2,'little')+b'\x4C\x04\xF0',at)))
    assert max(cells)<0x6200
    return cells,entry


def actual_return(stage,cells,entry,expect_bank):
    import test_v2_rtc_upgrade as test
    plan=f.read(stage/'upgrade/plan.json'); banks=f.images(stage/'prior-verified','b')
    allowed={(s['bank'],s['sector']) for s in plan['steps']}
    expected=f.images(stage/'upgrade','expected-b')
    records={}
    for row in plan['commit_records']:
        b,a=row['bank'],row['address'];i=a-0x8000;n=int.from_bytes(expected[b][i+6:i+8],'little')
        records[b,a]=expected[b][i:i+24+n]
    mem=test.Memory(banks,allowed,{},commit_records=records);mem.require_maintenance_commit=False
    for a,v in cells.items():mem.ram[a]=v
    cpu=test.CPU(memory=mem,pc=entry);mem.cpu=cpu;mem.rx.extend(b'Y\r')
    for i,s in enumerate(plan['steps']):
        token=f'SEND 4096 BYTES FOR B{s["bank"]}:{s["sector"]:X}\r\n'.encode()
        test.run(cpu,lambda:token in bytes(mem.tx));mem.tx.clear()
        mem.rx.extend((stage/f'upgrade/transfer-{i:02d}.bin').read_bytes())
    test.run(cpu,lambda:cpu.pc==0xF004)
    assert plan['completion_token'].encode() in mem.tx
    assert mem.bank==expect_bank,(mem.bank,expect_bank)
    assert [bytes(b) for b in mem.banks]==expected
    if expect_bank==3:assert mem[0xF004]==0x4C
    else:assert mem[0xF004]==0xFF
    print('PASS actual installer end bank',stage.name,mem.bank,flush=True)
    return dict(passed=True,return_bank=mem.bank,reset_entry_byte=mem[0xF004],
                final_hashes=[f.sha(bytes(b)) for b in mem.banks])


def prepare():
    clock=f.OUT/'2604/clock';main=f.OUT/'2604/firmware'
    old,entry=f.m.read_s19(clock/'upgrade/installer.s19')
    old_result=actual_return(clock,old,entry,1)
    fixed,entry=patched(clock);fixed_result=actual_return(clock,fixed,entry,3)
    (clock/'upgrade/installer-bank-fixed-not-flashed.s19').write_bytes(f.m.s19(fixed,entry))
    cells,entry=patched(main)
    fixed_main=actual_return(main,cells,entry,3)
    for name in ('installer.s19','plan.json','model-check.json','functional.json'):
        p=main/'upgrade'/name;target=p.with_name(p.stem+'-before-bank-fix'+p.suffix)
        assert not target.exists();target.write_bytes(p.read_bytes())
    image=f.m.s19(cells,entry);(main/'upgrade/installer.s19').write_bytes(image)
    plan=f.read(main/'upgrade/plan.json');plan.update(installer_sha256=f.sha(image),
        explicit_return_bank=3,return_fix_source_sha256=f.sha(Path(__file__).read_bytes()))
    f.save(main/'upgrade/plan.json',plan)
    f.save(f.OUT/'2604/return-bank-regression.json',dict(passed=True,
        original_clock_return=old_result,fixed_clock_return=fixed_result,fixed_main_return=fixed_main,
        fixed_clock_flashed=False,main_installer_sha256=f.sha(image),
        source_sha256=f.sha(Path(__file__).read_bytes())))
    f.rehearse('2604','firmware');f.functional('2604','firmware')


def resume():
    root=f.OUT/'2604';assert f.read(root/'reset-recovery/report.json')['passed']
    assert f.read(root/'return-bank-regression.json')['passed']
    p=f.read(root/'plan.json');assert p['stages']==['clock','firmware']
    f.save(root/'full-plan-before-resume.json',p)
    p.update(stages=['firmware'],original_hashes=f.read(root/'clock/upgrade/plan.json')['expected_hashes'],
             completed_stages=['clock'],physical_reset_recovery='reset-recovery/report.json')
    f.save(root/'plan.json',p)
    source=(root/'hardware').resolve();dest=(root/'clock-attempt-hardware').resolve()
    assert source.is_relative_to(f.OUT.resolve()) and dest.is_relative_to(f.OUT.resolve())
    assert source.is_dir() and not dest.exists()
    source.rename(dest)
    f.audit('2604');f.install('2604')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','resume'))
    globals()[parser.parse_args().stage]()
