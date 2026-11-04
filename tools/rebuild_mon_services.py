"""Reconstruct MON and runtime service sectors from versioned source; F stays frozen."""
import binascii,hashlib,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells
from build_native_apps import normalized,sealed
from mona_branches import conservative_branches


def assemble(stage,stem,origin,end,transform=True):
    if transform:
        path=stage/(stem+'.asm')
        text=re.sub(r'^\s*XDEF\s+.*$','',path.read_text(encoding='utf-8'),flags=re.M)
        text,_=conservative_branches(normalized(text),stem.upper().replace('-','_')+'_LONG_')
        path.write_text(text,encoding='utf-8',newline='\n')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],
                [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj']):
        if not cmd[0]:raise RuntimeError('WDC02AS/WDCLN must be on PATH')
        result=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,code=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (stage/(stem+'-build.json')).write_text(json.dumps(logs,indent=2)+'\n')
        if result.returncode:raise RuntimeError('Assembly failed; see '+str(stage/(stem+'-build.json')))
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/(stem+'.map')).read_text(),re.M)}
    memory=cells(stage/(stem+'.s19'))
    if set(memory)!=set(range(origin,symbols[end])):raise ValueError('Noncontiguous service module: '+stem)
    return bytes(memory[a] for a in range(origin,symbols[end])),symbols


def dispatcher(stage,support):
    stage.mkdir(parents=True,exist_ok=False)
    for path in support.glob('*.inc'):shutil.copyfile(path,stage/path.name)
    text=(ROOT/'monitors/src/services.asm').read_text(encoding='utf-8')
    marker='S_MODULE_NAMES:\n'
    alias='''S_MODULE_NAMES:
 LDX #<DT_R_ASM
 LDY #>DT_R_ASM
 JSR S_MATCH
 BCS DT_R_APP
 LDX #<DT_R_DBG
 LDY #>DT_R_DBG
 JSR S_MATCH
 BCC DT_NOT_APP
DT_R_APP:
 LDX #2
 JMP AP_LAUNCH
DT_NOT_APP:
'''
    if text.count(marker)!=1:raise ValueError('Dispatcher alias insertion moved')
    text=text.replace(marker,alias).replace('\nS_END:\n','\nDT_R_ASM: DB "R ASM",0\nDT_R_DBG: DB "R DBG",0\nS_END:\n')
    old='B1:8-A MAINT,B-D SRAM; B2 tools.'
    if text.count(old)!=1:raise ValueError('Dispatcher layout help moved')
    text=text.replace(old,'B1:A xfer,B-D SRAM; B2 tools.'.ljust(len(old)))
    loader=(stage/'service-load-image.inc').read_text()
    length=len(re.findall(r'\$[0-9A-Fa-f]{2}',loader))
    if not 256<length<=512:raise ValueError('Service loader allocation changed')
    text=text.replace('SERVICE_LOADER_TAIL',str(length-256))
    text=text.replace('"WORKBENCH_GENERATION_BYTES"',','.join(f'${v:02X}' for v in (14).to_bytes(4,'little')))
    apps=(ROOT/'monitors/src/service-apps.inc').read_text(encoding='utf-8')
    a=apps.index('AP_NATIVE_TEXT:');b=apps.index('AP_MISSING_TEXT:',a)
    # The qualified REC cleanup retained this field's width and directed
    # FLASH/MAINT users to their standalone RAM packets.
    help_line='R CLOCK; FLASH/MAINT: RAM BIN'.ljust(len('R CLOCK/FLASH/MAINT; EDU SRAM WORK'))
    apps=apps[:a]+'AP_NATIVE_TEXT: DB "'+help_line+'",13,10\n DB "R/APP name",13,10,0\n'+apps[b:]
    (stage/'service-apps.inc').write_text(apps,encoding='utf-8')
    for path in stage.glob('*.inc'):
        source=path.read_text(encoding='utf-8')
        if path.name not in ('str8n-v2-public.inc','service-layout.inc') and not path.name.endswith('interface.inc'):
            source,_=conservative_branches(source,'DT_E_'+re.sub(r'\W','_',path.name)+'_')
        path.write_text(source,encoding='utf-8')
    text,_=conservative_branches(text,'DT_E_services_')
    (stage/'image.asm').write_text(text,encoding='utf-8')
    body,_=assemble(stage,'image',0xe000,'S_END',transform=False)
    return sealed(body,4096)


def rtc_services(stage,clock_source):
    from build_edu_settings import build as edu_build
    stage.mkdir(parents=True,exist_ok=False)
    for path in clock_source.iterdir():
        if path.suffix in ('.asm','.inc'):shutil.copyfile(path,stage/path.name)
    provider,ps=assemble(stage,'rtc-provider',0x8000,'SERVICE_END')
    provider=sealed(provider,len(provider)+2)
    if len(provider)>0x900:raise ValueError('RTC provider exceeds its original allocation')
    (stage/'split-defs.inc').write_text(f'PROVIDER_SIZE EQU ${len(provider):04X}\nPROVIDER_BASE EQU $8000\nPROVIDER_BITS EQU $EE\nPRIVATE_BASE EQU $6669\nPRIVATE_SIZE EQU 57\n')
    reader,_=assemble(stage,'batch-reader',0x8900,'BR_END_CODE')
    reader=sealed(reader,256)
    gate,gs=assemble(stage,'rtc-gateway',0x6500,'GATE_END')
    if gs['GATE_END']>0x6660:raise ValueError('RTC gateway overlaps mutable state')
    gate=sealed(gate,512)
    (stage/'journal-transport.inc').write_text(f'EE_TRANSFER EQU ${ps["EE_TRANSFER"]:04X}\nTRIM_CONTROL EQU ${ps["TRIM_CONTROL"]:04X}\nBIND_FLASH_BYTE EQU $7B64\n')
    journal,_=assemble(stage,'journal',0x9000,'JOURNAL_END')
    # Native return has already been rebuilt as a source dependency of CLOCK.
    memory=cells(clock_source/'native-return.s19')
    ret=bytes(memory[a] for a in range(min(memory),max(memory)+1))
    if len(ret)>510 or len(journal)>0xa00:raise ValueError('RTC history allocation changed')
    history=sealed(journal.ljust(0xa00,b'\xff')+ret.ljust(510,b'\xff'),3072)
    loader,_=assemble(stage,'native-loader',0x7000,'NL_END')
    if len(loader)>0x290:raise ValueError('Native loader overlaps EDU helper')
    edu=stage/'EDU';edu_build(edu)
    helper=(edu/'EDU-SETTINGS-ROM.bin').read_bytes()
    helptext=(edu/'MON-SHARED-HELP.bin').read_bytes()
    image=bytearray(loader.ljust(1022,b'\xff'))
    image[0x290:0x290+len(helper)]=helper
    image[0x380:0x380+len(helptext)]=helptext
    image+=binascii.crc_hqx(image,65535).to_bytes(2,'big')
    sector=provider.ljust(0x900,b'\xff')+reader+gate+image
    if len(sector)!=4096:raise ValueError('RTC sector length changed')
    return sector,history


def transfer_services(stage,clock_source,program_provider):
    stage.mkdir(parents=True,exist_ok=False)
    for path in clock_source.iterdir():
        if path.suffix in ('.asm','.inc'):shutil.copyfile(path,stage/path.name)
    # The accepted dense-parser repair calls the frozen hexadecimal parser.
    (stage/'flash-record-number.inc').write_text('FR_WORD:\n        JSR BOOT_API_HEX_WORD\n        STX FR_PARSE_INDEX\n        RTS\n')
    shutil.copyfile(ROOT/'monitors/native/flash-auto.inc',stage/'flash-auto.inc')
    (stage/'store-provider-pin.inc').write_text(f'STORE_PROVIDER_CRC_HI EQU ${program_provider[-2]:02X}\nSTORE_PROVIDER_CRC_LO EQU ${program_provider[-1]:02X}\n')
    tail,_=assemble(stage,'auto-reload',0x6a30,'TA_END')
    if len(tail)>208:raise ValueError('AUTO reload exceeds its original allocation')
    (stage/'auto-reload-defs.inc').write_text(f'AUTO_RELOAD_BYTES EQU ${len(tail):02X}\n')
    (stage/'auto-reload-bytes.inc').write_text(''.join(' DB '+','.join(f'${v:02X}' for v in tail[i:i+16])+'\n' for i in range(0,len(tail),16)))
    record,rs=assemble(stage,'flash-record',0x6b00,'FR_END_CODE')
    gate,gs=assemble(stage,'flash-transfer-gate',0x7300,'GG_END')
    if rs['FR_END_CODE']!=0x729e or gs['GG_END']!=0x759a:
        raise ValueError('Shared transfer code no longer matches its retained boundary')
    sector=bytearray(b'\xff'*4096)
    sector[0x380:0x780]=sealed(gate,1024)
    sector[0x7c0:0xfc0]=sealed(record,2048)
    return bytes(sector)


def rebuild(out,clock_source):
    from build_mona import build as build_mon
    from build_status import build as build_status
    from build_workbench import build as build_wb
    from build_program import build as build_program
    from build_services import build as build_services
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    lock=json.loads((ROOT/'components/inputs/LOCK.json').read_text())
    expected={r['path']:r for r in lock['reconstructed_inputs'] if r['rebuild_recipe']=='tools/rebuild_mon_services.py'}
    mapping,witness={},[]
    def record(name,data):
        key='components/inputs/accepted-base1/'+name
        row=expected[key]
        digest=hashlib.sha256(data).hexdigest()
        if len(data)!=row['bytes'] or digest!=row['sha256']:
            raise ValueError('MON/service reconstruction differs from qualified bytes: '+name)
        path=out/Path(name).name;path.write_bytes(data);mapping[name]=path
        witness.append(dict(input=name,bytes=len(data),sha256=digest,file=path.relative_to(out).as_posix(),result='EXACT_MATCH'))
    mon=build_mon(out/'MON',0x10)
    for name,row in mon['artifacts'].items():
        if row['variant'] in ('A','B'):
            record('native/payload/B3-'+('A000' if row['variant']=='A' else 'B000')+'.bin',(out/'MON'/name).read_bytes())
    status=build_status(out/'STATUS')
    record('native/payload/B2-F000.bin',b'\xff'*0xa50+(out/'STATUS/STATUS-FA50.bin').read_bytes()+b'\xff'*6)
    wb=build_wb(out/'WB',0xe)
    program=build_program(out/'PROGRAM',3)
    services=build_services(out/'SERVICES',0xc,out/'WB/manifest.json',out/'MON/manifest.json',
                            program_manifest=out/'PROGRAM/manifest.json',status_manifest=out/'STATUS/manifest.json')
    bundle=bytearray((out/'SERVICES/STR8N-SERVICES-g0000000C-B2-8000.bin').read_bytes())
    bundle[0x2c00:0x3000]=(out/'STATUS/STATUS-AC00.bin').read_bytes()
    for index,address in enumerate((0x8000,0x9000,0xa000)):
        record(f'native/payload/B2-{address:04X}.bin',bytes(bundle[index*4096:(index+1)*4096]))
    record('native/payload/B3-E000.bin',dispatcher(out/'DISPATCHER',out/'SERVICES/staging/E'))
    rtc,history=rtc_services(out/'RTC',clock_source)
    record('native/payload/B3-8000.bin',rtc)
    record('native/payload/B3-9000.bin',history)
    provider=(out/'PROGRAM'/program['artifact']['filename']).read_bytes()
    record('native/payload/B1-A000.bin',transfer_services(out/'TRANSFER',clock_source,provider))
    if set(expected)!={'components/inputs/accepted-base1/'+name for name in mapping}:
        raise ValueError('Incomplete MON/service reconstruction')
    if mon['F_rebuilt'] or status['F_rebuilt'] or services['F_rebuilt'] or program['F_rebuilt']:
        raise ValueError('F must remain frozen')
    sources={}
    for folder in ('monitors/src','monitors/native','monitors/status'):
        for path in (ROOT/folder).iterdir():
            if path.suffix in ('.asm','.inc'):sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('build_mona.py','build_status.py','build_workbench.py','build_program.py','build_services.py',
                 'build_edu_settings.py','mona_branches.py','rebuild_mon_services.py'):
        path=ROOT/'tools'/name;sources['tools/'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(schema=1,inputs=witness,F_rebuilt=False,F_sha256=mon['F_sha256'],source_sha256=sources,
                 generation=dict(MON='00000010',WB='0000000E',PROGRAM='00000003',services_bundle='0000000C'),
                 mutable_RTC_metadata_included=False,board_access=False,complete_source_only_build=False)
    (out/'MON-SERVICES-RECONSTRUCTION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return mapping,receipt
