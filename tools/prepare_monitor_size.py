"""Build an offline monitor-size candidate from the unchanged current baseline.

Only inverted-branch/JMP pairs become direct branches. Derived source and a
reviewable patch live in the candidate; src/current and installer profiles stay
unchanged. The batch provider's private reader binding is relinked explicitly.
"""
import argparse
import difflib
import importlib.abc
import json
from pathlib import Path
import re
import shutil
import socket
import sys

from str8build.assemble import Assembly
from str8build.formats import read_s19, save, sealed, sha
from str8build.images import monitor_slot

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6'
FILES=['monitor-b0.asm','str8n-v2-monitor.inc','str8n-v2-load.inc','str8n-v2-flash.inc','str8n-v2-config.inc']
INVERSE=dict(BCC='BCS',BCS='BCC',BEQ='BNE',BNE='BEQ',BMI='BPL',BPL='BMI',BVC='BVS',BVS='BVC')
PAIR=re.compile(r'(?m)^(?P<indent>[ \t]*)(?P<br>B(?:CC|CS|EQ|NE|MI|PL|VC|VS))\s+(?P<skip>\w+)\s*\n[ \t]*JMP\s+(?P<dest>\w+)\s*\n(?P<label>\w+):')
ATTEMPTS=[]
class NoDevices(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in ('serial','requests','httpx'):
            ATTEMPTS.append(fullname);raise AssertionError('Offline candidate cannot import device/network adapters')
def offline():
    sys.meta_path.insert(0,NoDevices())
    def refused(*a,**kw):ATTEMPTS.append('network');raise AssertionError('Offline candidate cannot use a network')
    socket.create_connection=socket.socket.connect=socket.socket.connect_ex=refused
def read(p):return json.loads(Path(p).read_text())
def protected():
    paths=[p for folder in ('src/current','tools/installer','tests/baselines') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT/f'output/qualification/device-operations/{b}.json' for b in ('2604','2609')]
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}
def excluded(name,text,offset):
    if name=='monitor-b0.asm':return offset<text.index('V2_COMMAND_W:')
    if name=='str8n-v2-monitor.inc':return text.index('V2_COMMAND_G:')<=offset<text.index('V2_COMMAND_D:')
    if name=='str8n-v2-load.inc':return text.index('V2_LOAD_DRAIN:')<=offset<text.index('V2_RECORD_END:')
    if name=='str8n-v2-config.inc':return offset>=text.index('V2_AUTO_HEADLESS:')
    return False
def flatten(path):
    lines=[]
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'\s*(?:\w+:\s*)?INCLUDE\s+"([^"]+)"\s*(?:;.*)?',line,re.I)
        if m:
            label=line[:line.upper().index('INCLUDE')].strip()
            if label:lines.append(label)
            lines.extend(flatten((path.parent/m[1]).resolve()))
        else:lines.append(line)
    return lines
def emitter_index(assembly,name,origin):
    core=assembly.out/'s/core';lines=flatten(core/(name+'.asm'))
    flat=name+'-proof';(core/(flat+'.asm')).write_text('\n'.join(lines)+'\n')
    body,symbols=assembly.link('core',flat,origin,'V2_END')
    records={}
    for line in (core/(flat+'.lst')).read_text().splitlines():
        m=re.match(r'^\s*(\d+) 00:([0-9A-F]{4}):',line)
        if not m:continue
        number,address=int(m[1]),origin+int(m[2],16)
        source=lines[number-1].strip()
        source=re.sub(r'^\w+:\s*','',source).split(';',1)[0].strip()
        source=re.sub(r'^\w+\s+(?=(?:DB|DW)\b)','',source)
        if not source:continue
        op=source.split()[0].upper()
        if op in ('CODE','MODULE','ENDMOD','END','EQU','XDEF'):continue
        # Continuation rows share their source line; keep its first address.
        if number not in records:records[number]=(address,source)
    ordered=sorted(records.values())
    result={}
    for i,(address,source) in enumerate(ordered):
        stop=ordered[i+1][0] if i+1<len(ordered) else origin+len(body)
        if stop>address:result[address]=dict(source=source,body=body[address-origin:stop-origin])
    assert b''.join(v['body'] for v in result.values())==body,'Flat emitter index must cover every byte'
    return body,symbols,result
def equivalence(old,new,origin,pairs):
    old_body,old_sy,old_rows=old;new_body,new_sy,new_rows=new
    removed=sorted(old_sy[p['skip']]-3 for p in pairs)
    branches={old_sy[p['skip']]-5:p for p in pairs}
    def relocate(a):
        assert not any(x<=a<x+3 for x in removed),'Reference enters a removed JMP'
        return a-3*sum(x<a for x in removed) if origin<=a<=origin+len(old_body) else a
    assert len(new_body)==len(old_body)-3*len(pairs)
    assert all(new_sy[k]==relocate(v) for k,v in old_sy.items()),'All symbols must follow the deletion-only map'
    sys.path.insert(0,str(ROOT/'BUILD/v1.30/local/test-deps'))
    from py65.devices.mpu65c02 import MPU
    modes=MPU.disassemble
    covered=set();counts={}
    for a,row in old_rows.items():
        if a in removed:continue
        b=relocate(a);actual=new_rows[b]['body'];raw=row['body'];source=row['source'];op=source.split()[0].upper()
        expected=bytearray(raw)
        if a in branches:
            p=branches[a];assert len(raw)==2 and old_body[a-origin+2]==0x4c
            assert raw[1]==3
            dest=relocate(old_sy[p['dest']]);delta=dest-b-2;assert -128<=delta<=127
            expected=bytes([raw[0]^0x20,delta&255]);assert INVERSE[op]==p['replacement']
        elif op=='DW':
            assert len(raw)%2==0
            expected=b''.join(relocate(int.from_bytes(raw[i:i+2],'little')).to_bytes(2,'little') for i in range(0,len(raw),2))
        elif op=='DB':pass
        else:
            mnemonic,mode=modes[raw[0]];assert mnemonic==op,(source,mnemonic)
            if mode=='rel':
                target=a+2+int.from_bytes(raw[1:2],'little',signed=True);d=relocate(target)-b-2
                assert -128<=d<=127;expected[1]=d&255
            elif len(raw)==3:
                assert mode in ('abs','abx','aby','ind','iax'),(source,mode)
                expected[1:3]=relocate(int.from_bytes(raw[1:3],'little')).to_bytes(2,'little')
            elif mode=='imm':
                m=re.search(r'#([<>])(\w+)$',source)
                if m:
                    value=new_sy[m[2]];expected[1]=(value if m[1]=='<' else value>>8)&255
        assert bytes(expected)==actual,(hex(a),source,bytes(expected).hex(),actual.hex())
        covered.update(range(b,b+len(actual)));counts[op]=counts.get(op,0)+1
    assert covered==set(range(origin,origin+len(new_body)))
    # Only the untouched timing-sensitive loop bodies require cycle equivalence.
    timing=[]
    for first,last in [('V2_LOAD_DRAIN','V2_RECORD_END'),('V2_AUTO_HEADLESS','V2_AUTO_NO_KEY'),('V2_READ_LINE','V2_PRINT')]:
        for a,row in old_rows.items():
            if not old_sy[first]<=a<old_sy[last]:continue
            raw=row['body'];op=row['source'].split()[0].upper()
            if op not in INVERSE and op!='BRA':continue
            assert a not in branches,'Timing region cannot be shortened'
            b=relocate(a);newraw=new_rows[b]['body']
            olddest=a+2+int.from_bytes(raw[1:2],'little',signed=True)
            newdest=b+2+int.from_bytes(newraw[1:2],'little',signed=True)
            assert ((a+2)>>8!=olddest>>8)==((b+2)>>8!=newdest>>8),('Timing page crossing changed',hex(a),first)
            timing.append(a)
    return dict(passed=True,all_emitted_bytes_verified=True,deletion_only_symbol_map=True,shortened_pairs=len(pairs),bytes_saved=len(old_body)-len(new_body),emitter_kinds=counts,timing_branches_checked=len(timing))
def prepare(control,out):
    control,out=control.resolve(),out.resolve();assert not out.exists() and len(str(out))<65
    snapshot=protected();report=read(control/'build-report.json');assert report['passed']
    assert sha((control/'firmware.bin').read_bytes())==BASE_SHA
    current={p.relative_to(ROOT/'src/current').as_posix():sha(p.read_bytes()) for p in (ROOT/'src/current').rglob('*') if p.is_file()}
    assert current==report['source_files'],'Control must be a fresh build of current source'
    shutil.copytree(control,out)
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols=read(out/'symbols.json');a.compiled=[];a.sources=current
    assert a.assembler and a.linker
    core=out/'s/core';original={name:(core/name).read_text() for name in FILES};pairs=[]
    base_sy=read(control/'symbols.json')['core/monitor-b0']
    sy=base_sy
    # Reevaluate reach after each deletion pass; shrinking can make more pairs fit.
    for roundno in range(12):
        selected=[]
        for name in FILES:
            text=(core/name).read_text()
            def shorten(m):
                if m['skip']!=m['label'] or excluded(name,text,m.start()):return m[0]
                if m['skip'] not in sy or m['dest'] not in sy:return m[0]
                pc=sy[m['skip']]-5;target=sy[m['dest']]
                delta=target-(pc+2)-(3 if target>=pc+5 else 0)
                if not -128<=delta<=127:return m[0]
                selected.append(dict(file=name,skip=m['skip'],dest=m['dest'],original=m['br'],replacement=INVERSE[m['br']],round=roundno))
                return m['indent']+INVERSE[m['br']]+' '+m['dest']+'\n'+m['label']+':'
            changed=PAIR.sub(shorten,text);(core/name).write_text(changed)
        if not selected:break
        pairs.extend(selected)
        body,sy=a.link('core','monitor-b0',0xb080,'V2_END')
    else:raise AssertionError('Branch shortening did not converge')
    assert pairs
    text=(core/'monitor-b0.asm').read_text();(core/'monitor-a0.asm').write_text(text.replace('V2_IMAGE_PAGE EQU $B0','V2_IMAGE_PAGE EQU $A0',1))
    body_b,sy_b=a.link('core','monitor-b0',0xb080,'V2_END');body_a,sy_a=a.link('core','monitor-a0',0xa080,'V2_END')
    layout=read(ROOT/'src/current/layout.json')
    for page,body,symbols in [(0xb0,body_b,sy_b),(0xa0,body_a,sy_a)]:
        a.emit(f'str8n-v2-recovery-slot-{page:02x}.bin',monitor_slot(body,symbols,page,layout['generation'],layout['boot_compatibility']))
    # Private batch reader binding: both its low byte and selected-slot page delta.
    dispatch=out/'s/xip/dispatch.inc';old_dispatch=dispatch.read_text();new_dispatch=old_dispatch.replace('B29_MON_DELTA EQU $0C',f'B29_MON_DELTA EQU ${(sy_a["V2_BANK_READ_LINE"]>>8)-0xa0:02X}').replace('B29_READERS DW $ACF0,',f'B29_READERS DW ${sy_a["V2_BANK_READ_LINE"]:04X},')
    assert new_dispatch!=old_dispatch;dispatch.write_text(new_dispatch)
    utilities,_=a.link('xip','utilities',0x8000,'X28_END');utilities=sealed(utilities,0x5800)
    old_util=(control/'payload/xip/utilities.bin').read_bytes();table=a.symbols['xip/utilities']['B29_READERS']-0x8000
    signature=bytes.fromhex('AD307D18690C8DEB7E');assert old_util.count(signature)==1;immediate=old_util.index(signature)+5
    allowed={table,table+1,immediate,0x57fe,0x57ff}
    util_diffs=[i for i,(x,y) in enumerate(zip(old_util,utilities)) if x!=y]
    assert set(util_diffs)<=allowed,'Only reader binding and CRC may change in utilities'
    a.emit('xip/utilities.bin',utilities)
    # DBG1's shared D/M commands also use private, slot-relative monitor entries.
    generated=out/'debugger/generated.inc';old_generated=generated.read_text();new_generated=old_generated
    for key,target in [('MON_D','V2_COMMAND_D'),('MON_M','V2_M_EDIT')]:
        new_generated,n=re.subn(r'(?m)^'+key+r' EQU \$[0-9A-F]+$',f'{key} EQU ${sy_a[target]-0xa000:04X}',new_generated)
        assert n==1
        assert sy_b[target]-0xb000==sy_a[target]-0xa000
    generated.write_text(new_generated)
    debugger,debug_sy=a.link('debugger','debugger',0xa000,'DEBUG_END');debugger=sealed(debugger,4096)
    old_debug=(control/'debugger/debugger-a000.bin').read_bytes();debug_allowed={4094,4095}
    debug_sites=[]
    for line in (control/'debugger/debugger.lst').read_text().splitlines():
        m=re.match(r'^\s*\d+ 00:([0-9A-F]{4}):.*\bLDA #([<>])MON_([DM])\s*$',line)
        if not m:continue
        offset=int(m[1],16)+1;debug_allowed.add(offset);debug_sites.append(offset)
        value=debug_sy['MON_'+m[3]];assert debugger[offset]==((value if m[2]=='<' else value>>8)&255)
    assert len(debug_sites)==4
    debug_diffs=[i for i,(x,y) in enumerate(zip(old_debug,debugger)) if x!=y]
    assert set(debug_diffs)<=debug_allowed,'Only DBG monitor D/M bindings and sector CRC may change'
    old_debug_meta=read(control/'debugger-build.json')
    assert {k for k,v in debug_sy.items() if old_debug_meta['debugger_symbols'].get(k)!=v}=={'MON_D','MON_M'}
    (out/'debugger/debugger-a000.bin').write_bytes(debugger)
    image=bytearray((control/'firmware.bin').read_bytes())
    image[0x2000:0x3000]=debugger
    image[0x8000:0xd800]=utilities
    image[0x12000:0x13000]=(out/'payload/str8n-v2-recovery-slot-a0.bin').read_bytes()
    image[0x13000:0x14000]=(out/'payload/str8n-v2-recovery-slot-b0.bin').read_bytes()
    (out/'firmware.bin').write_bytes(image)
    save(out/'debugger-build.json',dict(old_debug_meta,debugger_symbols=debug_sy,firmware_sha256=sha(image)))
    assert bytes(image[0x17000:])==(control/'firmware.bin').read_bytes()[0x17000:]
    # Independently relink flattened assembly for an exhaustive byte/operand audit.
    proofs={}
    proof_control=out/'proof-control';shutil.copytree(control/'s',proof_control/'s')
    for page in (0xb0,0xa0):
        name=f'monitor-{page:02x}';origin=(page<<8)+128
        old_a=object.__new__(Assembly);old_a.out=proof_control;old_a.assembler=a.assembler;old_a.linker=a.linker;old_a.symbols={};old_a.compiled=[]
        before=emitter_index(old_a,name,origin);after=emitter_index(a,name,origin)
        assert before[0]==bytes(read_s19(control/'s/core'/(name+'.s19')).values())
        assert after[0]==(body_b if page==0xb0 else body_a)
        proofs[name]=equivalence(before,after,origin,pairs)
    symbols=read(control/'symbols.json');symbols.update({'core/monitor-b0':sy_b,'core/monitor-a0':sy_a})
    assert {k for k,v in a.symbols['xip/utilities'].items() if symbols['xip/utilities'].get(k)!=v}=={'B29_MON_DELTA'},'Only the reader page-delta constant may change'
    symbols['xip/utilities']=a.symbols['xip/utilities']
    save(out/'symbols.json',symbols)
    patch=''.join(''.join(difflib.unified_diff(original[n].splitlines(True),(core/n).read_text().splitlines(True),fromfile='src/current/core/'+n,tofile='src/current/core/'+n)) for n in FILES)
    patch+=''.join(difflib.unified_diff(old_dispatch.splitlines(True),new_dispatch.splitlines(True),fromfile='src/current/xip/dispatch.inc',tofile='src/current/xip/dispatch.inc'))
    patch+=''.join(difflib.unified_diff(old_generated.splitlines(True),new_generated.splitlines(True),fromfile='src/current/debugger/generated.inc',tofile='src/current/debugger/generated.inc'))
    (out/'source.patch').write_text(patch)
    artifact_names={p.relative_to(out/'payload').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in (out/'payload').rglob('*') if p.is_file()}
    changed=[n for n,row in artifact_names.items() if row!=report['artifacts'][n]]
    assert set(changed)=={'str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin','xip/utilities.bin'}
    assert snapshot==protected() and not ATTEMPTS
    result=dict(passed=True,board_access=False,installation_permitted=False,candidate='monitor-size-branches',control=str(control),baseline_sha256=BASE_SHA,
        firmware_sha256=sha(image),shortened_pairs_per_slot=len(pairs),bytes_saved_per_slot=3967-len(body_b),monitor_body_bytes=len(body_b),free_bytes_per_slot=3968-len(body_b),
        instruction_equivalence=proofs,patch_sha256=sha((out/'source.patch').read_bytes()),pairs=pairs,changed_payloads=changed,artifacts=artifact_names,
        batch_reader=dict(old='ACF0/BCF0',new_A=f'{sy_a["V2_BANK_READ_LINE"]:04X}',new_B=f'{sy_b["V2_BANK_READ_LINE"]:04X}',utility_changed_offsets=util_diffs),
        debugger_binding=dict(D=f'{debug_sy["MON_D"]:04X}',M=f'{debug_sy["MON_M"]:04X}',changed_offsets=debug_diffs),
        fixed_F_unchanged=True,RAM_worker_vectors_unchanged=True,current_sources_and_board_markers_unchanged=True,network_serial_attempts=ATTEMPTS,tool_sha256=sha(Path(__file__).read_bytes()))
    save(out/'monitor-size-build.json',result)
    # This is a candidate report, never a claim to match the installed baseline.
    save(out/'build-report.json',dict(result,compiled=a.compiled,source_files=current,firmware_matches=False,baseline_report_retained=str(control/'build-report.json')))
    print(json.dumps({k:result[k] for k in ('passed','shortened_pairs_per_slot','bytes_saved_per_slot','monitor_body_bytes','free_bytes_per_slot','firmware_sha256')},indent=2))
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();offline();prepare(args.control,args.out)
if __name__=='__main__':main()
