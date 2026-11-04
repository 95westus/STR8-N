"""Bind b10's measured/CPU results and exact unchanged b09 runtime regions."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(path):return json.loads(Path(path).read_bytes())
def sha(data):return hashlib.sha256(data).hexdigest()


def static_equivalence(build):
    build=Path(build);prior=ROOT/'BUILD/pr04-b09-usb2'
    old_sy=read(prior/'symbols.json');new_sy=read(build/'symbols.json')
    exceptions={'BOOT_END','_END_CODE','RL_GOT','P_LONG_63','P_LONG_64','P_LONG_65'}
    for module,labels in old_sy.items():
        assert all(new_sy[module].get(k)==v for k,v in labels.items() if k not in exceptions),module
    old=(prior/'payload/f-offline-component.bin').read_bytes();new=(build/'payload/f-offline-component.bin').read_bytes()
    sy=old_sy['core/str8n-v2-boot']
    allowed=set(range(sy['RL_GET']-0xf000,sy['RL_ADVANCE']-0xf000))
    allowed.update(range(sy['RL_HEADER_BYTE']-0xf000+1,sy['RL_HEADER_BYTE']-0xf000+3))
    allowed.update(range(sy['BOOT_END']-0xf000,sy['BOOT_END']-0xf000+16))
    changes=[n for n,(a,b) in enumerate(zip(old,new)) if a!=b]
    assert set(changes)<=allowed and len(old)==len(new)==4096
    assert old[0xfe0:]==new[0xfe0:]
    monitor_changes={}
    for name in ('monitor-a0-offline-component.bin','monitor-b0-offline-component.bin'):
        a=(prior/'payload'/name).read_bytes();b=(build/'payload'/name).read_bytes()
        differences=[n for n,(x,y) in enumerate(zip(a,b)) if x!=y]
        assert differences==[8,18,19,2510,2511] and a[2510:2512]==b'09' and b[2510:2512]==b'10'
        monitor_changes[name]=differences
    unchanged={}
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        body=(build/'payload'/name).read_bytes();assert body==(prior/'payload'/name).read_bytes();unchanged[name]=sha(body)
    info=read(build/'prototype-report.json')
    for label,size in (('BOOT_WORKER_IMAGE',info['f']['worker_bytes']),('BOOT_VECTOR_IMAGE',info['f']['vectors_bytes'])):
        start=sy[label]-0xf000;assert old[start:start+size]==new[start:start+size];unchanged[label]=sha(new[start:start+size])
    assert old[sy['BOOT_STARTUP']-0xf000:sy['BOOT_END']-0xf000]==new[sy['BOOT_STARTUP']-0xf000:sy['BOOT_END']-0xf000]
    assert old[:sy['RL_LOAD']-0xf000]==new[:sy['RL_LOAD']-0xf000]
    return dict(passed=True,F_changed_offsets=changes,MON_identity_only_changes=monitor_changes,
        public_ABI_and_external_private_entries_unchanged=True,unchanged_runtime_sha256=unchanged,
        startup_wait_drain_countdown_byte_identical_to_qualified_b09=True,
        hardware_vector_reservation_unchanged=True,source_F_sha256=sha(old),F_sha256=sha(new))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    build=p.parse_args().build.resolve();equivalence=static_equivalence(build)
    core=read(build/'b10-selection-tests.json');wait=read(build/'b10-wait-tests.json')
    assert core['passed'] and core['checks']==426 and not core['failures']
    assert wait['passed'] and wait['checks']==32 and not wait['failures']
    assert wait['checker_sha256']==sha((HERE/'test_b10_wait.py').read_bytes())
    bench=read(build/'bench-target-tests.json');assert bench['passed'] and len(bench['cases'])==4
    names=['b10-selection-tests.json','b10-wait-tests.json','cpu-tests.json','bench-target-tests.json',
           'bench-target.json','prototype-report.json','firmware.bin']
    for cpu in ('65c02','65c816-e'):
        name=f'b10-usb-wait-{cpu}.json';timing=read(build/name)
        assert timing['passed'] and timing['cycles']==15998781 and not timing['hardware']
        assert timing['F_sha256']==equivalence['F_sha256'];names.append(name)
    result=dict(passed=True,hardware=False,flashed=False,failures=0,identity='2.0proto b10',generation_hex='8000000A',
        regression_and_selection_groups=426,first_byte_receive_groups=32,
        static_equivalence=equivalence,receipt_bindings=[dict(file=name,sha256=sha((build/name).read_bytes())) for name in names],
        checker_sha256=sha(Path(__file__).read_bytes()))
    (build/'b10-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b10 qualification:426 regression +32 receive +2 USB timing +4 bench; zero failures',flush=True)


if __name__=='__main__':main()
