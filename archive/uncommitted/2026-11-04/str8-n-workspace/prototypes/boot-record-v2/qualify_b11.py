"""Bind exact b11 bytes, changed regions and all offline qualification receipts."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()

def static_equivalence(build):
    build=Path(build);prior=ROOT/'BUILD/pr04-b10-wait'
    a=read(prior/'symbols.json');b=read(build/'symbols.json');old=a['core/str8n-v2-boot'];new=b['core/str8n-v2-boot']
    intervals=[(old[x],old[y]) for x,y in [('BOOT_MENU','RL_GET'),('BOOT_READ_RECORD','BOOT_CHECK_FIELDS'),('BOOT_CHECK_FIELDS','BOOT_META_READ')]]
    # Every external/shared entry remains fixed, including BOOT_CHECK_FIELDS,
    # whose address is linked into MON's and standalone CONFIG's journal writer.
    for module,labels in a.items():
        for label,address in labels.items():
            if module=='core/str8n-v2-boot' and any(lo<address<hi for lo,hi in intervals):continue
            assert b[module].get(label)==address,(module,label)
    x=(prior/'payload/f-offline-component.bin').read_bytes();y=(build/'payload/f-offline-component.bin').read_bytes()
    allowed={n-0xf000 for lo,hi in intervals for n in range(lo,hi)}
    # R/V absent-image jump target; R lies in the first compacted region.
    allowed.update(range(old['RL_VERIFY']-0xf000+6,old['RL_VERIFY']-0xf000+8))
    # Three existing output-error tail calls follow the compacted handler.
    for label in ('P_LONG_70','P_LONG_72','P_LONG_73'):
        offset=old[label]-0xf000-3
        assert x[offset:offset+3]==b'\x4c'+old['DC_BINARY_TX_BAD'].to_bytes(2,'little')
        assert y[offset:offset+3]==b'\x4c'+new['DC_BINARY_TX_BAD'].to_bytes(2,'little')
        allowed.update((offset+1,offset+2))
    differences=[n for n in range(4096) if x[n]!=y[n]]
    assert set(differences)<=allowed,(set(differences)-allowed)
    assert x[0xfe0:]==y[0xfe0:]
    assert x[old['BOOT_STARTUP']-0xf000:]==y[old['BOOT_STARTUP']-0xf000:]
    unchanged={}
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        body=(build/'payload'/name).read_bytes();assert body==(prior/'payload'/name).read_bytes();unchanged[name]=sha(body)
    info=read(build/'prototype-report.json')
    for label,size in [('BOOT_WORKER_IMAGE',info['f']['worker_bytes']),('BOOT_VECTOR_IMAGE',info['f']['vectors_bytes'])]:
        offset=old[label]-0xf000;assert x[offset:offset+size]==y[offset:offset+size];unchanged[label]=sha(y[offset:offset+size])
    mons={}
    for name in ('monitor-a0-offline-component.bin','monitor-b0-offline-component.bin'):
        c=(prior/'payload'/name).read_bytes();d=(build/'payload'/name).read_bytes()
        diff=[n for n in range(4096) if c[n]!=d[n]]
        assert diff==[8,18,19,2511] and c[2510:2512]==b'10' and d[2510:2512]==b'11'
        mons[name]=diff
    return dict(passed=True,F_changed_offsets=differences,MON_identity_only_changes=mons,
        public_ABI_and_external_private_entries_unchanged=True,unchanged_runtime_sha256=unchanged,
        startup_wait_drain_countdown_byte_identical_to_qualified_b10=True,
        hardware_vector_reservation_unchanged=True,source_F_sha256=sha(x),F_sha256=sha(y))

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    equivalence=static_equivalence(build)
    names=['b11-selection-tests.json','b11-wait-tests.json','b11-help-tests.json','cpu-tests.json','bench-target-tests.json','bench-target.json','prototype-report.json','firmware.bin']
    for name,count in [('b11-selection-tests.json',426),('b11-wait-tests.json',32),('b11-help-tests.json',24),('cpu-tests.json',352)]:
        row=read(build/name);assert row['passed'] and row['checks']==count and not row['failures']
    assert len(read(build/'bench-target-tests.json')['cases'])==4
    for cpu in ('65c02','65c816-e'):
        name=f'b11-usb-wait-{cpu}.json';row=read(build/name)
        assert row['passed'] and row['cycles']==15998781 and row['F_sha256']==equivalence['F_sha256'];names.append(name)
    result=dict(passed=True,hardware=False,flashed=False,failures=0,identity='2.0proto b11',generation_hex='8000000B',
        regression_and_selection_groups=426,first_byte_receive_groups=32,recovery_help_raw_diagnostic_groups=24,
        static_equivalence=equivalence,receipt_bindings=[dict(file=name,sha256=sha((build/name).read_bytes())) for name in names],checker_sha256=sha(Path(__file__).read_bytes()))
    (build/'b11-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b11:426 regression/selection +32 receive +24 help/raw/diagnostics +2 USB timing +4 bench; zero failures',flush=True)

if __name__=='__main__':main()
