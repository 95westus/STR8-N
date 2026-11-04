"""Reconstruct all remaining utility/DEV inputs; reuse only frozen F."""
import binascii,hashlib,json
from pathlib import Path
from build_mona import ROOT,cells
from rebuild_utilities import native_maint,flash
from build_loadable_maint import build as build_maint
from rebuild_devtools import build as build_dev
from rebuild_storage import build as build_storage

def rebuild(out,service_output):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    lock=json.loads((ROOT/'components/inputs/LOCK.json').read_text())
    expected={r['path']:r for r in lock['reconstructed_inputs'] if r['rebuild_recipe']=='tools/rebuild_util_dev_inputs.py'}
    mapping,witness={},[]
    def record(name,data):
        row=expected['components/inputs/accepted-base1/'+name]
        digest=hashlib.sha256(data).hexdigest()
        if len(data)!=row['bytes'] or digest!=row['sha256']:raise ValueError('Utility/DEV source reconstruction differs: '+name)
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);mapping[name]=path
        witness.append(dict(input=name,bytes=len(data),sha256=digest,file=path.relative_to(out).as_posix(),result='EXACT_MATCH'))
    native_maint(out/'native-maint')
    build_maint(out/'MAINT',out/'native-maint')
    record('rec/MAINT.bin',(out/'MAINT/MAINT.bin').read_bytes())
    body,_=flash(out/'FLASH');record('rec/FLASH.bin',body)
    dev=build_dev(out/'DEV')
    record('developer/ASM-RAM.bin',dev['ASM_RAM']);record('developer/DBG-RAM.bin',dev['DBG_RAM'])
    for name,address in [('ASM',0xa000),('DBG',0xc000)]:
        image=dev[name+'_FLASH'];record(f'native/payload/B0-{address+0x1000:04X}.bin',image[4096:])
        for cpu,flag in [('65c02',2),('65c816e',0x16)]:
            first=bytearray(image[:4096]);first[15]=flag
            first[28:30]=binascii.crc_hqx(first[:28],65535).to_bytes(2,'little')
            record(f'native/payload/B0-{address:04X}-{cpu}.bin',bytes(first))
    memory=cells(out/'DEV/decoder/decoder.s19')
    decoder=bytes(memory[a] for a in range(min(memory),max(memory)+1))
    storage=build_storage(out/'STORAGE',decoder,Path(service_output)/'PROGRAM/manifest.json')
    for index,address in enumerate((0xb000,0xc000,0xd000)):
        record(f'native/payload/B1-{address:04X}.bin',storage[index*4096:(index+1)*4096])
    record('native/payload/ERASED-4096.bin',b'\xff'*4096)
    if set(expected)!={'components/inputs/accepted-base1/'+name for name in mapping}:raise ValueError('Incomplete utility/DEV reconstruction')
    sources={}
    for folder in ('monitors/native','monitors/reference','monitors/devtools/base1'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.asm','.inc'):sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('rebuild_util_dev_inputs.py','rebuild_utilities.py','rebuild_devtools.py','rebuild_storage.py','build_native_apps.py',
                 'build_loadable_maint.py','build_sram_work.py','port_sram_work.py','port_bank_maint.py','storage_compact.py',
                 'build_storage_batch.py','build_store_front.py','build_s19_loader.py','sram_named_source.py'):
        path=ROOT/'tools'/name;sources['tools/'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(schema=1,inputs=witness,source_sha256=sources,F_rebuilt=False,board_access=False,
        compiler_generated_maps=['MAINT/maint-adapter.map','FLASH/board-tool.map'],
        source_generated_loaders=['DEV/ASM-loader/app.asm','DEV/DBG-loader/app.asm'])
    (out/'UTIL-DEV-RECONSTRUCTION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    generated=dict(maint_map=out/'MAINT/maint-adapter.map',flash_map=out/'FLASH/board-tool.map',
                   asm_template=dev['asm_template'],dbg_template=dev['dbg_template'])
    return mapping,generated,receipt
