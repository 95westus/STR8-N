"""Audit b15 first-byte cancellation, fixed services and reproducible payloads."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def qualify(build,repro):
    old=ROOT/'BUILD/pr04-b14-raw-r4'
    info=read(build/'prototype-report.json');raw=info['raw_loader']
    assert info['banner']=='2.0proto b15' and info['experimental_generation']==0x8000000f
    assert not info['deployable'] and not info['board_access'] and not info['hardware_qualified']
    assert raw['first_byte_cancel'] and not raw['CRC'] and raw['idle_seconds']==3
    assert (raw['load_start'],raw['entry'],raw['max_bytes'])==(0x200,0x200,25344)
    a=read(old/'symbols.json')['core/str8n-v2-boot'];b=read(build/'symbols.json')['core/str8n-v2-boot']
    before=(old/'payload/f-offline-component.bin').read_bytes();after=(build/'payload/f-offline-component.bin').read_bytes()
    entries={k:v for k,v in a.items() if k.startswith(('BOOT_API_','BOOT_SR_')) or k in
             ('BOOT_RESET','BOOT_READ_RECORD','BOOT_CHECK_FIELDS','BOOT_SLOT_CHECK','BOOT_READ_LINE',
              'BOOT_PRINT','J_CRC_INIT','J_CRC_BYTE','BOOT_CON_SELECT','BOOT_WORKER_IMAGE','BOOT_VECTOR_IMAGE')}
    assert all(b[k]==v for k,v in entries.items())
    assert after[-32:]==before[-32:]
    for first,length in (('BOOT_WORKER_IMAGE',1000),('BOOT_VECTOR_IMAGE',196)):
        offset=b[first]-0xf000
        assert after[offset:offset+length]==before[offset:offset+length]
    for first,last in (('RL_LOAD_BYTE','B14_MAIN_END'),('BR_COUNTDOWN','BR_DEFAULT'),('BOOT_DRAIN_BEGIN','B13_FREE_SLOT')):
        assert after[b[first]-0xf000:b[last]-0xf000]==before[a[first]-0xf000:a[last]-0xf000]
    assert after[b['B14_FIRST_GOT']-0xf000:b['B14_FIRST_GOT']-0xf000+3]==bytes.fromhex('C903F0')
    assert b['BOOT_END']==0xfe55 and after[0xe55:0xfe0]==b'\xff'*395
    holes=set()
    for label,row in raw['internal_spare_regions'].items():
        address,n=row['address'],row['bytes'];cells=set(range(address,address+n))
        assert not holes&cells;holes|=cells
        fill=0xea if label=='B14_FREE_DISPATCH' else 0 if label in ('B14_FREE_MAIN','B14_FREE_INIT') else 0xff
        assert after[address-0xf000:address-0xf000+n]==bytes([fill])*n
    assert len(holes)==81 and raw['total_spare_bytes']==476
    payloads={}
    for path in (build/'payload').glob('*.bin'):
        assert path.read_bytes()==(repro/'payload'/path.name).read_bytes(),path.name
        payloads[path.name]=sha(path)
    for name in ('ram-config-offline.bin','ram-installer-offline.bin'):
        assert (build/'payload'/name).read_bytes()==(old/'payload'/name).read_bytes()
    # The candidate changes only first-byte dispatch, its cancel gap and help.
    allowed=set()
    for lo,hi in ((a['B14_INIT_BASE'],a['B14_INIT_BASE']+99),(a['B14_FREE_FIRST'],a['B14_FREE_FIRST']+17),
                  (a['B12_HELP_TEXT'],a['BOOT_CHECK_FIELDS']),(a['B12_HELP_TAIL'],a['B13_USB_START'])):
        allowed.update(range(lo-0xf000,hi-0xf000))
    assert all(i in allowed for i,(x,y) in enumerate(zip(before,after)) if x!=y)
    receipts={};groups={}
    for name,checker in (('b15-raw.json','test_b15_raw.py'),('b15-cancel.json','test_b15_raw.py'),
                         ('b15-selection-tests.json','test_b15.py'),('b15-startup-65c02.json','test_b15_startup.py'),
                         ('b15-startup-65c816-e.json','test_b15_startup.py')):
        r=read(build/name);assert r['passed'] and r['failures']==0 and not r['hardware'] and not r['serial_access']
        assert r['checker_sha256']==sha(HERE/checker)
        if 'F_sha256' in r:assert r['F_sha256']==sha(build/'payload/f-offline-component.bin')
        if 'prototype_report_sha256' in r:assert r['prototype_report_sha256']==sha(build/'prototype-report.json')
        groups[name]=r['checks'];receipts[name]=sha(build/name)
    assert groups['b15-raw.json']==62 and groups['b15-cancel.json']==40 and groups['b15-selection-tests.json']==350
    assert groups['b15-startup-65c02.json']==groups['b15-startup-65c816-e.json']==30
    result=dict(passed=True,hardware=False,serial_access=False,flashed=False,failures=0,
        identity='2.0proto b15',generation_hex='8000000F',checks=sum(groups.values()),groups=groups,
        first_input_Ctrl_C_cancels=True,payload_Ctrl_C_is_literal=True,first_byte_wait_indefinite=True,
        unverified_raw_transfer=True,shared_services_unchanged=True,receive_idle_loop_byte_identical_to_b14=True,
        F=dict(body_span_bytes=3669,active_code_data_bytes=3669-len(holes),contiguous_free_bytes=395,
               internal_spare_bytes=len(holes),total_available_bytes=476),
        reproducible_payload_sha256=payloads,receipts=receipts,
        source_sha256={p.name:sha(p) for p in (HERE/'build_b15.py',HERE/'test_b15_raw.py',HERE/'test_b15.py',
            HERE/'test_b15_startup.py',HERE/'test_b14_raw.py',HERE/'test_b14_core.py',Path(__file__))},
        inherited_idle_timing=dict(source=str(old/'b14-qualification.json'),sha256=sha(old/'b14-qualification.json'),
            reason='Complete receive/idle machine code, worker, budgets and shared service locations are identical'),
        limitations=['Offline candidate only; 2512 still runs unchanged b14',
            'A BIN beginning with 03 now cancels instead of loading',
            'After the first payload byte all values are literal; no mid-transfer cancel',
            'No CRC or length verification added; three seconds idle can run a truncated prefix',
            'Exact-F-CRC-bound b14 kits must be rebuilt and qualified before use with b15'])
    (build/'b15-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_sha256','receipts','reproducible_payload_sha256')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--repro',type=Path,required=True)
    x=p.parse_args();qualify(x.build.resolve(),x.repro.resolve())
