"""Offline b13 packing experiment: retain PR04 entries and coalesce F space."""
import argparse,json,re,sys
from pathlib import Path
import build_b12 as previous

HERE=previous.HERE;ROOT=previous.ROOT
BASE=ROOT/'BUILD/pr04-b12-no-readback-r4'
HELP=previous.HELP
PACK={}

def b13_source(source):
    source=previous.b12_source(source)
    old=json.loads((BASE/'symbols.json').read_bytes())['core/str8n-v2-boot']
    a,b=source.index('BOOT_SLOT_CHECK:'),source.index('BOOT_SR_ROUTE:')
    checker=source[a:b];shortened=[]
    def short(m):
        op,label,dest=m.groups()
        if -127<=old[dest]-(old[label]-3)<=127:
            shortened.append(dict(label=label,target=dest))
            return '        '+previous.previous.INVERSE[op]+' '+dest+'\n'
        return m[0]
    checker=re.sub(r'        (BEQ|BNE|BCS|BCC|BMI|BPL|BVS|BVC) (P_LONG_\d+)\n        JMP (\w+)\n\2:\n',short,checker)
    assert len(shortened)==21,len(shortened)
    start=source.index('BOOT_STARTUP:')
    startup=source[start:];source=source[:start]
    usb= startup[:startup.index('BOOT_USB_WAIT_DONE:')].replace('BOOT_STARTUP:','B13_USB_START:',1)
    setup=startup[startup.index('BOOT_USB_WAIT_DONE:'):startup.index('BOOT_DRAIN_BEGIN:')]
    drain=startup[startup.index('BOOT_DRAIN_BEGIN:'):startup.index('BOOT_DRAIN_DONE:')]
    finish=startup[startup.index('BOOT_DRAIN_DONE:'):]
    # The drain's 59 instruction bytes remain identical, including balanced
    # input paths. Its new location stays within one page, as before.
    relocated=drain+'        JMP BOOT_DRAIN_DONE\n'+previous.pad('B13_FREE_SLOT',1)
    assert 21*3==59+3+1
    # Replace the validator interval before inserting startup chunks; retain
    # the original route, print, CRC, worker, vector and startup entry addresses.
    source=source[:a]+checker+relocated+source[b:]
    def fill(label,capacity,body,size):
        nonlocal source
        pattern=label+r':\n        DB [^\n]+\n'
        replacement=body+previous.pad('B13_FREE_'+label,capacity-size)
        source,n=re.subn(pattern,lambda _:replacement,source);assert n==1,label
    fill('B12_FREE_B12_HELP_TAIL',21,usb+'        JMP BOOT_USB_WAIT_DONE\n',11)
    fill('B12_FREE_TX_ERROR',32,setup+'        JMP BOOT_DRAIN_BEGIN\n',26)
    fill('B12_FREE_LOADED',14,finish,14)
    source+='BOOT_STARTUP:\n        JMP B13_USB_START\n'
    PACK.update(shortened_validation_branches=shortened,branch_bytes_saved=63,
                startup_instruction_bytes_relocated=104,new_JMP_overhead_bytes=12,
                net_reclaimed_bytes=51)
    return source

def main():
    source=Path(previous.previous.__file__).read_text()
    source=source[source.index('def main():'):source.index("if __name__=='__main__':")]
    source=source.replace('0x8000000B','0x8000000D').replace('2.0proto b11','2.0proto b13')
    source=source.replace('b11_source','b13_source')
    ns=dict(__file__=__file__,HERE=HERE,ROOT=ROOT,Path=Path,argparse=argparse,json=json,sys=sys,HELP=HELP,b13_source=b13_source)
    exec(compile(source,str(Path(previous.previous.__file__)),'exec'),ns);ns['main']()
    out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'prototype-report.json'
    report=json.loads(path.read_bytes());report.pop('b11_recovery_patch')
    old=json.loads((BASE/'symbols.json').read_bytes())['core/str8n-v2-boot']
    new=json.loads((out/'symbols.json').read_bytes())['core/str8n-v2-boot']
    # Retain every pre-existing F symbol except validator internals, removed
    # branch aliases, relocated startup internals, and explicitly named gaps.
    allowed=set(k for k,v in old.items() if old['BOOT_SLOT_CHECK']<v<old['BOOT_SR_ROUTE'])
    allowed.update(k for k,v in old.items() if old['BOOT_STARTUP']<v<old['BOOT_END'])
    allowed.update(k for k in old if k.startswith(('B12_FREE_','P_LONG_')))
    allowed.update(('BOOT_END','_END_CODE'))
    fixed={k:v for k,v in old.items() if k not in allowed}
    for label,address in fixed.items():assert new.get(label)==address,(label,hex(address),new.get(label))
    same=[]
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        assert (out/'payload'/name).read_bytes()==(BASE/'payload'/name).read_bytes(),name
        same.append(name)
    f=(out/'payload/f-offline-component.bin').read_bytes()
    assert new['BOOT_END']==0xff1c and report['f']['free']==196
    assert f[0xf1c:0xfe0]==b'\xff'*196
    oldf=(BASE/'payload/f-offline-component.bin').read_bytes()
    def span(data,sym,first,last):return data[sym[first]-0xf000:sym[last]-0xf000]
    begin=new['BOOT_DRAIN_BEGIN']-0xf000
    assert f[begin:begin+59]==span(oldf,old,'BOOT_DRAIN_BEGIN','BOOT_DRAIN_DONE')
    assert new['BOOT_DRAIN_BEGIN']>>8==(new['BOOT_DRAIN_BEGIN']+58)>>8
    for first,last in [('BOOT_WORKER_IMAGE','BOOT_VECTOR_IMAGE'),('BOOT_VECTOR_IMAGE','BOOT_STARTUP')]:
        assert span(f,new,first,last)==span(oldf,old,first,last)
    # Changed MON bytes are restricted to generation, identity and header CRC.
    mon_diffs={}
    for sector in ('a0','b0'):
        name=f'monitor-{sector}-offline-component.bin'
        x=(BASE/'payload'/name).read_bytes();y=(out/'payload'/name).read_bytes()
        diffs=[i for i,(u,v) in enumerate(zip(x,y)) if u!=v]
        assert diffs==[8,18,19,2511],diffs
        mon_diffs[name]=diffs
    holes={}
    for label,address in new.items():
        if label.startswith(('B12_FREE_','B12_EXISTING_MENU_PAD','B13_FREE_')):
            # Only labels still present denote retained allocations.
            count=previous.SPARES.get(label)
            if count is not None and count:holes[label]=dict(address=address,bytes=count)
    report['b13_packing']=dict(**PACK,offline_only=True,hardware_flashed=False,
        previous_build=str(BASE.relative_to(ROOT)),fixed_F_symbols=fixed,
        fixed_F_symbol_count=len(fixed),shared_PR04_entry_addresses_unchanged=True,
        standalone_RAM_tools_byte_identical_to_b12=same,monitor_changed_offsets=mon_diffs,
        internal_spare_regions=holes,internal_spare_bytes=sum(x['bytes'] for x in holes.values()),
        contiguous_free_start=new['BOOT_END'],contiguous_free_end_inclusive=0xffdf,
        contiguous_free_bytes=196,total_spare_bytes=240,
        drain_instruction_bytes_identical=True,drain_page_crossing_unchanged=True)
    assert report['b13_packing']['internal_spare_bytes']==44,holes
    report['new_f_features']=[x for x in report['new_f_features'] if x!='RAM readback and escrow']
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS b13 offline packing',report['f'],report['monitors'],flush=True)

if __name__=='__main__':main()
