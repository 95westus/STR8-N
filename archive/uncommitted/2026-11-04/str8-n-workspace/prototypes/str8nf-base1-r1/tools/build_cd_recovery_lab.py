"""Build JCR1 once: C/D-only source-bound interruption/repair lab, frozen F.

One unrendered 0200-4FFF RAM template; per-phase metadata/frames are rendered
without assembly. The template refuses. No CPU model or hardware access.
Production CONFIG, its writer, frozen F and existing kit remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from build import cells,db
from build_system import long_branches

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'migration-host'))
import nf_migrate as p
sha=lambda body:hashlib.sha256(body).hexdigest()


def build(out,backup):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    original=Path(backup).read_bytes()
    j=p.classify_journal(original)
    assert len(original)==32768 and j['sequence']==965 and j['valid_records']==3
    assert j['default']=='B' and j['enabled_mask']==15 and j['entries']==[8]*4
    assert (j['counts'][28],j['counts'][29],j['counts'][31])==(49,29,24)
    rows=[original[a-0x8000:a-0x7f00] for a in (0xc000,0xc100,0xd000)]
    assert [int.from_bytes(row[8:12],'little') for row in rows]==[964,965,963]
    assert all(p.valid_snapshot(row) for row in rows)
    lock=json.loads((ROOT/'F_FREEZE.json').read_text())
    for name,digest in lock['sources'].items():assert sha((ROOT/name).read_bytes())==digest,name
    f=(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert original[-4096:]==f and sha(f)==lock['sha256']
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    if not assembler or not linker:raise ValueError('WDC tools required')
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src/core',out/'core');shutil.copytree(ROOT/'src/include',out/'include')
    core=out/'core'
    pins='JR_F_HASH:\n'
    db(core/'jr-f-hash.inc',p.fnv(f).to_bytes(4,'little'))
    db(core/'jr-original-hashes.inc',b''.join(p.fnv(row).to_bytes(4,'little') for row in rows))
    (core/'jr-pins.inc').write_text(pins+'        INCLUDE "jr-f-hash.inc"\nJR_ORIGINAL_HASHES:\n        INCLUDE "jr-original-hashes.inc"\n',encoding='ascii')
    migrator=(ROOT/'migrator/nf-migrate.asm').read_text()
    fnv=migrator[migrator.index('HASH_RANGE:\n'):migrator.index('SELECT_BANK:\n')]
    names={'PTR':'V2_PTR','HASH':'JR_HASH','TERM':'JR_TERM',
        'STOP_LO':'JR_STOP_LO','STOP_HI':'JR_STOP_HI'}
    for name in re.findall(r'^(\w+):',fnv,re.M):names[name]='JR_'+name
    names['FNV_OFFSET']='JR_FNV_OFFSET'
    fnv=re.sub(r'\b[A-Z][A-Z_0-9]*\b',lambda match:names.get(match[0],match[0]),fnv)
    fnv+='JR_FNV_OFFSET: DB $C5,$9D,$1C,$81\n'
    (core/'jr-fnv.inc').write_text(fnv,encoding='ascii')
    config=(core/'ram-config.asm').read_text()
    assert config.count('CONFIG_START:\n')==1
    config=config.replace('CONFIG_START:\n','CONFIG_START:\n        JMP JR_START\n')
    config=config.replace('        INCLUDE "config-engine.inc"',
        '        INCLUDE "cd-recovery-lab.inc"\n        INCLUDE "config-engine.inc"')
    (core/'ram-config.asm').write_text(long_branches(config,'JR_CFG_LONG_'),encoding='ascii',newline='\n')
    engine=(core/'config-engine.inc').read_text()
    replacements={
        'JE_WRITE:\n':'''JE_WRITE:
        LDA JE_DEST
        CMP #$C0
        BCC JE_SPACE_BAD
        CMP #$E0
        BCS JE_SPACE_BAD
        LDA JR_META+5
        CMP #2
        BEQ JE_LONG_59
''',
        '        LDA JE_FRAME,X\n        CMP #$FF\n        BNE CE_LONG_61':
            '        LDA JE_FRAME,X\n        CMP (V2_FLASH_PTR)\n        BEQ JE_WRITE_NEXT\n        CMP #$FF\n        BNE CE_LONG_61',
        'JE_WRITE_NEXT:\n        INC V2_FLASH_PTR\n        INC J_INDEX\n        LDA J_INDEX\n':
            'JE_WRITE_NEXT:\n        INC V2_FLASH_PTR\n        INC J_INDEX\n        JSR JR_AFTER_BYTE\n        LDA J_INDEX\n',
        'CE_LONG_65:\n        STZ V2_FLASH_DATA':
            'CE_LONG_65:\n        JSR JR_BEFORE_COMMIT\n        STZ V2_FLASH_DATA',
        'JE_LONG_66:\n        SEC\n':
            'JE_LONG_66:\n        JSR JR_AFTER_COMMIT\n        SEC\n',
        'CE_LONG_49:\nJE_PEER_FREE:':
            'CE_LONG_49:\n        JSR JR_PEER_ERASED\nJE_PEER_FREE:',
    }
    for before,after in replacements.items():
        if engine.count(before)!=1:raise ValueError('Changed writer anchor: '+before)
        engine=engine.replace(before,after)
    (core/'config-engine.inc').write_text(long_branches(engine,'JR_ENGINE_LONG_'),encoding='ascii',newline='\n')
    helper=(core/'cd-recovery-lab.inc').read_text()
    (core/'cd-recovery-lab.inc').write_text(long_branches(helper,'JR_HELPER_LONG_'),encoding='ascii',newline='\n')
    logs=[]
    for command in ([assembler,'-G','-L','-S','-W','-I',str(core),'ram-config.asm'],
                    [linker,'-g','-s','-t','-c0200','-hm19','-j','-o','ram-config.s19','ram-config.obj']):
        result=subprocess.run(command,cwd=core,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
        if result.returncode:raise RuntimeError('Inspect build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(core/'ram-config.map').read_text(),re.M)}
    memory=cells(core/'ram-config.s19');assert set(memory)==set(range(0x200,sy['CONFIG_END']))
    assert sy['CONFIG_END']<0x4000,'Code overlaps rendered parameters'
    template=bytearray(0x4e00)
    for a,value in memory.items():template[a-0x200]=value
    assert template[0x3e00:]==bytes(0x1000)
    (out/'JCR1-CD-RECOVERY-TEMPLATE.bin').write_bytes(template)
    report=dict(schema=1,protocol='JCR1',template_sha256=sha(template),bytes=len(template),
        code_end=f'{sy["CONFIG_END"]:04X}',status='unrendered-template-refuses',
        F_rebuilt=False,F_sha256=sha(f),CPU_simulations=0,hardware_access=False,
        production_CONFIG_changed=False,writer_source_sha256=sha((ROOT/'src/core/config-engine.inc').read_bytes()),
        original_record_sha256=[sha(row) for row in rows],
        allowed_flash='B3:C/D only; no F write path in lab entry',
        ops={'1':'append','2':'exact-preimage resume','3':'original-record restore',
             '4':'native peer rotation, stop after erase','5':'committed no-op',
             '6':'bounded blank-page fill','7':'publish recovered peer after exact original-row restore'},
        helper_source_sha256=sha((ROOT/'src/core/cd-recovery-lab.inc').read_bytes()),
        instrumented_writer_sha256=sha(engine.encode()))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--original-b3',type=Path,required=True)
    args=parser.parse_args();build(args.out,args.original_b3)
