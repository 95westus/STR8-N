"""Prepare a separate B3:F journal-branch/vector-packing candidate offline.

The authoritative source, selected firmware, A/B slots, RAM worker, vector
instructions, fixed service addresses and original CRC block are preserved.
"""
import argparse,difflib,json,re,shutil,sys
from pathlib import Path
from str8build.assemble import Assembly
from str8build.formats import read_s19,save,sha
from str8build.images import boot_sector
from prepare_monitor_size import PAIR,INVERSE,flatten,offline,protected
ROOT=Path(__file__).resolve().parents[1]
BASE='efb5f2c031be32d268aefb9bc14a16d0b8f7f4bef12974293664de517ec83dad'
FILES=('str8n-v2-boot.asm','str8n-v2-journal.inc')
def read(p):return json.loads(Path(p).read_text())

def emitter(a,name):
    core=a.out/'s/core';lines=flatten(core/'str8n-v2-boot.asm')
    (core/(name+'.asm')).write_text('\n'.join(lines)+'\n')
    body,sy=a.link('core',name,0xf000,'BOOT_END');records={}
    for line in (core/(name+'.lst')).read_text().splitlines():
        m=re.match(r'^\s*(\d+) 00:([0-9A-F]{4}):',line)
        if not m:continue
        number,address=int(m[1]),0xf000+int(m[2],16)
        source=re.sub(r'^\w+:\s*','',lines[number-1].strip()).split(';',1)[0].strip()
        source=re.sub(r'^\w+\s+(?=(?:DB|DW)\b)','',source)
        if not source or source.split()[0] in ('CODE','MODULE','ENDMOD','END','EQU','XDEF'):continue
        records.setdefault(number,(address,source))
    ordered=sorted(records.values());result={}
    for i,(address,source) in enumerate(ordered):
        stop=ordered[i+1][0] if i+1<len(ordered) else 0xf000+len(body)
        if stop>address:result[address]=dict(source=source,body=body[address-0xf000:stop-0xf000])
    assert b''.join(v['body'] for v in result.values())==body
    return body,sy,result

def audit(before,after,pairs,pad):
    old,os,rows=before;new,ns,nrows=after
    removed=sorted(os[x['skip']]-3 for x in pairs);branches={os[x['skip']]-5:x for x in pairs}
    lo,hi=os['BOOT_META_READ'],os['J_CRC_INIT']
    def move(a):
        assert not any(x<=a<x+3 for x in removed),'Reference enters deleted JMP'
        if lo<=a<hi:return a-3*sum(x<a for x in removed)
        if os['BOOT_VECTOR_IMAGE']<=a<=os['BOOT_END']:
            return ns['BOOT_END'] if a==os['BOOT_END'] else ns['BOOT_VECTOR_IMAGE']+a-os['BOOT_VECTOR_IMAGE']
        return a
    for key,value in os.items():
        if key=='BOOT_END':assert ns[key]==value-196
        else:assert ns[key]==move(value),(key,hex(value),hex(ns[key]),hex(move(value)))
    sys.path.insert(0,str(ROOT/'BUILD/v1.30/local/test-deps'))
    from py65.devices.mpu65c02 import MPU
    covered=set();counts={}
    for a,row in rows.items():
        if a in removed:continue
        b=move(a);raw=row['body'];src=row['source'];op=src.split()[0].upper();expected=bytearray(raw)
        if a in branches:
            pair=branches[a];delta=ns[pair['dest']]-b-2
            assert raw[1]==3 and old[a-0xf000+2]==0x4c and -128<=delta<=127
            expected=bytes((raw[0]^0x20,delta&255))
        elif op=='DW':expected=b''.join(move(int.from_bytes(raw[i:i+2],'little')).to_bytes(2,'little') for i in range(0,len(raw),2))
        elif op!='DB':
            mnemonic,mode=MPU.disassemble[raw[0]];assert mnemonic==op,(src,mnemonic)
            if mode=='rel':
                dest=a+2+int.from_bytes(raw[1:2],'little',signed=True);delta=move(dest)-b-2
                assert -128<=delta<=127;expected[1]=delta&255
            elif len(raw)==3:
                assert mode in ('abs','abx','aby','ind','iax');expected[1:]=move(int.from_bytes(raw[1:],'little')).to_bytes(2,'little')
            elif mode=='imm':
                m=re.search(r'#([<>])(\w+)$',src)
                if m:expected[1]=(ns[m[2]] if m[1]=='<' else ns[m[2]]>>8)&255
        assert nrows[b]['body']==bytes(expected),(hex(a),src,bytes(expected).hex(),nrows[b]['body'].hex())
        covered.update(range(b,b+len(expected)));counts[op]=counts.get(op,0)+1
    padding=set(range(ns['F_SIZE_PADDING'],ns['J_CRC_INIT']))
    assert len(padding)==pad and all(new[a-0xf000]==255 for a in padding)
    assert covered|padding==set(range(0xf000,ns['BOOT_END'])) and not covered&padding
    # Timing-sensitive reset/poll/console loops stay in place; only the vector
    # copy's source operand changes. Its new page crossing is checked separately.
    assert old[:0x688][:0x10e]==new[:0x688][:0x10e]
    assert old[0x111:0x688]==new[0x111:0x688]
    return dict(passed=True,all_emitted_bytes_and_symbols_checked=True,branches=len(pairs),vector_bytes=196,padding_bytes=pad,emitter_kinds=counts)

def prepare(control,out):
    control,out=control.resolve(),out.resolve();assert not out.exists() and len(str(out))<65
    snapshot=protected();report=read(control/'build-report.json');assert report['passed']
    current={p.relative_to(ROOT/'src/current').as_posix():sha(p.read_bytes()) for p in (ROOT/'src/current').rglob('*') if p.is_file()}
    assert report['source_files']==current and sha((control/'firmware.bin').read_bytes())==BASE
    shutil.copytree(control,out);a=object.__new__(Assembly)
    a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    core=out/'s/core';original={n:(core/n).read_text() for n in FILES}
    oldsy=read(control/'symbols.json')['core/str8n-v2-boot'];sy=oldsy;allpairs=[]
    journal=original[FILES[1]];crc=journal.index('J_CRC_INIT:')
    work=journal[:crc];suffix=journal[crc:]
    boot=original[FILES[0]].replace('BOOT_VECTOR_IMAGE:      INCLUDE "vectors-image.inc"\n','')
    assert boot!=original[FILES[0]]
    (core/FILES[0]).write_text(boot)
    for roundno in range(12):
        chosen=[]
        def shorten(m):
            if m['skip']!=m['label'] or m['skip'] not in sy or m['dest'] not in sy:return m[0]
            pc=sy[m['skip']]-5;target=sy[m['dest']]
            delta=target-pc-2-(3 if pc<target<oldsy['J_CRC_INIT'] else 0)
            if not -128<=delta<=127:return m[0]
            chosen.append(dict(skip=m['skip'],dest=m['dest'],original=m['br'],replacement=INVERSE[m['br']],round=roundno))
            return m['indent']+INVERSE[m['br']]+' '+m['dest']+'\n'+m['label']+':'
        work=PAIR.sub(shorten,work)
        if not chosen:break
        allpairs+=chosen;pad=3*len(allpairs)-196;assert pad>=0
        middle='BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"\nF_SIZE_PADDING:\n'
        if pad:middle+=' DB '+','.join('$FF' for _ in range(pad))+'\n'
        (core/FILES[1]).write_text(work+middle+suffix)
        body,sy=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
        assert sy['J_CRC_INIT']==oldsy['J_CRC_INIT'] and sy['J_CRC_BYTE']==oldsy['J_CRC_BYTE']
    else:raise AssertionError('Shortening did not converge')
    assert len(allpairs)==69 and pad==11
    vs=read(control/'symbols.json')['core/str8n-v2-vectors']
    fixed=boot_sector(body,sy,vs,read(ROOT/'src/current/layout.json')['boot_compatibility'])
    oldfixed=(control/'firmware.bin').read_bytes()[-4096:]
    assert fixed[0xab4:0xae7]==oldfixed[0xab4:0xae7],'CRC bytes/addresses must not change'
    assert fixed[0xae7:0xb5c]==oldfixed[0xae7:0xb5c],'Wear report bytes must not change'
    assert fixed[0xb93:0xf14]==oldfixed[0xb93:0xf14],'Worker bytes must not change'
    assert fixed[0xfe0:]==oldfixed[0xfe0:] and fixed[0x684:0x688]==oldfixed[0x684:0x688]
    assert fixed[sy['BOOT_VECTOR_IMAGE']-0xf000:sy['BOOT_VECTOR_IMAGE']-0xf000+196]==oldfixed[0xf14:0xfd8]
    for key in ('BOOT_SLOT_CHECK','BOOT_COMPAT_DATA','BOOT_META_READ','BOOT_META_CFG','BOOT_META_ERASE','BOOT_META_PROMOTE','BOOT_REPORT','BOOT_UPDATE_WRITE','BOOT_WORKER_IMAGE'):
        assert sy[key]==oldsy[key],key
    a.emit('str8n-v2-recovery-f000-ffff.bin',fixed)
    image=(control/'firmware.bin').read_bytes()[:-4096]+fixed;(out/'firmware.bin').write_bytes(image)
    symbols=read(control/'symbols.json');symbols['core/str8n-v2-boot']=sy;save(out/'symbols.json',symbols)
    # Two independent flattened links check every emitted byte and relocation.
    proof=out/'proof-control';shutil.copytree(control/'s',proof/'s')
    olda=object.__new__(Assembly);olda.out=proof;olda.assembler=a.assembler;olda.linker=a.linker;olda.symbols={};olda.compiled=[]
    before=emitter(olda,'f-size-proof');after=emitter(a,'f-size-proof')
    assert before[0]==bytes(read_s19(control/'s/core/str8n-v2-boot.s19').values()) and after[0]==body
    evidence=audit(before,after,allpairs,pad)
    patch=''.join(''.join(difflib.unified_diff(original[n].splitlines(True),(core/n).read_text().splitlines(True),fromfile='src/current/core/'+n,tofile='src/current/core/'+n)) for n in FILES)
    (out/'source.patch').write_text(patch)
    changed=[p.relative_to(out/'payload').as_posix() for p in (out/'payload').rglob('*') if p.is_file() and p.read_bytes()!=(control/'payload'/p.relative_to(out/'payload')).read_bytes()]
    assert changed==['str8n-v2-recovery-f000-ffff.bin'] and image[:-4096]==(control/'firmware.bin').read_bytes()[:-4096]
    assert protected()==snapshot
    result=dict(passed=True,board_access=False,installation_permitted=False,candidate='fixed-f-journal-size',baseline_sha256=BASE,firmware_sha256=sha(image),fixed_F_sha256=sha(fixed),journal_branches=len(allpairs),instruction_bytes_saved=207,contiguous_free_bytes=0xffe0-sy['BOOT_END'],interior_free_bytes=pad,previous_contiguous_free_bytes=8,body_bytes=len(body),vector_ROM_address=sy['BOOT_VECTOR_IMAGE'],A_B_unchanged=True,CRC_bytes_and_entry_addresses_unchanged=True,worker_and_initialized_vectors_unchanged=True,changed_payloads=changed,pairs=allpairs,emission_audit=evidence,source_files=current,protected_snapshot=snapshot,tool_sha256=sha(Path(__file__).read_bytes()))
    save(out/'f-size-build.json',result)
    shutil.copyfile(out/'build-report.json',out/'baseline-build-report.json')
    save(out/'build-report.json',dict(passed=True,candidate_id=result['candidate'],candidate_only=True,
        board_access=False,installation_permitted=False,firmware_sha256=sha(image),
        baseline_sha256=BASE,selected_current_firmware_unchanged=True,
        artifacts={p.relative_to(out/'payload').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted((out/'payload').rglob('*')) if p.is_file()},
        source_files=current,derived_source_patch_sha256=sha((out/'source.patch').read_bytes()),qualification='See f-size-build.json and separate CPU test report; baseline manifests are not rewritten.'))
    print('PASS separate F size candidate; 69 pairs, 204 contiguous + 11 interior free bytes; A/B and CRC unchanged',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    offline();prepare(args.control,args.out)
