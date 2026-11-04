"""Bind offline packing, compatibility, timing and regression evidence."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
    build=p.parse_args().build.resolve();old=ROOT/'BUILD/pr04-b12-no-readback-r4'
    report=read(build/'prototype-report.json');pack=report['b13_packing']
    a=read(old/'symbols.json')['core/str8n-v2-boot'];b=read(build/'symbols.json')['core/str8n-v2-boot']
    x=(old/'payload/f-offline-component.bin').read_bytes();y=(build/'payload/f-offline-component.bin').read_bytes()
    assert report['banner']=='2.0proto b13' and report['experimental_generation']==0x8000000d
    assert report['bootstrap_contract']=='PR04' and not report['deployable'] and not report['board_access']
    for label,address in pack['fixed_F_symbols'].items():assert a[label]==b[label]==address,label
    shared={k:v for k,v in a.items() if k.startswith(('BOOT_API_','BOOT_SR_')) or k in
            ['BOOT_RESET','BOOT_READ_RECORD','BOOT_CHECK_FIELDS','BOOT_SLOT_CHECK','BOOT_READ_LINE',
             'BOOT_PRINT','J_CRC_INIT','J_CRC_BYTE','BOOT_STARTUP','RL_LOAD','RL_GET','RL_ADVANCE',
             'BOOT_WORKER_IMAGE','BOOT_VECTOR_IMAGE']}
    for label,address in shared.items():assert b[label]==address,label
    # Every changed F byte must be in a named padding allocation, validator
    # interval or old startup body. Everything else, including loader, console,
    # root descriptor and hardware vectors, is byte-for-byte unchanged.
    changed={i+0xf000 for i,(u,v) in enumerate(zip(x,y)) if u!=v}
    allowed=set();regions=[]
    for label,size in [('B12_FREE_B12_HELP_TAIL',21),('B12_FREE_TX_ERROR',32),('B12_FREE_LOADED',14),
                       ('BOOT_SLOT_CHECK',a['BOOT_SR_ROUTE']-a['BOOT_SLOT_CHECK']),
                       ('BOOT_STARTUP',a['BOOT_END']-a['BOOT_STARTUP'])]:
        allowed.update(range(a[label],a[label]+size));regions.append(dict(label=label,start=f'{a[label]:04X}',bytes=size))
    assert changed<=allowed,sorted(changed-allowed)
    assert y[0xfe0:]==x[0xfe0:]
    assert b['BOOT_STARTUP']==0xff19 and y[0xf19:0xf1c]==b'\x4c'+b['B13_USB_START'].to_bytes(2,'little')
    assert b['BOOT_END']==0xff1c and y[0xf1c:0xfe0]==b'\xff'*196
    cells=set()
    for label,row in pack['internal_spare_regions'].items():
        start=row['address'];size=row['bytes'];new=set(range(start,start+size))
        assert not cells&new and start==b[label];cells|=new
        byte=0xea if label in ['B12_FREE_DISPATCH','B12_EXISTING_MENU_PAD'] else 0xff
        assert y[start-0xf000:start-0xf000+size]==bytes([byte])*size
    assert len(cells)==44 and not cells&set(range(0xff1c,0xffe0))
    assert 3868+196+32==4096 and 3868-44==3824 and 196+44==240 and 240-189==51
    for mon in report['monitors']:assert (mon['body_bytes'],mon['header_bytes'],mon['free'])==(3830,128,138)
    unchanged={}
    for name in ['ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1']:
        assert (old/'payload'/name).read_bytes()==(build/'payload'/name).read_bytes();unchanged[name]=sha(build/'payload'/name)
    repro=ROOT/'BUILD/pr04-b13-packed-repro'
    reproducible={}
    for path in sorted((build/'payload').glob('*-offline*')):
        if path.suffix not in ['.bin','.rlp1']:continue
        assert path.read_bytes()==(repro/'payload'/path.name).read_bytes(),path.name
        reproducible[path.name]=sha(path)
    for name in ['monitor-a0-offline-component.bin','monitor-b0-offline-component.bin']:
        c=(old/'payload'/name).read_bytes();d=(build/'payload'/name).read_bytes()
        assert [i for i in range(4096) if c[i]!=d[i]]==[8,18,19,2511]
    groups={};receipts=[]
    for name,count in [('b13-selection-tests.json',426),('b13-wait-tests.json',32),('b13-command-tests.json',36),('b13-installer-cpu-tests.json',2)]:
        row=read(build/name);assert row['passed'] and row['checks']==count and row.get('failures',0)==0
        assert row['checker_sha256']==sha(HERE/'test_b13.py')
        if 'F_sha256' in row:assert row['F_sha256']==sha(build/'payload/f-offline-component.bin')
        receipts.append(name);groups[name]=count
    core=read(build/'cpu-tests.json');assert core['passed'] and core['checks']==352 and core['failures']==0
    for name,digest in core['component_hashes'].items():assert sha(build/'payload'/name)==digest
    receipts.append('cpu-tests.json')
    assert read(build/'b13-selection-tests.json')['frozen_b07_checker_adaptation']['adapter_sha256']==sha(HERE/'test_b12_core.py')
    for cpu in ['65c02','65c816-e']:
        name=f'b13-countdown-{cpu}.json';row=read(build/name)
        assert row['passed'] and row['countdown_seconds']==6 and row['F_sha256']==sha(build/'payload/f-offline-component.bin')
        assert row['checker_sha256']==sha(HERE/'test_b13.py');receipts.append(name);groups[name]=1
        name=f'b13-startup-{cpu}.json';row=read(build/name)
        assert row['passed'] and row['checks']==30 and row['failures']==0
        assert row['F_sha256']==sha(build/'payload/f-offline-component.bin')
        assert row['checker_sha256']==sha(HERE/'test_b13_startup.py')
        assert row['cases'][0]['cycles']==15998787
        receipts.append(name);groups[name]=30
    bench=read(build/'bench-target-tests.json');assert bench['passed'] and len(bench['cases'])==4
    receipts.append('bench-target-tests.json');groups['bench-target-tests.json']=4
    manifest=read(build/'bench-target.json');assert manifest['installation_permitted'] is False
    assert manifest['firmware_sha256']==sha(build/'firmware.bin')
    assert not any('readback' in s or 'escrow' in s for s in manifest['enabled_features'])
    receipts+=['prototype-report.json','symbols.json','bench-target.json','firmware.bin','regression.log','commands.log','wait.log',
               'startup-65c02.log','startup-65c816-e.log','startup-65c02-r2.log','startup-65c816-e-r2.log',
               'startup-65c02-r3.log','startup-65c816-e-r3.log']
    result=dict(passed=True,failures=0,hardware=False,serial_access=False,flashed=False,
        identity='2.0proto b13',generation_hex='8000000D',prototype_only=True,previous_build='2.0proto b12',
        F=dict(body_span_bytes=3868,active_code_data_bytes=3824,reserved_hardware_vectors_bytes=32,
            contiguous_free_start_hex='FF1C',contiguous_free_end_hex='FFDF',contiguous_free_bytes=196,
            internal_spare_bytes=44,total_available_bytes=240,additional_contiguous_vs_b12=101,additional_total_vs_b12=51),
        MON=dict(body_bytes_each=3830,header_bytes_each=128,free_bytes_each=138,
            executable_bytes_unchanged_except_banner=True),
        packing=dict(branch_encodings_shortened=21,saved_bytes=63,new_jump_bytes=12,
            startup_entry_retained_hex='FF19',drain_loop_bytes_and_page_crossing_unchanged=True,
            drain_cycles_including_new_exit_jump=8000498,USB_cycles_including_entry_and_phase_jumps=15998787),
        shared_entry_addresses_hex={k:f'{v:04X}' for k,v in shared.items()},unchanged_RAM_tools=unchanged,
        fresh_rebuild_identical_components=reproducible,
        F_changed_bytes=len(changed),allowed_change_regions=regions,
        test_groups=groups,total_test_groups=sum(groups.values()),
        initial_test_harness_failures=dict(first_two_CPU_runs='Incorrect expectation of 480 queued bytes for a 432-byte input fixture',
            second_two_CPU_runs='Frozen startup helper expected the old three-second chooser; adapted assertion to six seconds',
            resolution='Corrected harness only; firmware bytes unchanged; final runs in r3 logs',
            logs=['startup-65c02.log','startup-65c816-e.log','startup-65c02-r2.log','startup-65c816-e-r2.log']),
        receipt_bindings=[dict(file=name,sha256=sha(build/name)) for name in receipts],
        component_hashes={p.name:sha(p) for p in (build/'payload').glob('*-offline*') if p.suffix in ['.bin','.rlp1']},
        source_bindings={p.name:sha(p) for p in sorted(HERE.glob('build*.py'))}|{name:sha(HERE/name) for name in
            ['test_b13.py','test_b13_startup.py','test_b12_core.py','test_b12_commands.py','test_b12_wait.py','test_b12_deployment_cpu.py',
             'test_b08.py','test_b08_countdown.py','test_boot_startup.py','test_boot_countdown.py','bench_b12.py','bench_target.py']},
        checker_sha256=sha(Path(__file__)),limitations=['Offline CPU/register/timing models; no new hardware measurement',
            'Not a deployable update package; all three boards left unchanged',
            '196 contiguous free bytes plus 44 scattered; not all 240 bytes are contiguous',
            'Internal validator/startup labels move; public PR04 and actual shared call entries remain fixed',
            'ACIA electrical/CTS/baud behaviour not measured'])
    assert result['total_test_groups']==562
    (build/'b13-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b13:562 groups; F196 contiguous +44 scattered =240; all shared entry addresses retained',flush=True)

if __name__=='__main__':main()
