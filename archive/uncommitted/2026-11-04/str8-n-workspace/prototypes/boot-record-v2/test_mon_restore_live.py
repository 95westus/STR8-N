"""Exact-current-source F-only MON restoration and software-boot models."""
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_mon_absent as f
t=f.t;ROOT=HERE.parents[1];BUILD=ROOT/'BUILD/pr04-b14-mon-absent-r5'
SOURCE=ROOT/'output/qualification/opaque-absent-2512-install-run-restore-r2'
CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n';MON=b'\r\nB3> '

def restart_recovery(h):
    start=len(h.m.tx);h.m.rx.extend(b'J3\r\n')
    h.run(lambda:len(h.m.tx)>start and bytes(h.m.tx).endswith(CHOICES),limit=12000000)
    h.m.rx.append(ord('S'));h.run(lambda:bytes(h.m.tx).endswith(b'REC> '))
    assert b'Recovery L A/B 0-3 C1/2/3 ?' in h.m.tx[start:]

def main(out):
    assert not out.exists(),'Fresh output required';out.mkdir(parents=True)
    source=[(SOURCE/f'restored-independent-flash-r2-b{n}.bin').read_bytes() for n in range(4)]
    original=(ROOT/'tmp/pr04-b14-2512-native-plan/expected-b3.bin').read_bytes()
    assert source[3][0x2000:0x4000]==b'\xff'*8192
    cases=[]
    def passed(cpu,label,**kw):cases.append(dict(cpu=cpu,case=label,passed=True,**kw));print('PASS',cpu,label,flush=True)
    for cpu in ('65c02','65c816-e'):
        h=f.fresh(BUILD,cpu,source);f.load(h,BUILD,'mon-kit.bin',f.KIT)
        start=len(h.m.tx);h.m.rx.extend(b'T')
        h.run(lambda:len(h.m.tx)>start and bytes(h.m.tx).endswith(MON),limit=12000000)
        boot=bytes(h.m.tx[start:]);assert b'MON KIT DONE' in boot and b'STR8-N 2.0proto b14 B3' in boot and h.m.ram[0x7d30]==0xb0
        assert bytes(h.m.banks[3][0x2000:0x4000])==original[0x2000:0x4000]
        f.preserved(source,h.m.banks)
        old,new=t.latest_record(source),t.latest_record(h.m.banks)
        for bank in range(4):
            for sector in range(0x80,0x100,0x10):
                assert t.counter(new,bank,sector)==t.counter(old,bank,sector)+int(bank==3 and sector in (0xa0,0xb0))
        assert [e[2] for e in h.m.events if e[0]=='erase']==[0xa000,0xb000]
        for sector in (0xa000,0xb000):
            events=[e for e in h.m.events if e[2]&0xf000==sector]
            assert events[0][0]=='erase' and events[-1][0]=='program' and events[-1][2]==sector+31 and events[-1][3]==0
        expected=list(map(bytes,h.m.banks))
        for n,data in enumerate(expected):
            path=out/f'expected-b{n}.bin'
            if cpu=='65c02':path.write_bytes(data)
            else:assert path.read_bytes()==data,'CPU postimages disagree'
        passed(cpu,'F-raw-kit-restores-original-AB-commit-last-wear-before-erase-boot-B',mutations=len(h.m.events))
        restart_recovery(h)
        reply=h.command(b'A\r',MON);assert b'2.0proto b14' in reply and h.m.ram[0x7d30]==0xa0
        restart_recovery(h)
        reply=h.command(b'B\r',MON);assert b'2.0proto b14' in reply and h.m.ram[0x7d30]==0xb0
        assert list(map(bytes,h.m.banks))==expected
        passed(cpu,'both-MON-selections-and-J3-S-without-reset-or-flash-writes')
        restart_recovery(h);f.load(h,BUILD,'mon-kit.bin',f.KIT);before=len(h.m.events)
        start=len(h.m.tx);h.m.rx.extend(b'T');h.run(lambda:len(h.m.tx)>start and bytes(h.m.tx).endswith(MON),limit=12000000)
        assert len(h.m.events)==before and list(map(bytes,h.m.banks))==expected
        passed(cpu,'identical-restore-retry-has-no-erase-or-wear-reservation')
    report=dict(passed=True,hardware=False,serial_access=False,checks=len(cases),failures=0,cases=cases,
        checker_sha256=t.sha(Path(__file__).read_bytes()),source_run=str(SOURCE),source_bank_sha256=list(map(t.sha,source)),
        source_completion_sha256=t.sha((SOURCE/'state.json').read_bytes()),
        restore_kit_sha256=t.sha((BUILD/'payload/mon-kit.bin').read_bytes()),
        retained_kit_proof_sha256=t.sha((BUILD/'mon-absent-tests.json').read_bytes()),
        expected_bank_sha256=[t.sha((out/f'expected-b{n}.bin').read_bytes()) for n in range(4)],
        target_MON_sha256=[t.sha(original[off:off+4096]) for off in (0x2000,0x3000)],
        firmware_identity='2.0proto b14',generation_hex='8000000E',F_unchanged=True,
        limitations=['Existing kit has selected interrupted-write prefix coverage; no physical power-cut test added'])
    t.base.save(out/'mon-restore-model-tests.json',report)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
