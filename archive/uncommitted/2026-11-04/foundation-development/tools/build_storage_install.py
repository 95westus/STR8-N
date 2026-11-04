"""Link the changed storage adapters once; reuse accepted SW/RTC/PROGRAM code."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha
from mona_branches import conservative_branches
from build_storage_batch import pack_existing


def build(out,reuse=None):
    out=Path(out).resolve();out.mkdir(exist_ok=False)
    base=ROOT.parents[1]/'BUILD';q=ROOT.parents[1]/'output/qualification'
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    marker=json.loads((q/'device-operations/2512.json').read_text())
    original1=bytearray((q/'NAMED-EDU-2512-scope-20261101-r1/B1-original.bin').read_bytes())
    original1[:0x3000]=(base/'named-edu-g3-r8/BANK-MAINT-EDU-flash.bin').read_bytes()
    original1[0x3000:0x6000]=(base/'named-edu-g3-r8/SRAM-WORK-X-flash.bin').read_bytes()
    cold=q/'2512-TIME-PREP-cold-installed-20261101-r1'
    original={1:bytes(original1),2:(cold/'B2-after.bin').read_bytes(),3:(cold/'B3-after.bin').read_bytes()}
    assert all(sha(b)==marker['current_physical_bank_sha256'][f'B{bank}'] for bank,b in original.items())
    logs=[];symbols={};artifacts={};sources={}
    reused=[]
    def identical(stage,prior,name,seen=None):
        seen=set() if seen is None else seen
        if name in seen:return True
        seen.add(name);p=stage/name;old=prior/name
        return old.exists() and p.read_bytes()==old.read_bytes() and all(identical(stage,prior,n,seen) for n in re.findall(r'INCLUDE\s+"([^"]+)"',p.read_text()))
    def emit(name,body):
        (out/name).write_bytes(body);artifacts[name]=dict(bytes=len(body),sha256=sha(body))
    def link(name,prior,origin,last,filename=None,extra=()):
        stage=out/name;stage.mkdir()
        for p in prior.iterdir():
            if p.suffix in ('.inc','.asm'):shutil.copyfile(p,stage/p.name)
        for src in (filename or name+'.asm',*extra):
            source=ROOT/'monitors/native'/src;sources[str(source.relative_to(ROOT))]=sha(source.read_bytes());shutil.copyfile(source,stage/src)
        for source in (ROOT/'src/include/str8n-v2-public.inc',ROOT/'src/include/str8n-v2-eq.inc',ROOT/'src/core/boot-symbols.inc',ROOT/'src/core/worker-public-symbols.inc',ROOT/'monitors/src/batch-interface.inc'):
            shutil.copyfile(source,stage/source.name)
        text=(stage/(filename or name+'.asm')).read_text()
        text,_=conservative_branches(text,'SI_'+name.replace('-','_')+'_')
        stem=Path(filename or name+'.asm').stem;(stage/(stem+'.asm')).write_text(text)
        prior_link=Path(reuse)/name if reuse else None
        can_reuse=bool(prior_link and (prior_link/(stem+'.map')).exists() and identical(stage,prior_link,stem+'.asm'))
        if can_reuse:
            for suffix in ('.map','.s19'):shutil.copyfile(prior_link/(stem+suffix),stage/(stem+suffix))
            reused.append(name)
        for cmd in ([] if can_reuse else ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],[shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj'])):
            p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
            logs.append(dict(stage=name,command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if p.returncode:raise RuntimeError('Inspect '+str(out/'build-log.json'))
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)}
        m=cells(stage/(stem+'.s19'));assert set(m)==set(range(origin,sy[last]));symbols[name]=sy
        body=bytes(m[a] for a in range(origin,sy[last]));print(name,len(body),'linked bytes',flush=True)
        return body
    def seal(body,size):
        assert len(body)<=size-2,(len(body),size)
        b=body.ljust(size-2,b'\xff');return b+binascii.crc_hqx(b,65535).to_bytes(2,'big')
    nl=link('native-loader',base/'native-apps-g1-maint-r1',0x7000,'NL_END')
    fr=link('flash-record',base/'flash-status-correction-r4',0x6B00,'FR_END_CODE',extra=('flash-auto.inc',))
    gg=link('flash-transfer-gate',base/'flash-status-correction-r4',0x7300,'GG_END')
    assert len(nl)<=0x290,'Loader overlaps the accepted EDU reader at8E90'
    native=bytearray(original[3][0xC00:0x1000]);native[:0x290]=nl.ljust(0x290,b'\xff')
    native[-2:]=binascii.crc_hqx(native[:-2],65535).to_bytes(2,'big')
    assert native[0x290:-2]==original[3][0xE90:0xFFE]
    emit('NATIVE-LOADER-7000.bin',native);emit('FLASH-RECORD-6B00.bin',seal(fr,2048));emit('FLASH-GATE-7300.bin',seal(gg,1024))
    # Reuse the linked and RAM-qualified12853-byte SW body; only its ROM
    # capability/header and packing are finalized, with no reassembly.
    sw=out/'SW';sw.mkdir()
    for name in ('manifest.json','SRAM-WORK-BATCH-2000.bin'):
        shutil.copyfile(base/'storage-batch-g4-r1'/name,sw/name)
    sm=pack_existing(sw);emit('SRAM-WORK-g4-flash.bin',(sw/'SRAM-WORK-BATCH-flash.bin').read_bytes())
    wbdir=base/'wb2-gE-storage-batch-r1';wm=json.loads((wbdir/'manifest.json').read_text())
    wb=(wbdir/'WB2-module-4800.bin').read_bytes();assert sha(wb)==wm['module']['sha256']
    emit('WB2-gE-4800.bin',wb)
    # Reuse the accepted dispatcher support/loader. Its only changes are the
    # current source router, FG1/5 admission, and WB generation pin D->E.
    stage=out/'E';stage.mkdir();prior=base/'flash-dispatch-g1-r3/staging'
    assert original[3][0x6000:0x7000]==(base/'flash-dispatch-g1-r3/FLASH-DISPATCH-E.bin').read_bytes()
    for p in prior.iterdir():
        if p.suffix in ('.asm','.inc'):shutil.copyfile(p,stage/p.name)
    tail=len(re.findall(r'\$[0-9A-Fa-f]{2}',(prior/'service-load-image.inc').read_text()))-256
    for name in ('services.asm','service-flash-transfer.inc'):
        p=ROOT/'monitors/src'/name;sources[str(p.relative_to(ROOT))]=sha(p.read_bytes())
        text=p.read_text().replace('"WORKBENCH_GENERATION_BYTES"','$0E,$00,$00,$00').replace('SERVICE_LOADER_TAIL',str(tail))
        text,_=conservative_branches(text,'SI_E_'+name.replace('.','_').replace('-','_')+'_');(stage/name).write_text(text)
    prior_E=Path(reuse)/'E' if reuse else None
    can_reuse_E=bool(prior_E and (prior_E/'services.map').exists() and identical(stage,prior_E,'services.asm'))
    if can_reuse_E:
        for suffix in ('.map','.s19'):shutil.copyfile(prior_E/('services'+suffix),stage/('services'+suffix))
        reused.append('E')
    for cmd in ([] if can_reuse_E else ([shutil.which('wdc02as'),'-G','-L','-S','-W','services.asm'],[shutil.which('wdcln'),'-g','-s','-t','-cE000','-hm19','-j','-o','services.s19','services.obj'])):
        p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(stage='E',command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:raise RuntimeError('Inspect '+str(out/'build-log.json'))
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'services.map').read_text(),re.M)}
    m=cells(stage/'services.s19');e=bytes(m[a] for a in range(0xE000,sy['S_END']));emit('SERVICES-E.bin',seal(e,4096));symbols['E']=sy
    after={k:bytearray(v) for k,v in original.items()}
    after[1][0x3000:0x6000]=(out/'SRAM-WORK-g4-flash.bin').read_bytes()
    # Move the unchanged581-byte dense-S19 library into the already free
    # compressed-MAINT gap. Its old fragments no longer limit FR/gate growth.
    library=(base/'flash-status-correction-r4/DENSE-CONTROL-4000.bin').read_bytes();assert len(library)==581
    assert after[1][0x2090:0x2090+len(library)]==b'\xff'*len(library)
    after[1][0x2090:0x2090+len(library)]=library
    after[1][0x231D:0x2380]=b'\xff'*99
    after[1][0x2380:0x2780]=(out/'FLASH-GATE-7300.bin').read_bytes()
    after[1][0x27C0:0x2FC0]=(out/'FLASH-RECORD-6B00.bin').read_bytes()
    after[1][0x2FFE:0x3000]=binascii.crc_hqx(after[1][:0x2FFE],65535).to_bytes(2,'big')
    after[2][0x300:0x1F00]=wb
    oldfragments=json.loads((base/'flash-status-correction-r4/manifest.json').read_text())['fragments']
    table=lambda fragments:b''.join(int(x['source'],16).to_bytes(2,'little')+x['length'].to_bytes(2,'little') for x in fragments)
    pos=0x6000+32+0x29CA-0x2000;assert after[2][pos:pos+12]==table(oldfragments)
    fragments=[dict(source='A090',length=200),dict(source='A158',length=200),dict(source='A220',length=181)]
    after[2][pos:pos+12]=table(fragments);after[2][0x600E:0x6012]=(3).to_bytes(4,'little')
    after[2][-2:]=binascii.crc_hqx(after[2][0x6000:-2],65535).to_bytes(2,'big')
    after[3][0xC00:0x1000]=(out/'NATIVE-LOADER-7000.bin').read_bytes();after[3][0x6000:0x7000]=(out/'SERVICES-E.bin').read_bytes()
    assert after[1][:0x2000]==original[1][:0x2000] and after[1][0x6000:]==original[1][0x6000:]
    assert after[1][0x5900:0x5FFE]==original[1][0x5900:0x5FFE]
    assert after[2][0x7A50:0x7FFA]==original[2][0x7A50:0x7FFA]
    assert after[3][0x7000:]==original[3][0x7000:]
    changed=[]
    for bank,b in after.items():
        emit(f'B{bank}-candidate.bin',b)
        for page in range(0x80,0x100,16):
            off=(page-0x80)*256
            if b[off:off+4096]!=original[bank][off:off+4096]:changed.append(f'B{bank}:{page:02X}00')
    (out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    report=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,
        artifacts=artifacts,sources=sources,changed_sectors=changed,NL_bytes=len(nl),FR_bytes=len(fr),GG_bytes=len(gg),E_bytes=len(e),
        WB_free_bytes=7166-wm['module']['linked_bytes'],SW_reassembled=False,SW_manifest=sm,dense_library_unchanged=True,
        fragments=fragments,STATUS_details_exact=True,MON_A_B_unchanged=True,PROGRAM_provider_unchanged=True,
        EDU_reader_and_shared_help_exact=True,reused_modules=reused,
        original_bank_sha256={str(k):sha(v) for k,v in original.items()})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('changed_sectors','NL_bytes','FR_bytes','GG_bytes','E_bytes','WB_free_bytes')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse',type=Path)
    a=p.parse_args();build(a.out,a.reuse)
