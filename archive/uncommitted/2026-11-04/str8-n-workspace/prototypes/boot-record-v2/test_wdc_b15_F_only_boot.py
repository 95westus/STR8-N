"""F-up tests: a directly flashed 4096-byte BIN or factory-WDC RAM migration.

Neither route installs MON, C/D records, language images or providers.
"""
import argparse
from pathlib import Path
from test_wdc_b15_2609 import Model
import wdc_b15_2609 as planning
from installer.common import save
from test_b14_core import load_core
from test_b14_raw import start,feed
CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
REC=b'REC> '

def boot(build,banks,ram,key=None):
    core,_=load_core();core.GENERATION=planning.GENERATION
    h=core.Machine(build,'65c816-e',opaque=True)
    h.m.banks[:]=[bytearray(b) for b in banks];h.m.ram[:]=ram;h.m.bank=3
    h.m.tx.clear();h.m.acia_tx.clear();h.m.acia_writes.clear();h.m.rx.clear();h.m.acia_rx.clear()
    h.c.pc=0xf004;h.c.dpr=h.c.dbr=h.c.pbr=0;h.c.mode=1;h.c.p=0x34;h.c.sp=255
    h.run(lambda:bytes(h.m.tx).endswith(CHOICES))
    if key is not None:h.m.rx.append(ord(key))
    h.run(lambda:bytes(h.m.tx).endswith(REC))
    assert not h.m.events and tuple(map(bytes,h.m.banks))==tuple(map(bytes,banks))
    assert bytes(h.m.ram[0x7e60:0x7e64])==b'RA\x01\x0d'
    return h

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    model=Model(args.plan);normal=model.execute();checks=[]
    def passed(case,**kw):
        checks.append(dict(passed=True,case=case,**kw));save(out/'progress.json',checks)
        print('PASS',len(checks),case,flush=True)
    image=(args.plan/'b15-F-4096.bin').read_bytes();assert len(image)==4096
    direct=list(map(bytearray,model.source));direct[3][-4096:]=image
    assert list(map(bytes,direct))==model.expected
    passed('direct-4096-byte-F-overlay-equals-RAM-migrator-postimage',changed_sectors=['B3:F'])
    bare=[bytearray(b'\xff'*32768) for _ in range(4)];bare[0][:]=model.source[0];bare[3][-4096:]=image
    routes=[('direct-F-on-blank-nonF',list(map(bytes,bare))),('factory-WDC-RAM-migration',model.expected)]
    ram=model.memory.ram
    for route,banks in routes:
        for key in (None,'S','A','B','0','1','2','3'):
            h=boot(planning.TARGET,banks,ram,key)
            assert bytes(h.m.tx).endswith(REC) and h.m.bank==3 and h.c.mode==1
            assert bytes(h.m.ram[0x200:0x6500])==bytes(ram[0x200:0x6500])
            passed(route+'-reset-'+('default' if key is None else key),read_only_flash=True,application_RAM_preserved=True)
        h=boot(planning.TARGET,banks,ram);h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
        before=bytes(h.m.ram[0x200:0x6500]);start(h,1);h.m.rx.append(3);h.run(lambda:bytes(h.m.tx).endswith(REC))
        assert bytes(h.m.ram[0x200:0x6500])==before and not h.m.events
        passed(route+'-Ctrl-C-before-first-byte-preserves-RAM')
        h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE']);start(h,1)
        # HOLD resumes the active MON and is not an F-only return contract.
        # The public RAM RESET entry selects B3 and restarts F independently.
        app=bytes.fromhex('a940206d7e4c647e') # print @ through RAM console; RESET
        feed(h,1,app);h.run(lambda:h.c.pc==0x200);h.run(lambda:bytes(h.m.tx).endswith(REC))
        assert b'@' in h.m.tx and bytes(h.m.ram[0x200:0x208])==app and not h.m.events
        assert bytes(h.m.ram[0x208:0x6500])==before[8:]
        passed(route+'-raw-RAM-app-load-autorun-and-RESET',RAM_payload_bytes=len(app),no_flash_write=True)
    prefix_rows=[]
    for point in model.checkpoints:
        partial=point['banks']
        assert partial[:3]==model.source[:3] and partial[3][:-4096]==model.source[3][:-4096]
        retry=Model(args.plan,fault='stale-3');retry.memory.banks=list(map(bytearray,partial))
        retry.execute();assert not retry.memory.events
        classification='incomplete F; host/B0 recovery may be required'
        if partial[3][-4096:]==image:
            boot(planning.TARGET,partial,ram);classification='complete F resets to recovery'
        prefix_rows.append(dict(case=point['case'],original_plan_refused_before_write=True,every_nonF_byte_unchanged=True,classification=classification))
        print('PASS interrupted-state',point['case'],flush=True)
    passed('interrupted-F-original-plan-replay-refused',states=len(prefix_rows),checks=prefix_rows,all_mutation_prefixes=model.prefixes,every_nonF_byte_preserved=True)
    save(out/'boot-proof.json',dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,
        cases=checks,checks=len(checks),source_transaction_model=normal,
        plan_sha256=planning.digest(args.plan/'plan.json'),installer_sha256=planning.digest(args.plan/'installer-model-only.s19'),
        F_sha256=planning.digest(args.plan/'b15-F-4096.bin'),F_bytes=4096,
        test_source_sha256=planning.digest(__file__),model_source_sha256=planning.digest(Path(__file__).with_name('test_wdc_b15_2609.py')),
        limits='Direct-programmer overlay and CPU/NOR simulation only; no board flashed, electrical power cut or NMI test'))
    print('PASS',len(checks),'F-only boot/raw-loader/interruption groups; no hardware access',flush=True)

if __name__=='__main__':main()
