"""Preserve STATUS in FLASH padding; share dense control code and repair AUTO."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,sha
from build import db
from mona_branches import conservative_branches
from status_extents import assert_preserved


def build(out,scope,reuse=None):
    out,scope=Path(out).resolve(),Path(scope).resolve()
    assert not out.exists();out.mkdir(parents=True)
    prior=ROOT.parents[1]/'BUILD/flash-transfer-g1-r5'
    support=ROOT.parents[1]/'BUILD/native-apps-g1-maint-r1'
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert all(sha((ROOT/n).read_bytes())==v for n,v in freeze['sources'].items())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    for p in prior.glob('*.inc'):shutil.copyfile(p,out/p.name)
    sources={};logs=[];reused=[]
    def src(name):
        p=ROOT/'monitors/native'/name;sources[p.relative_to(ROOT).as_posix()]=sha(p.read_bytes());return p.read_text()
    def assemble(stem,text,origin,last):
        text,_=conservative_branches(text,'FC_'+stem.replace('-','_')+'_')
        (out/(stem+'.asm')).write_text(text)
        def same(name,seen=None):
            seen=set() if seen is None else seen
            if name in seen:return True
            seen.add(name);old=Path(reuse)/name;new=out/name
            return old.exists() and new.read_bytes()==old.read_bytes() and all(same(n,seen) for n in re.findall(r'INCLUDE\s+"([^"]+)"',new.read_text()))
        can_reuse=bool(reuse and (Path(reuse)/(stem+'.map')).exists() and same(stem+'.asm'))
        if can_reuse:
            for suffix in ('.map','.s19'):shutil.copyfile(Path(reuse)/(stem+suffix),out/(stem+suffix))
            reused.append(stem)
        commands=[] if can_reuse else ([shutil.which('wdc02as'),'-G','-L','-S','-W',stem+'.asm'],
                    [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o',stem+'.s19',stem+'.obj'])
        for cmd in commands:
            r=subprocess.run(cmd,cwd=out,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if r.returncode:raise RuntimeError('Build failed; inspect build-log.json')
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(out/(stem+'.map')).read_text(),re.M)}
        memory=cells(out/(stem+'.s19'));return bytearray(memory[a] for a in range(origin,sy[last])),sy
    def seal(raw,n):
        assert len(raw)<=n-2,(len(raw),n);data=bytes(raw).ljust(n-2,b'\xff');return data+binascii.crc_hqx(data,65535).to_bytes(2,'big')
    provider=(ROOT.parents[1]/'BUILD/program-sp1-g3-store-r2/STR8N-PROGRAM-SP1-6B00.bin').read_bytes()
    (out/'store-provider-pin.inc').write_text(f'STORE_PROVIDER_CRC_HI EQU ${provider[-2]:02X}\nSTORE_PROVIDER_CRC_LO EQU ${provider[-1]:02X}\n')
    tail,ts=assemble('auto-reload',src('auto-reload.asm'),0x6A30,'TA_END')
    assert len(tail)<=208
    (out/'auto-reload-defs.inc').write_text(f'AUTO_RELOAD_BYTES EQU ${len(tail):02X}\n')
    db(out/'auto-reload-bytes.inc',tail)
    gate,gs=assemble('flash-transfer-gate',src('flash-transfer-gate.asm'),0x7300,'GG_END')
    # The frozen text parser reads7C00. Reuse it rather than duplicate hex code.
    (out/'flash-record-number.inc').write_text('FR_WORD:\n        JSR BOOT_API_HEX_WORD\n        STX FR_PARSE_INDEX\n        RTS\n')
    record,rs=assemble('flash-record',src('flash-record.asm'),0x6B00,'FR_END_CODE')
    assert len(gate)<=1022 and len(record)<=2046

    dense=src('flash-s19.inc')
    state=dense[:dense.index('FI_COMMAND:')]
    (out/'flash-s19-state.inc').write_text(state)
    core=src('board-tool.asm')
    core=core.replace('        CODE\n','        INCLUDE "flash-s19-state.inc"\n        CODE\n',1)
    core=core.replace('        JMP CONFIG_START\n','        JSR FI_LIB_LOAD\n        BCC FT_BAD\n        JMP CONFIG_START\n',1)
    a=core.index('        LDX #<FI_WORD');b=core.index('        LDX #<FT_HELP_WORD',a)
    core=core[:a]+'''        LDA V2_LINE
        CMP #'I'
        BNE FC_NOT_I
        LDA FI_LIB_OK
        BEQ FT_BAD
        LDX #1
        JMP $4008
FC_NOT_I:
'''+core[b:]
    core=core.replace('        LDX #<FI_HELP_TEXT\n        LDY #>FI_HELP_TEXT\n        JSR CONFIG_PRINT\n','')
    a=core.index('FT_HELP_TEXT:');b=core.index('FT_VALID:',a)
    core=core[:a]+'''FT_HELP_TEXT:
        DB "BANK READ VIEW EDIT WRITE BYTE ERASE",13,10
        DB "I first last (S19)",13,10
        DB "BOOT B/C/OFF/RUN/DELAY; B/C/W/?",13,10
        DB "HOST; VERSION; Q; B3:C/D/F protected",13,10,0
'''+core[b:]
    replacements={
      'REFUSED: syntax/range/protected/stale; ? help':'REFUSED',
      'Canceled; flash unchanged.':'Canceled',
      'STR8-N FLASH/MAINT g00000001; N-F 0.3.0 BASE1/PR05':'FLASH g2 / N-F0.3.0 BASE1/PR05',
      'EDU profile: Rev D; revision/presence not electrically identified.':'EDU Rev D profile',
      'SXB: W65C02SXB / 65C02':'W65C02SXB / 65C02',
      'SXB: W65C816SXB / emulation':'W65C816SXB / emulation',
      'offset 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F':'offset 00..0F (16 bytes)'}
    for old,new in replacements.items():assert old in core;core=core.replace(old,new)
    core=core.replace('        INCLUDE "flash-s19.inc"','        INCLUDE "flash-s19-parser.inc"\n        INCLUDE "flash-s19-load.inc"')
    (out/'flash-s19-load.inc').write_text(src('flash-s19-load.inc'))
    board,bs=assemble('board-tool',core,0x2000,'BOARD_END')
    assert len(board)<=0x1A30,f'FLASH overlaps protected STATUS: {len(board)} >6704'
    bindings={k:v for k,v in bs.items() if k.startswith('FT_') or k in ('CONFIG_PRINT','JE_ENTER','SL_RECORD_READ','SL_DRAIN')}
    (out/'dense-core.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
    control=dense[dense.index('FI_COMMAND:'):dense.index('        INCLUDE "flash-s19-parser.inc"')]
    control=re.sub(r'^FI_HELP_TEXT:.*\n','',control,flags=re.M)
    library_text='''        MODULE DENSE_CONTROL
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "batch-interface.inc"
        INCLUDE "flash-s19-state.inc"
        INCLUDE "dense-core.inc"
        CODE
FI_LIBRARY: DB "FI",1,0,"PR05"
        JMP FI_COMMAND
'''+control+'\nFI_CONTROL_END:\n        ENDMOD\n        END\n'
    library,ls=assemble('dense-control',library_text,0x4000,'FI_CONTROL_END')
    library=bytes(library)+binascii.crc_hqx(library,65535).to_bytes(2,'big')
    maint=bytearray((support/'BANK-MAINT-g00000001-flash.bin').read_bytes())
    assert len(maint)==12288
    body_end=32+int.from_bytes(maint[8:10],'little')
    holes=((body_end,0x2380),(0x2380+len(gate),0x277E),(0x27C0+len(record),0x2FBE))
    assert all(a<b for a,b in holes)
    assert sum(b-a for a,b in holes)>=len(library),(len(library),holes)
    maint[0x2380:0x2780]=seal(gate,1024)
    maint[0x27C0:0x2FC0]=seal(record,2048)
    fragments=[];remaining=library;offset=0
    for start,end in holes:
        size=min(len(remaining),end-start);assert size>0
        assert maint[start:start+size]==b'\xff'*size
        maint[start:start+size]=remaining[:size];remaining=remaining[size:]
        fragments.append(dict(source=f'{start+0x8000:04X}',length=size,library_offset=offset));offset+=size
    assert not remaining
    # Fragment bytes are also covered by their containing gate/record seals.
    for start,length in ((0x2380,1024),(0x27C0,2048)):
        end=start+length;maint[end-2:end]=binascii.crc_hqx(maint[start:end-2],65535).to_bytes(2,'big')
    maint[-2:]=binascii.crc_hqx(maint[:-2],65535).to_bytes(2,'big')
    patch=bs['FI_FRAGMENTS']-0x2000;assert board[patch:patch+12]==bytes(12)
    table=b''.join(int(f['source'],16).to_bytes(2,'little')+f['length'].to_bytes(2,'little') for f in fragments)
    board[patch:patch+12]=table
    original2=(scope/'B2-original.bin').read_bytes()
    flash=bytearray(original2[0x6000:0x8000])
    h=bytearray(flash[:32]);h[8:10]=len(board).to_bytes(2,'little');h[14:18]=(2).to_bytes(4,'little')
    flash[:32]=h;flash[32:32+len(board)]=board
    # Padding may be STATUS code, never an FF-filled image budget.
    assert flash[0x1A50:0x1FFA]==original2[0x7A50:0x7FFA]
    flash[-2:]=binascii.crc_hqx(flash[:-2],65535).to_bytes(2,'big')
    new2=bytearray(original2);new2[0x6000:]=flash;assert_preserved(original2,bytes(new2))
    out_files={'FLASH-RAM.bin':bytes(board),'DENSE-CONTROL-4000.bin':library,'BANK-MAINT-corrected.bin':bytes(maint),
      'FLASH-corrected.bin':bytes(flash),'FLASH-RECORD-6B00.bin':bytes(maint[0x27C0:0x2FC0]),
      'FLASH-TRANSFER-GATE-7300.bin':bytes(maint[0x2380:0x2780])}
    artifacts={}
    for name,data in out_files.items():(out/name).write_bytes(data);artifacts[name]=dict(bytes=len(data),sha256=sha(data))
    assert all(binascii.crc_hqx(v,65535)==0 for k,v in out_files.items() if k!='FLASH-RAM.bin')
    report=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],CPU_simulations=0,
      source_sha256=sources,artifacts=artifacts,FLASH_linked_bytes=len(board),FLASH_STATUS_boundary='FA50',
      STATUS_details_exact=True,STATUS_details_SHA256=sha(original2[0x7A50:0x7FFA]),
      fragments=fragments,fragment_table_RAM=f'{bs["FI_FRAGMENTS"]:04X}',dense_library_bytes=len(library),
      gate_linked_bytes=len(gate),record_linked_bytes=len(record),auto_tail_bytes=len(tail),
      ROM_targets=['B1:A','B2:E','B2:F'],CORE_body_limit=6704,MACRO_build_passes=1,reused_modules=reused)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('FLASH_linked_bytes','dense_library_bytes','gate_linked_bytes','record_linked_bytes','fragments')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--scope',required=True);p.add_argument('--reuse')
    a=p.parse_args();build(a.out,a.scope,a.reuse)
