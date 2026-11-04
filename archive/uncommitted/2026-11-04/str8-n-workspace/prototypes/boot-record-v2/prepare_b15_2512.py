"""Build and qualify an exact captured-source b15 plan with success-only F restart."""
import argparse
import json
import shutil
import sys
import types
from pathlib import Path
import board_b15_2512 as live
import deployment_b15 as planning
import deployment_b15_model as native_model
import deployment_b07_model as frozen_model
import capture_native_2512 as capture
from installer.engine import legacy_transport as wire
from test_b14_core import load_core
from test_b14_raw import start,feed

ROOT,HERE=live.ROOT,live.HERE


def patched_installer(native):
    cells,entry=wire.read_s19(native/'installer-model-only.s19')
    symbols=live.io.read(planning.TEMPLATE/'symbols.json');halt=symbols['MIG_HALT'];failure=halt+10
    assert bytes(cells[a] for a in range(halt,halt+3))==b'\x4c'+halt.to_bytes(2,'little')
    assert bytes(cells[a] for a in range(failure,failure+3))==b'\x4c'+halt.to_bytes(2,'little')
    # The failure tail must remain halted, even if F is partially programmed.
    cells.update(dict(enumerate(b'\x4c'+failure.to_bytes(2,'little'),failure)))
    cells.update(dict(enumerate(bytes.fromhex('4c04f0'),halt)))
    first,stop=symbols['MIG_DONE'],symbols['MIG_BAD']
    old=bytes(cells[a] for a in range(first,stop))
    assert old==live.OLD_DONE+b'\r\n\0'
    new=live.DONE+b'\r\n\0';assert len(new)<=len(old)
    cells.update(dict(enumerate(new+bytes(len(old)-len(new)),first)))
    return wire.s19(cells,entry)


def verify_software(target,folder):
    native=folder.parent/'plan-native';base=planning.verify(target,native)
    info=live.io.read(folder/'plan.json')
    expected=dict(base,installer_sha256=live.io.sha(patched_installer(native)),
        native_plan_sha256=live.io.sha((native/'plan.json').read_bytes()),
        success_only_software_restart=True)
    assert info==expected
    assert (folder/'installer-model-only.s19').read_bytes()==patched_installer(native)
    for n in range(3):assert (folder/f'transfer-{n:02d}.bin').read_bytes()==(native/f'transfer-{n:02d}.bin').read_bytes()
    return info


def prove_restart(memory,cpu,build,owner,checks,is816):
    assert cpu.pc==0x21d0
    cpu.step();assert cpu.pc==0xf004 and memory.bank==3
    core,_=load_core();core.GENERATION=0x8000000f
    h=core.Machine(build,'65c816-e' if is816 else '65c02',opaque=True)
    # Use the actual transaction's full postimage and RAM/peripheral state.
    h.m.banks[:]=[bytearray(b) for b in memory.banks];h.m.ram[:]=memory.ram
    h.c.pc=0xf004;h.c.processorCycles=cpu.processorCycles
    h.m.acia_writes.clear();h.m.tx.clear();h.m.acia_tx.clear()
    h.run(lambda:bytes(h.m.tx).endswith(live.io.MON))
    assert b'STR8-N 2.0proto b15 B3' in h.m.tx and h.m.ram[0x7d30]==0xb0
    n=len(h.m.tx);h.m.rx.extend(b'J3\r');h.run(lambda:len(h.m.tx)>n and bytes(h.m.tx).endswith(live.io.CHOICES))
    h.m.rx.append(ord('S'));h.run(lambda:bytes(h.m.tx).endswith(live.io.REC))
    h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    h.port_command(1,b'C1\r');before=bytes(h.m.ram[0x200:0x6500]);zp=bytes(h.m.ram[:0xe0])
    start(h,1);h.m.rx.append(3);h.run(lambda:bytes(h.m.tx).endswith(live.io.REC))
    assert bytes(h.m.ram[0x200:0x6500])==before and not h.m.events
    start(h,1);app=(ROOT/'BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin').read_bytes();feed(h,1,app)
    h.run(lambda:bytes(h.m.tx).endswith(live.io.CFG))
    show=h.port_command(1,b'B\r',live.io.CFG);assert b'DEFAULT=B\r\n' in show
    h.m.rx.extend(b'Q\r');h.run(lambda:bytes(h.m.tx).endswith(live.io.MON))
    sy=live.io.read(ROOT/'BUILD/pr04-b14-ram-config-r1/symbols.json')['core/ram-config']
    expected=bytearray(app);expected[sy['CONFIG_ROW']-0x200]=4
    assert bytes(h.m.ram[0x200:0x200+len(app)])==expected
    n=len(h.m.tx);h.m.rx.extend(b'J3\r');h.run(lambda:len(h.m.tx)>n and bytes(h.m.tx).endswith(live.io.CHOICES))
    h.m.rx.append(ord('S'));h.run(lambda:bytes(h.m.tx).endswith(live.io.REC));h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
    h.port_command(1,b'C1\r');start(h,1)
    feed(h,1,(live.io.SERVICE/'payload/mon-service-load.bin').read_bytes());h.run(lambda:bytes(h.m.tx).endswith(live.io.SVC))
    h.port_command(1,b'W'+owner+wire.crc(owner).to_bytes(2,'little'),live.io.SVC)
    assert bytes(h.m.ram[0x200:0x6500])==owner and bytes(h.m.ram[:0xe0])==zp and not h.m.events
    checks.append(dict(passed=True,cpu=h.name,success_only_reset=True,default_B_boot=True,
        Ctrl_C_preserves_RAM=True,normal_BIN_exact=True,whole_owner_RAM_restore=True))


def main(run):
    assert run.resolve().is_relative_to((ROOT/'output/qualification').resolve())
    state=live.io.read(run/'state.json');assert state['capture_passed']
    assert not (run/'live-model-proof.json').exists()
    qualification=live.io.read(live.BUILD/'b15-qualification.json')
    assert qualification['passed'] and qualification['checks']==512
    for name,digest in qualification['source_sha256'].items():assert live.io.sha((HERE/name).read_bytes())==digest
    banks=[(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert banks==[(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]==live.source_banks()
    owner=(run/'owner-ram.bin').read_bytes()
    cap=run/'capture';capture.write(cap,banks,owner,evidence=dict(fresh_run=str(run),owner_authorized=True,
        repeated_hardware_reads=True,authorization_sha256=live.io.sha((run/'authorization.json').read_bytes())))
    for name in ('owner-zp.bin',):live.io.durable(cap/name,(run/name).read_bytes())
    # Owner ZP is separately retained; do not mutate the native capture manifest.
    native=run/'plan-native'
    sys.argv=[__file__,'--target',str(live.BUILD),'--capture',str(cap),'--out',str(native),'--qualify']
    planning.main()
    folder=run/'plan';shutil.copytree(native,folder)
    image=patched_installer(native);live.io.durable(folder/'installer-model-only.s19',image)
    info=live.io.read(native/'plan.json')
    info.update(installer_sha256=live.io.sha(image),native_plan_sha256=live.io.sha((native/'plan.json').read_bytes()),
                success_only_software_restart=True)
    live.io.save(folder/'plan.json',info);verify_software(live.BUILD,folder)
    # Reuse the exact native CPU/NOR model with only its two halt predicates
    # and completion-token matching adapted for the reviewed restart patch.
    source=Path(frozen_model.__file__).read_text().replace('import deployment_b07 as planning','import deployment_b15 as planning')
    source=source.replace("cpu.pc == symbols['MIG_HALT']","cpu.pc in (symbols['MIG_HALT'], symbols['MIG_HALT']+10)")
    token='        def until(self, token, seconds=45):\n'
    assert source.count(token)==1
    source=source.replace(token,token+"            if token == OLD_DONE: token = DONE\n")
    after="    expected = [(plan / f'expected-b{n}.bin').read_bytes() for n in range(4)]\n"
    assert source.count(after)==1
    source=source.replace(after,after+'    prove_restart(memory,cpu,pkg,OWNER,POST_CHECKS,is816)\n')
    module=types.ModuleType('b15_software_native_model');module.__file__=str(HERE/'deployment_b15_model.py')
    checks=[];module.OLD_DONE=live.OLD_DONE;module.DONE=live.DONE;module.OWNER=owner
    module.prove_restart=prove_restart;module.POST_CHECKS=checks
    exec(compile(source,str(Path(__file__)),'exec'),module.__dict__)
    cases=[]
    for is816 in (False,True):
        for fault in (None,'stale','corrupt','reservation-corrupt','reservation-commit'):
            row=module.execute(live.BUILD,folder,banks,is816=is816,deps02=ROOT/'BUILD/v1.30/local/test-deps',
                deps816=ROOT/'BUILD/test-deps-816',fault=fault,verifier=verify_software)
            cases.append(row);print('PASS software-restart native model',row['CPU'],fault or 'success',flush=True)
    assert len(checks)==2 and {x['cpu'] for x in checks}=={'65c02','65c816-e'}
    expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    a,b=live.io.latest(banks),live.io.latest(expected)
    assert live.policy(a)==live.policy(b) and b[18:22]==bytes.fromhex('0f000080')
    assert expected[:3]==banks[:3]
    assert b[160:252]==a[160:252]
    # Bind every plan/capture/qualification artifact that the live phase uses.
    files=[folder/'plan.json',folder/'installer-model-only.s19',native/'model-proof.json',
        live.BUILD/'b15-qualification.json',run/'owner-ram.bin',run/'owner-zp.bin',run/'original-record.bin',
        ROOT/'BUILD/pr04-b14-ram-config-r1/payload/ram-config-offline.bin',live.io.SERVICE/'payload/mon-service-load.bin',
        HERE/'deployment_b15.py',HERE/'deployment_b15_model.py',HERE/'deployment_b07.py',HERE/'deployment_b07_model.py',
        HERE/'native-reserve.asm',ROOT/'tools/installer/engine/install_transport.py',HERE/'board_ram_config_2512.py',
        HERE/'b15-host-tests.json']
    files += [folder/f'transfer-{n:02d}.bin' for n in range(3)]+[folder/f'expected-b{n}.bin' for n in range(4)]
    proof=dict(passed=True,hardware=False,serial_access=False,cases=cases,post_install_checks=checks,
        checks=len(cases)+len(checks),native_original_checks=10,planned_erases=['B3:A','B3:F','B3:B'],C_D_erases=0,
        original_policy_hex=live.policy(a).hex(),target_policy_hex=live.policy(b).hex(),
        helper_sha256=live.io.sha((HERE/'board_b15_2512.py').read_bytes()),
        checker_sha256=live.io.sha(Path(__file__).read_bytes()),adapted_model_sha256=live.io.sha(source.encode()),
        bindings={str(p):live.io.sha(p.read_bytes()) for p in files},
        limits=['Conservative wear and committed journal checked at every modeled NOR mutation',
                'Interrupted F programming can require external recovery; no physical power-cut test'])
    live.io.save(run/'live-model-proof.json',proof)
    print('PASS exact-source b15 installation/restart/cancel/normal-load/RAM-restore models; ready for live admission',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run.resolve())
