"""Hash-bound b12 offline results, compatibility and exact F space accounting."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    old=ROOT/'BUILD/pr04-b11-help-r7';report=read(build/'prototype-report.json')
    sy=read(build/'symbols.json');a=read(old/'symbols.json')['core/str8n-v2-boot'];b=sy['core/str8n-v2-boot']
    x=(old/'payload/f-offline-component.bin').read_bytes();y=(build/'payload/f-offline-component.bin').read_bytes()
    assert report['banner']=='2.0proto b12' and report['experimental_generation']==0x8000000c and report['bootstrap_contract']=='PR04'
    assert not any(k in b for k in ['RL_DUMP','RL_VERIFY','RL_OUTPUT','DC_BINARY_TX_BAD'])
    for label in a:
        if label.startswith('BOOT_API_') or label in ['BOOT_RESET','BOOT_READ_RECORD','BOOT_CHECK_FIELDS','BOOT_PRINT','J_CRC_INIT','J_CRC_BYTE','RL_LOAD','RL_GET','RL_ADVANCE','BOOT_STARTUP']:
            assert a[label]==b[label],label
    def span(body,sy,first,last):return body[sy[first]-0xf000:sy[last]-0xf000]
    assert span(x,a,'RL_LOAD','DC_BINARY_TX_BAD')==span(y,b,'RL_LOAD','B12_FREE_TX_ERROR')
    before=span(x,a,'RL_GET','RL_ADVANCE');after=span(y,b,'RL_GET','RL_ADVANCE')
    offset=a['B10_HEADER_GET']-a['RL_GET']+4
    assert before[offset-1]==after[offset-1]==0x4c
    adjusted=bytearray(before);adjusted[offset:offset+2]=b['B10_WAIT_FIRST'].to_bytes(2,'little');assert bytes(adjusted)==after
    assert span(x,a,'BR_COUNTDOWN','BR_DEFAULT')==span(y,b,'BR_COUNTDOWN','BR_DEFAULT')
    startup=bytearray(span(x,a,'BOOT_STARTUP','BOOT_CONSUMING'))
    pattern=bytes([0xa2,a['BOOT_CONSUMING']&255,0xa0,a['BOOT_CONSUMING']>>8]);assert startup.count(pattern)==1
    startup=startup.replace(pattern,bytes([0xa2,b['BOOT_CONSUMING']&255,0xa0,b['BOOT_CONSUMING']>>8]))
    assert bytes(startup)==y[b['BOOT_STARTUP']-0xf000:b['BOOT_STARTUP']-0xf000+len(startup)]
    assert x[0xfe0:]==y[0xfe0:]
    unchanged={}
    for name in ['ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1']:
        assert (old/'payload'/name).read_bytes()==(build/'payload'/name).read_bytes();unchanged[name]=sha(build/'payload'/name)
    for label,count in [('BOOT_WORKER_IMAGE',1000),('BOOT_VECTOR_IMAGE',196)]:
        start=a[label]-0xf000;assert a[label]==b[label] and x[start:start+count]==y[start:start+count]
    for name in ['monitor-a0-offline-component.bin','monitor-b0-offline-component.bin']:
        c=(old/'payload'/name).read_bytes();d=(build/'payload'/name).read_bytes()
        assert [n for n in range(4096) if c[n]!=d[n]]==[8,18,19,2511]
    patch=report['b12_recovery_patch'];holes=set();regions=[]
    for label,count in patch['internal_spare_regions'].items():
        start=b[label]-0xf000;cells=set(range(start,start+count));assert not holes&cells;holes|=cells
        byte=0xea if label in ['B12_FREE_DISPATCH','B12_EXISTING_MENU_PAD'] else 0xff
        assert y[start:start+count]==bytes([byte])*count
        regions.append(dict(label=label,address_hex=f'{b[label]:04X}',bytes=count))
    assert report['f']['bytes']==3969 and report['f']['free']==95 and len(holes)==94
    assert 4096==3969+95+32 and 3969-94==3875 and patch['newly_reclaimed_bytes']==95+94-8==181
    receipts=[];groups={}
    for name,count in [('cpu-tests.json',352),('b12-selection-tests.json',426),('b12-wait-tests.json',32),('b12-command-tests.json',36)]:
        row=read(build/name);assert row['passed'] and row['checks']==count and row['failures']==0
        receipts.append(name);groups[name]=count
    assert read(build/'b12-selection-tests.json')['frozen_b07_checker_adaptation']['adapter_sha256']==sha(HERE/'test_b12_core.py')
    for name,checker in [('b12-selection-tests.json','test_b12.py'),('b12-wait-tests.json','test_b12_wait.py'),('b12-command-tests.json','test_b12_commands.py')]:
        assert read(build/name)['checker_sha256']==sha(HERE/checker)
    for cpu in ['65c02','65c816-e']:
        name=f'b12-usb-wait-{cpu}.json';row=read(build/name)
        assert row['passed'] and row['cycles']==15998781 and row['F_sha256']==sha(build/'payload/f-offline-component.bin');receipts.append(name)
    bench=read(build/'bench-target-tests.json');assert bench['passed'] and len(bench['cases'])==4;receipts.append('bench-target-tests.json')
    for name,digest in read(build/'cpu-tests.json')['component_hashes'].items():assert sha(build/'payload'/name)==digest
    manifest=read(build/'bench-target.json');assert manifest['firmware_sha256']==sha(build/'firmware.bin')
    assert manifest['installation_permitted'] is False and not any('readback' in s or 'escrow' in s for s in manifest['enabled_features'])
    receipts+=['prototype-report.json','bench-target.json','symbols.json','firmware.bin']
    result=dict(passed=True,failures=0,hardware=False,flashed=False,identity='2.0proto b12',generation_hex='8000000C',
        regression_and_selection_groups=426,receive_groups=32,command_groups=36,USB_timing_groups=2,bench_groups=4,total_test_groups=500,
        F=dict(body_span_bytes=3969,active_code_data_bytes=3875,reserved_vector_bytes=32,contiguous_free_bytes=95,
            internal_padding_bytes=94,total_available_bytes=189,additional_available_vs_b11=181,additional_contiguous_vs_b11=94,regions=regions),
        MON=dict(body_bytes_each=3830,header_bytes_each=128,free_bytes_each=138),
        unchanged_RAM_tools=unchanged,shared_PR04_entries_preserved=True,RLP1_loader_validation_retained=True,
        recovery_RAM_may_be_overwritten=True,receipt_bindings=[dict(file=n,sha256=sha(build/n)) for n in receipts],
        source_bindings={n:sha(HERE/n) for n in ['build_b12.py','test_b12_core.py','test_b12.py','test_b12_wait.py','test_b12_commands.py','test_b12_usb_wait.py','bench_b12.py']},
        checker_sha256=sha(Path(__file__)),limitations=['Offline only; no b12 hardware boot or deployment qualification',
            'Existing b11 deployment recovery probe uses V and requires adaptation before a b12 installation',
            'Internal padding is split across regions; 189 bytes is not one contiguous block',
            'ACIA electrical behaviour is not measured; both consoles tested with CPU/register models'])
    (build/'b12-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS b12:500 groups; zero failures; F95 contiguous +94 internal =189 available,181 reclaimed',flush=True)

if __name__=='__main__':main()
