"""Separate F branch/failure-path candidate; selected source and devices untouched."""
import argparse,ast,difflib,re,shutil
from dataclasses import dataclass
from pathlib import Path
from prepare_f_size import read,emitter,offline,protected
from prepare_monitor_size import INVERSE,flatten
from str8build.assemble import Assembly
from str8build.formats import sha,save,read_s19
from str8build.images import boot_sector
ROOT=Path(__file__).resolve().parents[1]
BASE='7fcec7cdbf8a9c9aed0766894d0d63a396c48d38e2da7cf90f894a565f2485f1'
FILES=('str8n-v2-boot.asm','str8n-v2-journal.inc')
ANCHORS=('BOOT_CHOICE_SLOT','BOOT_HOLD','BOOT_SELECT','BOOT_SLOT_CHECK','BOOT_SR_ROUTE','BOOT_UPDATE','BOOT_UPDATE_NEW','BOOT_PRINT','BOOT_RECOVERY_TEXT','BOOT_FIFO_DRAIN','BOOT_COMPAT_DATA','BOOT_META_READ','BOOT_META_CFG','BOOT_META_ERASE','BOOT_META_PROMOTE','J_CRC_INIT','BOOT_REPORT','BOOT_UPDATE_WRITE','BOOT_WORKER_IMAGE')
@dataclass
class Line:
    text:str
    key:int|None=None
def plain(lines):return '\n'.join(x.text for x in lines)+'\n'
def label(text):
    m=re.match(r'^\s*(\w+):',text);return m[1] if m else None
def asm(out):
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[];return a
def rows(a,name):
    body,sy,unused=emitter(a,name);lines=flatten(a.out/'s/core/str8n-v2-boot.asm');records={}
    for line in (a.out/'s/core'/(name+'.lst')).read_text().splitlines():
        m=re.match(r'^\s*(\d+) 00:([0-9A-F]{4}):',line)
        if not m:continue
        n,pc=int(m[1])-1,0xf000+int(m[2],16)
        src=re.sub(r'^\w+:\s*','',lines[n].strip()).split(';',1)[0].strip()
        src=re.sub(r'^\w+\s+(?=(?:DB|DW)\b)','',src)
        if not src or src.split()[0] in ('CODE','MODULE','ENDMOD','END','EQU','XDEF'):continue
        records.setdefault(n,(pc,src))
    ordered=sorted((pc,n,src) for n,(pc,src) in records.items());result={}
    for i,(pc,n,src) in enumerate(ordered):
        stop=ordered[i+1][0] if i+1<len(ordered) else 0xf000+len(body)
        if stop>pc:result[n]=dict(pc=pc,source=src,raw=body[pc-0xf000:stop-0xf000])
    assert b''.join(v['raw'] for v in result.values())==body
    return body,sy,lines,result
def transform(original,allowed,pads=None):
    result=[];changes=[];removed=[];i=0;counts={};in_crc=False
    while i<len(original):
        node=original[i];s=node.text.strip();name=label(node.text)
        if name=='J_CRC_INIT':in_crc=True
        if name=='BOOT_REPORT':in_crc=False
        # Old internal FF padding is recreated at the fixed CRC boundary.
        if i and label(original[i-1].text)=='F_SIZE_PADDING' and re.fullmatch(r'DB (?:\$FF,)*\$FF',s):
            removed.append(dict(key=node.key,kind='padding'));i+=1;continue
        m=re.fullmatch(r'(B(?:CC|CS|EQ|NE|MI|PL|VC|VS))\s+(\w+)',s)
        if m and i+2<len(original) and not in_crc:
            jump=re.fullmatch(r'JMP\s+(\w+)',original[i+1].text.strip())
            skip=label(original[i+2].text)
            if jump and skip==m[2] and jump[1] in ('BOOT_SLOT_BAD','BOOT_UPDATE_BAD','BOOT_COUNTS_UNKNOWN','BOOT_REPORT_NEXT'):
                dest={'BOOT_SLOT_BAD':'FBC_SLOT_BAD','BOOT_UPDATE_BAD':'FBC_UPDATE_REFUSE'}.get(jump[1],jump[1])
                result.append(Line('                        '+INVERSE[m[1]]+' '+dest,node.key))
                changes.append(dict(key=node.key,kind='conditional',skip=skip,semantic_dest=jump[1],dest=dest,original=m[1],replacement=INVERSE[m[1]]))
                counts[jump[1]]=counts.get(jump[1],0)+1
                removed.append(dict(key=original[i+1].key,kind='jump'));i+=2;continue
        jump=re.fullmatch(r'JMP\s+(\w+)',s)
        if jump:
            dest=jump[1];ordinal=counts.get(dest,0);counts[dest]=ordinal+1
            if (dest,ordinal) in allowed:
                node=Line(re.sub(r'\bJMP\b','BRA',node.text,count=1),node.key)
                changes.append(dict(key=node.key,kind='jump',dest=dest,original='JMP',replacement='BRA'))
        if name=='BOOT_LENGTH_OK':
            result += [Line('FBC_SLOT_SKIP: BRA BOOT_LENGTH_OK'),Line('FBC_SLOT_BAD: CLC'),Line(' RTS')]
        if name=='BOOT_RECEIVE':
            result += [Line('FBC_UPDATE_SKIP: BRA BOOT_RECEIVE'),Line('FBC_UPDATE_REFUSE: JMP BOOT_UPDATE_BAD')]
        if name in ANCHORS:
            result.append(Line('FBC_PAD_'+name+':'))
            count=(pads or {}).get(name,0)
            if count:result.append(Line(' DB '+','.join('$FF' for _ in range(count))))
        result.append(node);i+=1
    return result,changes,removed

def expression(text,sy):
    text=text.strip()
    if text.startswith('(') and text.endswith(')'):text=text[1:-1]
    text=re.sub(r'\$([0-9A-Fa-f]+)',r'0x\1',text)
    def evaluate(n):
        if isinstance(n,ast.Expression):return evaluate(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,int):return n.value
        if isinstance(n,ast.Name):return sy[n.id]
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub)):
            x,y=evaluate(n.left),evaluate(n.right);return x+y if isinstance(n.op,ast.Add) else x-y
        raise ValueError(text)
    return evaluate(ast.parse(text,mode='eval'))

def proof(a,name,lines,emitted):
    text=[]
    for node in lines:
        if node.key in emitted:text.append('FBC_M%05d:'%node.key)
        text.append(node.text)
    (a.out/'s/core'/(name+'.asm')).write_text('\n'.join(text)+'\n')
    return a.link('core',name,0xf000,'BOOT_END')

def audit(a,original,transformed,emitted,changes,removed,pads,oldbody,body,oldsy,sy):
    before,bs=proof(a,'f-flow-map-before',original,emitted)
    after,ns=proof(a,'f-flow-map-after',transformed,emitted)
    assert before==oldbody and after==body
    assert all(bs[k]==v for k,v in oldsy.items()) and all(ns[k]==v for k,v in sy.items())
    import sys
    sys.path.insert(0,str(ROOT/'BUILD/v1.30/local/test-deps'))
    from py65.devices.mpu65c02 import MPU
    edits={x['key']:x for x in changes};deleted={x['key']:x['kind'] for x in removed};covered=set();checked=0
    for key,row in emitted.items():
        raw=row['raw'];src=row['source'];op=src.split()[0];pc=row['pc']
        assert bs['FBC_M%05d'%key]==pc
        if key in deleted:
            assert (deleted[key]=='jump' and op=='JMP' and len(raw)==3) or (deleted[key]=='padding' and raw==b'\xff'*11)
            continue
        target=ns['FBC_M%05d'%key];expected=bytearray(raw);edit=edits.get(key)
        if edit:
            dest=sy[edit['dest']];delta=dest-target-2;assert -128<=delta<=127
            expected=bytes((raw[0]^0x20 if edit['kind']=='conditional' else 0x80,delta&255))
        elif op not in ('DB','DW'):
            mnemonic,mode=MPU.disassemble[raw[0]];assert mnemonic==op,(src,mnemonic)
            operand=src.split(None,1)[1] if ' ' in src else ''
            if mode=='rel':
                delta=sy[operand]-target-2;assert -128<=delta<=127;expected[1]=delta&255
            elif len(raw)==3:
                operand=re.sub(r',\s*[XY]$','',operand)
                value=expression(operand,sy);expected[1:]=value.to_bytes(2,'little')
            elif mode=='imm':
                m=re.fullmatch(r'#([<>])(\w+)',operand)
                if m:expected[1]=(sy[m[2]] if m[1]=='<' else sy[m[2]]>>8)&255
        assert body[target-0xf000:target-0xf000+len(expected)]==bytes(expected),(hex(pc),src,bytes(expected).hex())
        covered.update(range(target,target+len(expected)));checked+=1
    extra={sy['FBC_SLOT_SKIP']:bytes((0x80,2)),sy['FBC_SLOT_BAD']:bytes.fromhex('1860'),sy['FBC_UPDATE_SKIP']:bytes((0x80,3)),sy['FBC_UPDATE_REFUSE']:b'\x4c'+sy['BOOT_UPDATE_BAD'].to_bytes(2,'little')}
    for pc,raw in extra.items():
        assert body[pc-0xf000:pc-0xf000+len(raw)]==raw
        assert not covered.intersection(range(pc,pc+len(raw)));covered.update(range(pc,pc+len(raw)))
    for name,count in pads.items():
        pc=sy['FBC_PAD_'+name];assert body[pc-0xf000:pc-0xf000+count]==b'\xff'*count
        assert not covered.intersection(range(pc,pc+count));covered.update(range(pc,pc+count))
    assert covered==set(range(0xf000,sy['BOOT_END'])),'Every emitted byte must be explained'
    for change in changes:
        change.update(before_pc=emitted[change['key']]['pc'],after_pc=ns['FBC_M%05d'%change['key']])
    return dict(passed=True,independent_flattened_links_match=True,every_emitted_byte_explained=True,unchanged_instruction_data_rows=checked-len(changes),new_failure_path_bytes=9)

def prepare(control,out):
    control,out=control.resolve(),out.resolve();assert not out.exists() and len(str(out))<65
    snapshot=protected();selected=sha((ROOT/'BUILD/current/firmware.bin').read_bytes())
    current={p.relative_to(ROOT/'src/current').as_posix():sha(p.read_bytes()) for p in (ROOT/'src/current').rglob('*') if p.is_file()}
    assert read(control/'build-report.json')['passed'] and read(control/'build-report.json')['source_files']==current
    image=(control/'firmware.bin').read_bytes();assert sha(image)==BASE==selected
    shutil.copytree(control,out);a=asm(out);oldbody,oldsy,flat,emitted=rows(a,'f-flow-original')
    original=[Line(s,n) for n,s in enumerate(flat)]
    # Select private JMPs by linked range, excluding fixed service wrappers,
    # CRC and the JMP half of the conditional rewrites.
    allowed=set();ordinals={};folded_jumps=set()
    for i,node in enumerate(original[:-2]):
        branch=re.fullmatch(r'B(?:CC|CS|EQ|NE|MI|PL|VC|VS)\s+(\w+)',node.text.strip())
        if branch and re.fullmatch(r'JMP\s+\w+',original[i+1].text.strip()) and label(original[i+2].text)==branch[1]:folded_jumps.add(i+1)
    for i,node in enumerate(original):
        m=re.fullmatch(r'JMP\s+(\w+)',node.text.strip())
        if not m:continue
        dest=m[1];ordinal=ordinals.get(dest,0);ordinals[dest]=ordinal+1
        if i not in emitted:continue
        pc=emitted[i]['pc'];delta=oldsy[dest]-pc-2
        if pc>=0xf0c5 and not 0xfab4<=pc<0xfae7 and i not in folded_jumps and dest!='J_ENTER' and -120<=delta<=120:allowed.add((dest,ordinal))
    # The same text transformation is applied to normal includes and a separate
    # fully flattened, instruction-identified proof source.
    originals={n:(out/'s/core'/n).read_text() for n in FILES}
    def write(pads=None):
        for name,text in originals.items():
            result,_,_=transform([Line(s) for s in text.splitlines()],allowed,pads)
            (out/'s/core'/name).write_text(plain(result))
    write();unpacked,us=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
    pads={};added=0
    for name in ANCHORS:
        count=oldsy[name]-us[name]-added;assert count>=0,(name,count)
        pads[name]=count;added+=count
    write(pads);body,sy=a.link('core','str8n-v2-boot',0xf000,'BOOT_END')
    transformed,changes,removed=transform(original,allowed,pads)
    assert [x.text for x in transformed]==flatten(out/'s/core/str8n-v2-boot.asm')
    assert sum(x['kind']=='conditional' for x in changes)==19 and sum(x['kind']=='jump' for x in changes)==17
    assert all(sy[name]==oldsy[name] for name in ANCHORS)
    evidence=audit(a,original,transformed,emitted,changes,removed,pads,oldbody,body,oldsy,sy)
    original_symbols=read(control/'symbols.json');symbols=dict(original_symbols);symbols['core/str8n-v2-boot']=sy
    fixed=boot_sector(body,sy,original_symbols['core/str8n-v2-vectors'],read(ROOT/'src/current/layout.json')['boot_compatibility'])
    oldfixed=image[-4096:]
    assert fixed[:0xc5]==oldfixed[:0xc5] and fixed[0xab4:0xae7]==oldfixed[0xab4:0xae7]
    assert fixed[0xb93:]==oldfixed[0xb93:],'ROM worker, trailing free area and hardware vectors unchanged'
    assert fixed[sy['BOOT_VECTOR_IMAGE']-0xf000:sy['BOOT_VECTOR_IMAGE']-0xf000+196]==oldfixed[0x9e5:0xaa9]
    assert fixed[0x57d:0x586]==oldfixed[0x57d:0x586]==bytes.fromhex('64f6205cfbeaeaeaea')
    a.emit('str8n-v2-recovery-f000-ffff.bin',fixed);new=image[:-4096]+fixed;(out/'firmware.bin').write_bytes(new);save(out/'symbols.json',symbols)
    patch=''.join(''.join(difflib.unified_diff(originals[n].splitlines(True),(out/'s/core'/n).read_text().splitlines(True),fromfile='src/current/core/'+n,tofile='src/current/core/'+n)) for n in FILES)
    (out/'source.patch').write_text(patch)
    changed=[p.relative_to(out/'payload').as_posix() for p in sorted((out/'payload').rglob('*')) if p.is_file() and p.read_bytes()!=(control/'payload'/p.relative_to(out/'payload')).read_bytes()]
    assert changed==['str8n-v2-recovery-f000-ffff.bin'] and sum(pads.values())==76
    report=dict(passed=True,board_access=False,installation_permitted=False,candidate='fixed-f-flow-size',baseline_sha256=BASE,firmware_sha256=sha(new),fixed_F_sha256=sha(fixed),
        conditional_branches=19,short_private_jumps=17,new_failure_path_bytes=9,additional_free_bytes=65,contiguous_free_bytes=204,interior_free_bytes=76,previous_interior_free_bytes=11,
        body_bytes=len(body),padding_blocks=[dict(anchor=n,address=sy['FBC_PAD_'+n],bytes=count) for n,count in pads.items() if count],
        A_B_and_all_non_F_bytes_unchanged=True,CRC_bytes_and_addresses_unchanged=True,journal_format_and_two_sectors_unchanged=True,recovery_status_fix_unchanged=True,worker_and_initialized_vectors_unchanged=True,
        fixed_entries={k:sy[k] for k in ANCHORS},changes=changes,emission_audit=evidence,source_files=current,protected_snapshot=snapshot,selected_current_sha256=selected,tool_sha256=sha(Path(__file__).read_bytes()),changed_payloads=changed)
    save(out/'f-flow-build.json',report)
    save(out/'build-report.json',dict(passed=True,candidate_only=True,board_access=False,installation_permitted=False,candidate_id=report['candidate'],firmware_sha256=sha(new),baseline_sha256=BASE,source_patch_sha256=sha((out/'source.patch').read_bytes())))
    assert protected()==snapshot and sha((ROOT/'BUILD/current/firmware.bin').read_bytes())==selected
    print('PASS separate F flow candidate: 65 additional free bytes; 204 end + 76 internal; A/B, CRC, format, services and worker preserved',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    offline();prepare(args.control,args.out)
