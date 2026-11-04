"""Build the optional BASE1 service dispatcher/bundle once; no F rebuild/port I/O."""
import argparse
import binascii
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_mona import ROOT,cells,equs,sha
from mona_branches import conservative_branches
from status_extents import preserve_text


def reference_path(path):
    path=Path(path).resolve()
    try:return path.relative_to(ROOT).as_posix()
    except ValueError:return path.as_posix()


def build(out, generation, workbench_manifest, monitor_manifest, reuse_support=None, program_manifest=None,finish_existing=False,status_manifest=None):
    out=Path(out).resolve()
    if out.exists() and not finish_existing:raise ValueError('Use a fresh directory; preserve previous outputs')
    if not 1<=generation<=0xffffffff:raise ValueError('Generation outside1..FFFFFFFF')
    if status_manifest is None:raise ValueError('Current MON requires --status-manifest;8040/8240 are STATUS, not padding')
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    if not assembler or not linker:raise ValueError('WDC assembler/linker required')
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f)==freeze['sha256'] and len(f)==4096
    for name,digest in freeze['sources'].items():assert sha((ROOT/name).read_bytes())==digest,name
    wbpath=Path(workbench_manifest).resolve();wb=json.loads(wbpath.read_text())
    monpath=Path(monitor_manifest).resolve();mon=json.loads(monpath.read_text())
    assert wb['foundation_sha256']==mon['F_sha256']==sha(f)
    module=(wbpath.parent/wb['module']['filename']).read_bytes()
    assert sha(module)==wb['module']['sha256'] and len(module)==7168
    assert binascii.crc_hqx(module,0xffff)==0
    wb_generation=int(wb['generation'],16)
    assert module[17:23]==b'WG'+wb_generation.to_bytes(4,'little')
    if program_manifest is None:raise ValueError('Current bundle requires a PROGRAM provider manifest')
    pvpath=Path(program_manifest).resolve();pv=json.loads(pvpath.read_text())
    provider=(pvpath.parent/pv['artifact']['filename']).read_bytes()
    assert len(provider)==3328 and sha(provider)==pv['artifact']['sha256'] and binascii.crc_hqx(provider,65535)==0
    for name,digest in pv['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    bs=equs(ROOT/'src/core/boot-symbols.inc');ws=equs(ROOT/'src/core/worker-public-symbols.inc')
    crc=binascii.crc_hqx(f,0xffff)
    bindings=dict(SB_F_SELECT=ws['V2W_SELECT'],SB_F_READ=ws['V2W_READ'],SB_F_EXECUTE=ws['V2W_EXECUTE'],
                  SB_F_BOOT_READ=bs['BOOT_READ_RECORD'],SB_F_RECOVERY=bs['BOOT_RECOVERY'],
                  SB_F_CRC_LO=crc&255,SB_F_CRC_HI=crc>>8)
    inputs=('services.asm','service-layout.inc','service-map.inc','service-wear.inc',
            'service-interface.inc','service-load.asm','service-bundle-boot.asm','workbench-interface.inc','service-apps.inc','batch-interface.inc','service-transfer.inc','service-flash-transfer.inc')
    sources={'monitors/src/'+name:sha((ROOT/'monitors/src'/name).read_bytes()) for name in inputs}
    sources['src/core/map-wdc-catalog.inc']=sha((ROOT/'src/core/map-wdc-catalog.inc').read_bytes())
    out.mkdir(parents=True,exist_ok=finish_existing);logs=json.loads((out/'build-log.json').read_text()) if finish_existing else [];layouts={}
    if finish_existing:assert logs and all(row['returncode']==0 for row in logs)
    def assemble(label,stem,origin,end_symbol,ram=False,loader=None):
        stage=out/'staging'/label;stage.mkdir(parents=True,exist_ok=finish_existing)
        for name in inputs:
            text=(ROOT/'monitors/src'/name).read_text()
            text=text.replace('"SERVICE_GENERATION_BYTES"',','.join(f'${v:02X}' for v in generation.to_bytes(4,'little')))
            text=text.replace('"WORKBENCH_GENERATION_BYTES"',','.join(f'${v:02X}' for v in wb_generation.to_bytes(4,'little')))
            if label=='raw' and name=='service-bundle-boot.asm':
                text=text.replace('$8100','$0300').replace('$8200','$0400').replace('#>SB_MODULE_SOURCE','#5')
            if not name.endswith('interface.inc') and name!='service-layout.inc':
                text,info=conservative_branches(text,'S_LONG_'+label+'_'+name.replace('.','_').replace('-','_')+'_')
                layouts[label+'/'+name]=info
            if name=='services.asm' and loader is not None:
                text=text.replace('SERVICE_LOADER_TAIL',str((len(loader)-256)&255))
            if finish_existing:assert (stage/name).read_text()==text,name
            else:(stage/name).write_text(text,encoding='utf-8',newline='\n')
        shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
        shutil.copyfile(ROOT/'src/core/map-wdc-catalog.inc',stage/'map-wdc-catalog.inc')
        private=dict(bindings,SB_RAM_PROVIDER=int(ram))
        (stage/'service-foundation.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in private.items()),encoding='ascii',newline='\n')
        if loader is not None:
            assert 256 < len(loader) <= 512
            body=loader
            (stage/'service-load-image.inc').write_text(''.join('        DB '+','.join(f'${x:02X}' for x in body[i:i+16])+'\n' for i in range(0,len(body),16)),encoding='ascii',newline='\n')
            p=stage/'services.asm'
            p.write_text(p.read_text().replace('SERVICE_LOADER_TAIL',str((len(loader)-256)&255)),encoding='ascii',newline='\n')
        for command in ([] if finish_existing else ([assembler,'-G','-L','-S','-W',stem+'.asm'],
                        [linker,'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj'])):
            done=subprocess.run(command,cwd=stage,capture_output=True,text=True)
            logs.append(dict(component=label,command=command,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8',newline='\n')
            if done.returncode:raise RuntimeError('WDC failed; inspect '+str(out/'build-log.json'))
        symbols={name:int(value,16) for value,name in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)}
        memory=cells(stage/(stem+'.s19'));assert set(memory)==set(range(origin,symbols[end_symbol]))
        body=bytes(memory[a] for a in range(origin,symbols[end_symbol]))
        return body,symbols
    if reuse_support is not None:
        previous_path=Path(reuse_support).resolve();previous=json.loads(previous_path.read_text())
        assert previous['F_sha256']==sha(f) and previous['private_adapter']==bindings
        for name in ('service-load.asm','service-interface.inc','service-bundle-boot.asm','workbench-interface.inc'):
            key='monitors/src/'+name
            assert sources[key]==previous['source_sha256'][key],key
        old_name,old_info=next((n,a) for n,a in previous['artifacts'].items() if a['variant']=='B2 bundle')
        old_bundle=(previous_path.parent/old_name).read_bytes()
        assert sha(old_bundle)==old_info['sha256'] and old_bundle[768:776]==module[:8]
        # Only the loader/prefix are reused. The independently admitted current
        # provider replaces the former payload; do not require payload equality.
        assert old_bundle[7936:7944]==provider[:8]
        assert binascii.crc_hqx(old_bundle[7936:11264],65535)==0
        loader=old_bundle[256:256+old_info['loader_bytes']]
        prefix=old_bundle[:old_info['prefix_bytes']]
        old_raw_name,old_raw_info=next((n,a) for n,a in previous['artifacts'].items() if a['variant']=='Full tool RAM packet')
        old_raw=(previous_path.parent/old_raw_name).read_bytes();assert sha(old_raw)==old_raw_info['sha256']
        raw_prefix=old_raw[:old_info['prefix_bytes']]
    else:
        loader,ls=assemble('loader','service-load',0x6900,'SL_END')
        assert ls['SL_RECOVERY']<0x6a00
    assert len(loader)<=512 and 0x6900+len(loader)<=0x6b00
    artifacts={}
    images={}
    for variant,origin,ram in (('E',0xE000,False),('RAM',0x2000,True)):
        body,symbols=assemble(variant,'services',origin,'S_END',ram=ram,loader=loader)
        assert body[:8]==b'MS\x01\x10PR05' and len(body)<=4094
        image=body+b'\xff'*(4094-len(body));image+=binascii.crc_hqx(image,0xffff).to_bytes(2,'big')
        assert binascii.crc_hqx(image,0xffff)==0
        name=f'STR8N-SERVICES-g{generation:08X}-{variant}.bin'
        (out/name).write_bytes(image);images[variant]=image
        artifacts[name]=dict(variant=variant,bytes=4096,sha256=sha(image),linked_bytes=len(body),free_bytes=4094-len(body),origin=f'{origin:04X}',command_entry=f'{origin+8:04X}')
    if reuse_support is None:
        prefix,_=assemble('bundle','service-bundle-boot',0x8000,'SBB_END')
    assert len(prefix)<=256 and prefix[3:11]==b'WF\x03\x1cPR05'
    prefix=bytearray(prefix);prefix[11:15]=generation.to_bytes(4,'little');prefix=bytes(prefix)
    bundle=(prefix.ljust(256,b'\xff')+loader.ljust(512,b'\xff')+module+provider).ljust(12288,b'\xff')
    bundle=preserve_text(bundle,status_manifest)
    assert len(bundle)==12288 and bundle[768:768+7168]==module and bundle[7936:11264]==provider
    name=f'STR8N-SERVICES-g{generation:08X}-B2-8000.bin';(out/name).write_bytes(bundle)
    artifacts[name]=dict(variant='B2 bundle',bytes=12288,sha256=sha(bundle),sectors=['B2:8','B2:9','B2:A'],module_origin='8300',provider_origin='9F00',boot_entry='8000',loader_bytes=len(loader),prefix_bytes=len(prefix),free_flash_tail_bytes=1024)
    if reuse_support is None:raw_prefix,_=assemble('raw','service-bundle-boot',0x0200,'SBB_END')
    raw_prefix=bytearray(raw_prefix);raw_prefix[11:15]=generation.to_bytes(4,'little');raw_prefix=bytes(raw_prefix)
    raw=raw_prefix.ljust(256,b'\xff')+loader.ljust(512,b'\xff')+module+provider
    name=f'STR8N-TOOLS-WB2-SP1-g{generation:08X}-RAM.bin';(out/name).write_bytes(raw)
    artifacts[name]=dict(variant='Full tool RAM packet',bytes=len(raw),sha256=sha(raw),load_address='0200',module_RAM='4800-66FF',provider_RAM='6B00-77FF',temporary_6A_saved_restored=True)
    ram_item=next((name,item) for name,item in mon['artifacts'].items() if item['variant']=='RAM')
    core=(monpath.parent/ram_item[0]).read_bytes();assert sha(core)==ram_item[1]['sha256']
    assert len(core)<=0x1e00
    combined=core.ljust(0x1e00,b'\xff')+images['RAM'];assert len(combined)==0x2e00
    name=f'STR8N-MON-SERVICES-g{mon["generation"]}-RAM.bin';(out/name).write_bytes(combined)
    artifacts[name]=dict(variant='RAM trial composite',bytes=len(combined),sha256=sha(combined),RAM='0200-2FFF',service_origin='2000',core_generation=mon['generation'])
    report=dict(schema=1,component='BASE1 optional services',generation=f'{generation:08X}',
                status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',F_sha256=sha(f),source_sha256=sources,
                private_adapter=bindings,artifacts=artifacts,build_passes=1,assembler_linker_invocations=len(logs),
                bundle_generation=int.from_bytes(bundle[11:15],'little'),
                workbench_manifest=reference_path(wbpath),monitor_manifest=reference_path(monpath),program_manifest=reference_path(pvpath),
                status_manifest=reference_path(status_manifest),STATUS_text_extents_preserved=['8040-80FF','8240-82FF'],
                readonly_commands=['M1','M2','M3','W','APPS'],readonly_RAM='6700-69FF; no owner RAM/ZP writes',
                explicit_workbench_commands=['MAINT','MAINT LOAD','FLASH','CLOCK'],module_RAM='4800-66FF',provider_RAM='6B00-77FF',
                workbench_cache_admission='Exact WG/generation and MW/02/1C/PR05 CRC plus SW/1/1 and whole SP CRC; invalid caches reload',
                CLOCK='R CLOCK routes to the full b35-derived native RAM app; STATUS and canceled SET accepted separately',
                FLASH='R FLASH/R MAINT route to native sector buffer/editor, guarded BYTE/WRITE/ERASE and BOOT/HOST',
                BATCH='returning WB2 subset; no loader/flash write/application handoff',
                F_rebuilt=False,hardware_access=False,CPU_simulations=0,branch_layout=layouts,
                reused_loader_bundle_from=reference_path(reuse_support) if reuse_support else None,
                metadata_finalized_without_rebuild=finish_existing)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({name:{k:v for k,v in a.items() if k in ('bytes','linked_bytes','free_bytes')} for name,a in artifacts.items()},indent=2))
    return report


def repackage_monitor(out, source_manifest, monitor_manifest):
    """Reuse exact service/bundle images; update only the RAM trial composite."""
    out=Path(out).resolve();source_path=Path(source_manifest).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    old=json.loads(source_path.read_text());monpath=Path(monitor_manifest).resolve()
    mon=json.loads(monpath.read_text());assert old['F_sha256']==mon['F_sha256']
    for name,digest in old['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    out.mkdir(parents=True);report=json.loads(json.dumps(old));ram=None
    for name,item in old['artifacts'].items():
        if item['variant']=='RAM trial composite':continue
        body=(source_path.parent/name).read_bytes();assert sha(body)==item['sha256']
        (out/name).write_bytes(body)
        if item['variant']=='RAM':ram=body
    assert ram is not None
    name,item=next((n,a) for n,a in mon['artifacts'].items() if a['variant']=='RAM')
    core=(monpath.parent/name).read_bytes();assert sha(core)==item['sha256'] and len(core)<=0x1e00
    composite=core.ljust(0x1e00,b'\xff')+ram
    name=next(n for n,a in old['artifacts'].items() if a['variant']=='RAM trial composite')
    (out/name).write_bytes(composite)
    report['artifacts'][name].update(sha256=sha(composite),bytes=len(composite))
    report.update(monitor_manifest=str(monpath.relative_to(ROOT)),build_passes=0,assembler_linker_invocations=0,
                  reused_service_images_from=str(source_path.relative_to(ROOT)),branch_layout={})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Reused all service/bundle bytes; updated composite',sha(composite),flush=True)
    return report


def repackage_program(out, source_manifest, program_manifest):
    """Keep service, loader and MW bytes; replace only the SP/01 provider."""
    out=Path(out).resolve();oldpath=Path(source_manifest).resolve();pvpath=Path(program_manifest).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    old=json.loads(oldpath.read_text());pv=json.loads(pvpath.read_text())
    assert old['F_sha256']==json.loads((ROOT/'F_FREEZE.json').read_text())['sha256']
    for name,digest in old['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    for name,digest in pv['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    provider=(pvpath.parent/pv['artifact']['filename']).read_bytes()
    assert sha(provider)==pv['artifact']['sha256'] and len(provider)==3328
    assert provider[:8]==b'SP\x01\x0dPR05' and binascii.crc_hqx(provider,65535)==0
    report=json.loads(json.dumps(old));out.mkdir(parents=True)
    for name,item in old['artifacts'].items():
        body=(oldpath.parent/name).read_bytes();assert sha(body)==item['sha256']
        if item['variant'] in ('B2 bundle','Full tool RAM packet'):
            assert body[3:11]==b'WF\x03\x1cPR05' and body[7936:7944]==provider[:8]
            body=body[:7936]+provider+body[11264:]
            report['artifacts'][name]['sha256']=sha(body)
        (out/name).write_bytes(body)
    report.update(program_manifest=str(pvpath.relative_to(ROOT)),build_passes=0,assembler_linker_invocations=0,
                  reused_service_images_from=str(oldpath.relative_to(ROOT)),program_payload_replaced=True,branch_layout={})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Reused support and main; replaced only SP/01 provider',pv['artifact']['sha256']);return report


def repackage_main_module(out, source_manifest, workbench_manifest):
    """Reuse qualified support bytes; update only the main MW/02 image."""
    out=Path(out).resolve();oldpath=Path(source_manifest).resolve();wbpath=Path(workbench_manifest).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    old=json.loads(oldpath.read_text());wb=json.loads(wbpath.read_text())
    assert old['F_sha256']==wb['foundation_sha256']
    prior_wb=Path(old['workbench_manifest'])
    if not prior_wb.is_absolute():prior_wb=ROOT/prior_wb
    assert json.loads(prior_wb.read_text())['generation']==wb['generation'],'Changing WG requires a new dispatcher seal'
    for name,digest in old['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    module=(wbpath.parent/wb['module']['filename']).read_bytes()
    assert sha(module)==wb['module']['sha256'] and len(module)==7168 and binascii.crc_hqx(module,65535)==0
    report=json.loads(json.dumps(old));out.mkdir(parents=True)
    for name,item in old['artifacts'].items():
        body=(oldpath.parent/name).read_bytes();assert sha(body)==item['sha256']
        if item['variant'] in ('B2 bundle','Full tool RAM packet'):
            assert body[768:776]==module[:8] and body[3:11]==b'WF\x03\x1cPR05'
            body=body[:768]+module+body[7936:]
            report['artifacts'][name]['sha256']=sha(body)
        (out/name).write_bytes(body)
    report.update(workbench_manifest=reference_path(wbpath),build_passes=0,assembler_linker_invocations=0,
                  reused_service_images_from=reference_path(oldpath),module_payload_replaced=True,branch_layout={})
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Reused all support; replaced only main MW/02 payload',wb['generation']);return report


def repackage_workbench(out, source_manifest, workbench_manifest, generation, bundle_generation=None):
    """Keep dispatcher/loader code; replace the versioned module payload only."""
    out=Path(out).resolve();source_path=Path(source_manifest).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    old=json.loads(source_path.read_text(encoding='utf-8'))
    wbpath=Path(workbench_manifest).resolve();wb=json.loads(wbpath.read_text(encoding='utf-8'))
    assert old['F_sha256']==wb['foundation_sha256'] and old['generation']==f'{generation:08X}'
    bundle_generation=generation if bundle_generation is None else bundle_generation
    assert 1<=bundle_generation<=0xffffffff
    for name,digest in old['source_sha256'].items():assert sha((ROOT/name).read_bytes())==digest,name
    module=(wbpath.parent/wb['module']['filename']).read_bytes()
    assert sha(module)==wb['module']['sha256'] and len(module)==7168 and binascii.crc_hqx(module,65535)==0
    report=json.loads(json.dumps(old));out.mkdir(parents=True)
    for name,item in old['artifacts'].items():
        body=(source_path.parent/name).read_bytes();assert sha(body)==item['sha256']
        if item['variant']=='B2 bundle':
            assert body[512:520]==module[:8] and body[3:11]==b'WF\x02\x1cPR05'
            prefix=bytearray(body[:512]);prefix[11:15]=bundle_generation.to_bytes(4,'little')
            body=(bytes(prefix)+module).ljust(8192,b'\xff')
            report['artifacts'][name]['sha256']=sha(body)
        (out/name).write_bytes(body)
    report.update(workbench_manifest=str(wbpath.relative_to(ROOT)),bundle_generation=bundle_generation,
                  build_passes=0,assembler_linker_invocations=0,branch_layout={},
                  reused_service_images_from=str(source_path.relative_to(ROOT)),module_payload_replaced=True)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Reused dispatcher and loaders; repackaged WB2 payload',wb['generation'],flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--generation',type=lambda s:int(s,0),required=True)
    p.add_argument('--workbench-manifest',type=Path,required=True);p.add_argument('--monitor-manifest',type=Path,required=True)
    p.add_argument('--reuse-support',type=Path)
    p.add_argument('--program-manifest',type=Path,required=True)
    p.add_argument('--finish-existing',action='store_true')
    p.add_argument('--status-manifest',type=Path,required=True)
    a=p.parse_args();build(a.out,a.generation,a.workbench_manifest,a.monitor_manifest,a.reuse_support,a.program_manifest,a.finish_existing,a.status_manifest)
