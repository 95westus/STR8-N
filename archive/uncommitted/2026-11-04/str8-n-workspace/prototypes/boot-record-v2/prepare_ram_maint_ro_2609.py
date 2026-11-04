"""Build/verify the first, read-only b15 RAM MAINT; no device access."""
import argparse,json,re,shutil
from pathlib import Path
import prepare_ram_config_2609 as base
from str8build.assemble import Assembly
from str8build.formats import crc,read_s19

ROOT,HERE,TARGET,SESSION=base.ROOT,base.HERE,base.TARGET,base.SESSION
BIN='2609-MAINT-RO-RAM.bin'


def source():
    banks,baseline,_=base.baseline();run=SESSION/'step13-F-demo-live'
    report=base.read(run/'report.json');audit=base.read(run/'audit.json')
    assert report['passed'] and audit['passed'] and audit['report_sha256']==base.digest(run/'report.json')
    assert audit['all_128KiB_flash_unchanged'] and report['final_REC_verified'] and report['port_released']
    paths=[run/'report.json',run/'audit.json',Path(__file__),HERE/'ram-maint-ro-b15.asm',
           TARGET/'symbols.json',TARGET/'prototype-report.json',TARGET/'payload/f-offline-component.bin',
           TARGET/'s/core/prototype-engine.inc',SESSION/'step09-VERSION-install/host-wear-after.json']
    for n in range(4):
        a,b=(run/f'after-r{r}-b{n}.bin' for r in (1,2));assert a.read_bytes()==b.read_bytes()==banks[n]
        paths.extend((a,b))
    paths.extend(TARGET.glob('s/**/*.inc'))
    baseline=dict(baseline,source_run=str(run))
    return banks,baseline,{str(p.resolve()):base.binding(p) for p in paths}


def prepare(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT/'output/qualification') and not out.exists()
    banks,baseline,inputs=source();marker=ROOT/'output/qualification/device-operations/2609.json';marker_sha=base.digest(marker)
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n')
    shutil.copytree(TARGET/'s',out/'s');(out/'payload').mkdir();core=out/'s/core'
    text=(HERE/'ram-maint-ro-b15.asm').read_text()
    externals=set(re.findall(r'\b(?:JSR|JMP)\s+(\w+)',text))
    allowed={'BOOT_API_LINE','BOOT_READ_RECORD','V2W_SELECT','STR8V2_RAM_RESET','STR8V2_RAM_PUTC',
             'STR8V2_RAM_HEX_OUT','STR8V2_RAM_NEWLINE'}
    assert {name for name in externals if not name.startswith('MA_')}==allowed
    (core/'ram-maint-ro.asm').write_text(base.long_branches(text).replace('P_LONG_','MRO_LONG_'))
    duplicate='MA_CHECK_DUPLICATES:\n'+(TARGET/'s/core/prototype-engine.inc').read_text().split('JE_CHECK_DUPLICATES:',1)[1].split('JE_END:',1)[0]
    duplicate=duplicate.replace('JE_FRAME','MA_JOURNAL').replace('JE_','MDUP_')
    assert not re.search(r'\b(?:STA|STZ|INC|DEC)\s+\(',duplicate)
    (core/'maint-ro-duplicates.inc').write_text(base.long_branches(duplicate).replace('P_LONG_','MD_LONG_'))
    fcrc=crc(banks[3][-4096:])
    (core/'maint-ro-params.inc').write_text(f'MA_F_CRC_LO EQU ${fcrc&255:02X}\nMA_F_CRC_HI EQU ${fcrc>>8:02X}\n')
    guards=bytearray();guard_rows=[]
    for name in ('worker','vectors'):
        cells=read_s19(TARGET/f's/core/str8n-v2-{name}.s19');start=min(cells);data=bytes(cells[a] for a in range(start,max(cells)+1))
        guards.extend(start.to_bytes(2,'little')+len(data).to_bytes(2,'little')+crc(data).to_bytes(2,'little'))
        guard_rows.append(dict(name=name,start=start,bytes=len(data),CRC16=f'{crc(data):04X}'))
        inputs[str((TARGET/f's/core/str8n-v2-{name}.s19').resolve())]=base.binding(TARGET/f's/core/str8n-v2-{name}.s19')
    (core/'maint-ro-ram-guards.inc').write_text(' DB '+','.join(f'${n:02X}' for n in guards)+'\n')
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled=[];a.symbols=base.read(TARGET/'symbols.json')
    body,sy=a.link('core','ram-maint-ro',0x200,'MA_END');body=bytearray(body)
    assert sy['MA_START']==0x200 and sy['MA_END']<=0x2000
    offset=sy['MA_IMAGE_CRC']-0x200;assert sy['MA_IMM_END']==sy['MA_IMAGE_CRC']+2
    body[offset:offset+2]=crc(body[:offset]).to_bytes(2,'big');assert crc(body[:sy['MA_IMM_END']-0x200])==0
    a.emit(BIN,body);shutil.copy2(TARGET/'payload/f-offline-component.bin',out/'payload/f-offline-component.bin')
    shutil.copy2(TARGET/'prototype-report.json',out/'prototype-report.json');base.save(out/'symbols.json',a.symbols)
    base.save(out/'baseline.json',baseline)
    for n,data in enumerate(banks):(out/f'source-b{n}.bin').write_bytes(data)
    artifacts=[*out.glob('source-b?.bin'),*list((out/'payload').glob('*.bin')),out/'symbols.json',out/'baseline.json',out/'prototype-report.json',
               *[core/name for name in ('ram-maint-ro.asm','maint-ro-duplicates.inc','maint-ro-params.inc','maint-ro-ram-guards.inc')]]
    assert not base.ATTEMPTS and base.digest(marker)==marker_sha
    info=dict(passed=True,build_only=True,board='2609',hardware=False,board_access=False,serial_access=False,RAM_uploaded=False,
        flash_writes=False,saved_setting_writes=False,BIN=BIN,bytes=len(body),sha256=base.sha(body),start='0200',end_exclusive=f'{sy["MA_END"]:04X}',
        immutable_end_exclusive=f'{sy["MA_IMM_END"]:04X}',buffer='5000-5FFF',F_sha256=base.F_SHA,F_CRC16=f'{fcrc:04X}',RAM_guards=guard_rows,
        external_calls=sorted(allowed),no_writer_linked=True,baseline=baseline,marker_sha256=marker_sha,inputs=inputs,
        commands=['?','M [1|2|3]','R src first last','D [offset [end]]','K [src first last]','V src first last dst start','Q'],
        artifacts={str(p.relative_to(out)):base.binding(p) for p in artifacts})
    base.save(out/'build.json',info)
    print('BUILT',BIN,len(body),'bytes; immutable/F/RAM CRC guards; no writer or saved-setting command',flush=True)
    return info


def verify(out):
    out=Path(out).resolve();info=base.read(out/'build.json')
    for name,value in info['inputs'].items():assert base.digest(name)==value['sha256'],'Changed input '+name
    for name,value in info['artifacts'].items():assert base.digest(out/name)==value['sha256'],'Changed artifact '+name
    assert base.digest(out/'payload'/BIN)==info['sha256'] and info['no_writer_linked']
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();prepare(args.out) if args.command=='prepare' else verify(args.out)
