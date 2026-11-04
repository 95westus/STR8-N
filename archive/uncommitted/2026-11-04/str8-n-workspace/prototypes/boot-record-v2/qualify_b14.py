"""Offline b14 size, ABI, raw-loader and relocated-tool qualification receipt."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--layout-only',action='store_true')
    args=p.parse_args();build=args.build.resolve()
    old=ROOT/'BUILD/pr04-b13-packed-r1';repro=ROOT/'BUILD/pr04-b14-raw-repro'
    r=read(build/'prototype-report.json');raw=r['raw_loader']
    a=read(old/'symbols.json')['core/str8n-v2-boot'];s=read(build/'symbols.json')['core/str8n-v2-boot']
    x=(old/'payload/f-offline-component.bin').read_bytes();y=(build/'payload/f-offline-component.bin').read_bytes()
    assert r['banner']=='2.0proto b14' and r['experimental_generation']==0x8000000e and r['bootstrap_contract']=='PR04'
    assert not r['deployable'] and not r['board_access'] and not r['hardware_qualified']
    assert (raw['load_start'],raw['entry'],raw['end_exclusive'],raw['max_bytes'])==(0x200,0x200,0x6500,25344)
    assert not raw['CRC'] and not raw['length_field'] and not raw['run_command'] and raw['header_bytes']==0
    assert raw['idle_seconds']==3 and raw['empty_polls']==dict(FT245=214256,ACIA=203363)
    for k in ['RL_RUN','RL_HEADER','RL_SIGNATURE','RL_LENGTH','RL_VALID','RL_GET','RL_ADVANCE']:assert k not in s,k
    assert b'RLP1' not in y and b'SEND HEADER' not in y and b'LOADED; R' not in y
    # CRC is deliberately retained for MON slots, boot records and OIP1 flash
    # safety. Neither raw receive block may call it or parse a transfer frame.
    asm=(build/'s/core/str8n-v2-boot.asm').read_text()
    for first,last in [('RL_LOAD_BYTE:','B14_MAIN_END:'),('RL_LOAD:','B14_INIT_END:')]:
        block=asm[asm.index(first):asm.index(last)]
        assert 'J_CRC' not in block and 'HEADER' not in block and 'RL_LENGTH' not in block
    entries={k:v for k,v in a.items() if k.startswith(('BOOT_API_','BOOT_SR_')) or k in
             ['BOOT_RESET','BOOT_READ_RECORD','BOOT_CHECK_FIELDS','BOOT_SLOT_CHECK','BOOT_READ_LINE',
              'BOOT_PRINT','J_CRC_INIT','J_CRC_BYTE','BOOT_CON_SELECT']}
    for name,value in entries.items():assert s[name]==value,name
    assert y[-32:]==x[-32:]
    assert y[s['BOOT_VECTOR_IMAGE']-0xf000:s['BOOT_VECTOR_IMAGE']-0xf000+196]==x[a['BOOT_VECTOR_IMAGE']-0xf000:a['BOOT_VECTOR_IMAGE']-0xf000+196]
    assert y[s['BOOT_WORKER_IMAGE']-0xf000:s['BOOT_WORKER_IMAGE']-0xf000+1000]==x[a['BOOT_WORKER_IMAGE']-0xf000:a['BOOT_WORKER_IMAGE']-0xf000+1000]
    for first,last in [('BR_COUNTDOWN','BR_DEFAULT'),('BOOT_DRAIN_BEGIN','B13_FREE_SLOT')]:
        assert y[s[first]-0xf000:s[last]-0xf000]==x[a[first]-0xf000:a[last]-0xf000]
    assert s['BOOT_END']==0xfe55 and y[0xe55:0xfe0]==b'\xff'*395
    cells=set()
    for label,row in raw['internal_spare_regions'].items():
        address=row['address'];size=row['bytes'];add=set(range(address,address+size));assert not cells&add;cells|=add
        # WDC emits DS reservations as zero-filled cells; explicit DB gaps
        # retain FF (or executable dispatch NOPs). All are reusable next build.
        expected=0xea if label=='B14_FREE_DISPATCH' else 0 if label in ['B14_FREE_MAIN','B14_FREE_INIT'] else 0xff
        assert y[address-0xf000:address-0xf000+size]==bytes([expected])*size,(label,address,size)
    assert len(cells)==97 and 3669+395+32==4096 and 3669-97==3572 and 395+97==492
    assert not cells&set(range(0xfe55,0x10000))
    for mon in r['monitors']:assert (mon['body_bytes'],mon['header_bytes'],mon['free'],mon['writer_bytes'])==(3830,128,138,983)
    for name in ['monitor-a0-offline-component.bin','monitor-b0-offline-component.bin']:
        c=(old/'payload'/name).read_bytes();d=(build/'payload'/name).read_bytes()
        assert [i for i in range(4096) if c[i]!=d[i]]==[8,18,19,2511],name
    assert r['config']['start']==r['installer']['start']==r['installer']['entry']==0x200
    assert r['config']['bytes']==1176 and r['installer']['bytes']==2412
    assert not list((build/'payload').glob('*.rlp1'))
    same={}
    for path in sorted((build/'payload').glob('*-offline*')):
        if path.suffix!='.bin':continue
        assert path.read_bytes()==(repro/'payload'/path.name).read_bytes(),path.name;same[path.name]=sha(path)
    if args.layout_only:
        print('PASS b14 layout/ABI/reproducibility: body3669, active3572, tail395, internal97, total492',flush=True)
        return
    groups={};receipts=[]
    for name,count,checker in [('b14-selection-tests.json',350,'test_b14.py'),('b14-raw.json',66,'test_b14_raw.py'),
                               ('b14-config-execution.json',14,'test_b14_config.py')]:
        row=read(build/name);assert row['passed'] and row['checks']==count and row['failures']==0,(name,row.get('checks'))
        assert row['checker_sha256']==sha(HERE/checker)
        if 'F_sha256' in row:assert row['F_sha256']==sha(build/'payload/f-offline-component.bin')
        groups[name]=count;receipts.append(name)
    core=read(build/'cpu-tests.json');assert core['checks']==276 and core['passed'] and core['failures']==0
    for name,digest in core['component_hashes'].items():assert sha(build/'payload'/name)==digest
    selection=read(build/'b14-selection-tests.json')
    assert selection['frozen_b07_checker_adaptation']['adapter_sha256']==sha(HERE/'test_b14_core.py')
    assert selection['prototype_report_sha256']==sha(build/'prototype-report.json')
    receipts.append('cpu-tests.json')
    for cpu in ['65c02','65c816-e']:
        for name,count,checker in [(f'b14-raw-timing-{cpu}.json',2,'test_b14_raw.py'),
                                   (f'b14-startup-{cpu}.json',30,'test_b14_startup.py'),
                                   (f'b14-opaque-installer-cpu-tests-{cpu}.json',60,'test_b14_tools.py')]:
            row=read(build/name);assert row['passed'] and row['checks']==count and row.get('failures',0)==0,(name,row.get('checks'))
            digest=row.get('checker_sha256',row.get('test_source_sha256'));assert digest==sha(HERE/checker),name
            if 'F_sha256' in row:assert row['F_sha256']==sha(build/'payload/f-offline-component.bin')
            if 'component_hashes' in row:
                for file,digest in row['component_hashes'].items():assert sha(build/'payload'/file)==digest
                assert row['prototype_report_sha256']==sha(build/'prototype-report.json')
            groups[name]=count;receipts.append(name)
        timer=read(build/f'b14-raw-timing-{cpu}.json')
        assert [c['cycles_until_run'] for c in timer['cases']]==[24000097,24000091]
        assert all(not c['accelerated_instructions'] for c in timer['cases'])
    bench=read(build/'bench-target-tests.json');assert bench['passed'] and len(bench['cases'])==4
    receipts.append('bench-target-tests.json');groups['bench-target-tests.json']=4
    manifest=read(build/'bench-target.json');assert not manifest['installation_permitted'] and manifest['firmware_sha256']==sha(build/'firmware.bin')
    assert sum(groups.values())==618,groups
    receipts+=['prototype-report.json','symbols.json','bench-target.json','firmware.bin','config.log','config-r2.log','config-r3.log','regression-r2.log','regression-r3.log']
    result=dict(passed=True,failures=0,hardware=False,serial_access=False,flashed=False,identity='2.0proto b14',generation_hex='8000000E',
        raw_load=dict(start_hex='0200',entry_hex='0200',last_writable_hex='64FF',max_bytes=25344,
            header=False,length=False,CRC=False,R_command=False,idle_seconds=3,first_byte_wait='indefinite',
            all_byte_values_are_data=True,first_data_port_owns_transfer=True,
            detected_error_or_overflow='Refuse without execution',raw_transfer_is_not_verified=True),
        F=dict(body_span_bytes=3669,active_code_data_bytes=3572,reserved_vectors_bytes=32,
            contiguous_free_start_hex='FE55',contiguous_free_end_hex='FFDF',contiguous_free_bytes=395,
            internal_spare_bytes=97,total_available_bytes=492,additional_available_vs_b13=252,
            additional_contiguous_vs_b13=199),
        MON=dict(body_bytes_each=3830,header_bytes_each=128,free_bytes_each=138,journal_writer_bytes_each=983),
        CONFIG=dict(entry_hex='0200',bytes=1176,journal_writer_bytes=983),
        opaque_installer=dict(entry_hex='0200',bytes=2412,raw_load_with_MON_absent=True,OIP1_flash_safeguards_retained=True,
            interrupted_write_prefixes=sum(read(build/f'b14-opaque-installer-cpu-tests-{cpu}.json')['mutation_prefixes'] for cpu in ['65c02','65c816-e'])),
        shared_entry_addresses_hex={k:f'{v:04X}' for k,v in entries.items()},
        private_ROM_data_and_startup_relocated=True,boot_countdown_and_drain_loop_bytes_identical_to_b13=True,
        total_test_groups=sum(groups.values()),test_groups=groups,
        unaccelerated_idle_to_entry_cycles=dict(FT245=24000097,ACIA=24000091),nominal_CPU_Hz=8_000_000,
        exact_fast_idle_model_checked_against_full_linked_CPU_and_RAM_state=True,
        reproducible_component_hashes=same,
        receipt_bindings=[dict(file=name,sha256=sha(build/name)) for name in receipts],
        source_bindings={p.name:sha(p) for p in sorted(HERE.glob('build*.py'))}|{name:sha(HERE/name) for name in
            ['raw-loader-b14.inc','raw-start-b14.inc','installer_build_b14.py','test_b14.py','test_b14_core.py','test_b14_raw.py',
             'test_b14_config.py','test_b14_tools.py','test_b14_startup.py','test_opaque_installer.py','test_b13_startup.py','calibrate_b14.py']},
        prior_harness_issues=['WDC EQU scope/indentation corrected during initial build attempts',
            'CONFIG blank journal correctly refused disabled bank 0; test now checks refusal and valid S',
            'Fast-idle test hook guarded for old parser-reference builds without b14 symbols',
            'Layout checker corrected to expect WDC zero-fill for DS reservations; firmware unchanged'],
        limitations=['Offline only; no hardware or electrical timing measurements; all three boards unchanged',
            'Three-second transfer pause runs the received prefix; corruption/truncation cannot be detected',
            'Every byte, including first 03, is data; no in-band binary cancellation',
            'Sender must wait for SEND BIN; optional command LF is normalized before that boundary',
            'The 395-byte tail is contiguous; another 97 bytes remain scattered',
            'Legacy auxiliary tools remain inactive; not a deployable update kit'],
        checker_sha256=sha(Path(__file__)))
    (build/'b14-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b14:618 offline groups; F395 contiguous +97 scattered =492 available',flush=True)

if __name__=='__main__':main()
