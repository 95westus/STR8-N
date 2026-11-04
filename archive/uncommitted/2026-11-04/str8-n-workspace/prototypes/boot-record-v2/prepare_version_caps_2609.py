"""Offline VX1 provider, matching MONs and exact current-state RAM installer.

F stays byte-identical. VX1 is a narrow B3 ROM-locator prototype, not the future
F-initialized resident ABI. No device import, board upload or flashing path.
"""
import argparse,json,shutil,sys,hashlib,re
from pathlib import Path
import prepare_journal_init_2609 as b
from build import long_branches
from str8build.assemble import Assembly
from str8build.images import monitor_slot
from str8build.formats import crc,sealed,save,read_s19

ROOT,HERE,TARGET,SESSION=b.ROOT,b.HERE,b.TARGET,b.SESSION


def normalized(image,kind):
    raw=bytearray(image);raw[0xfdc:0xffc]=bytes(32)
    if kind=='MON':raw[18:20]=b'\0\0'
    else:raw[-2:]=b'\0\0'
    raw[31]=0
    return hashlib.sha256(raw).digest()


def footer(kind,page,release):
    assert len(release.encode())<=15,'Release field must be NUL terminated'
    row=bytearray(b'\xff'*64);row[:8]=(b'MC' if kind=='MON' else b'XC')+bytes([1,1,1,64,page,0])
    row[8:12]=b.GENERATION.to_bytes(4,'little');row[12:28]=release.encode().ljust(16,b'\0');row[28:60]=bytes(32)
    return row


def provenance():
    state=b.r.read(SESSION/'session.json');run=Path(state['step07_report']).parent
    report=b.r.read(run/'report.json');audit=b.r.read(run/'audit.json');history=Path(state['wear_history']);wear=b.r.read(history)
    b.r.require(report['passed'] and audit['passed'] and state['MON_installed'] and not state['configuration_changed'],'Verified unconfigured MON A/B checkpoint required')
    b.r.require(wear['execution_report_sha256']==b.digest(run/'report.json') and wear['counts'][26:]==[50,53,78,47,42,30] and wear['sequence']==1017,'Verified actual owner history required')
    banks=[];files=[run/'report.json',run/'audit.json',history]
    for n in range(4):
        first,second=run/f'after-r1-b{n}.bin',run/f'after-r2-b{n}.bin';raw=first.read_bytes()
        b.r.require(raw==second.read_bytes() and len(raw)==32768,'Repeated bank capture required');banks.append(raw);files.extend([first,second])
    b.r.require(b.r.hashes(banks)==report['expected_sha256'] and b.r.sha(banks[0])==b.WDC_SHA and b.r.sha(banks[3][-4096:])==b.F_SHA,'Changed source/B0/F')
    records=b.snbt_records(banks);latest=max(records)[2]
    b.r.require(len(records)==4 and [int.from_bytes(latest[64+3*i:67+3*i],'little') for i in range(32)]==wear['counts'],'Journal/history mismatch')
    files.extend([Path(__file__),*[HERE/name for name in ('version-caps-e000.asm','version-caps-mon.inc','version-caps-public.inc','version-caps-client.asm','ram-mon-install-2609.asm','ram-journal-init-2609.asm')]])
    return banks,wear,latest,{str(p.resolve()):b.bind(p) for p in files}


def assembler(out):
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    return a


def build(out):
    out=Path(out).resolve();b.r.require(not out.exists(),'Fresh output required')
    source,wear,latest,inputs=provenance();out.mkdir(parents=True)
    shutil.copytree(TARGET/'s',out/'s');(out/'payload').mkdir();core=out/'s/core';a=assembler(out)
    shutil.copy2(HERE/'version-caps-public.inc',core/'version-caps-public.inc')
    for name in ('version-caps-e000.asm','version-caps-client.asm'):
        (core/name).write_text(long_branches((HERE/name).read_text()))
    fcrc=crc(source[3][-4096:]);f_identity=hashlib.sha256(source[3][-4096:]).digest()
    ident=f'F_CRC_LO EQU ${fcrc&255:02X}\nF_CRC_HI EQU ${fcrc>>8:02X}\n'
    ident+=b.db('VX_F_GENERATION',b.GENERATION.to_bytes(4,'little'))+b.db('VX_F_IDENTITY',f_identity)
    ident+=b.db('VX_F_RELEASE_TEXT',b'2.0proto b15\0'.ljust(16,b'\0'))
    (core/'version-caps-identities.inc').write_text(ident)
    raw,es=a.link('core','version-caps-e000',0xe000,'VX_END');assert len(raw)==4096 and es['VX_CODE_END']<0xefc0
    extension=bytearray(raw);extension[0xfc0:]=footer('EXT',0,'b15-vx1');extension[-2:]=b'\0\0'
    extension[0xfdc:0xffc]=normalized(extension,'EXT');extension[-2:]=crc(extension[:-2]).to_bytes(2,'big');assert crc(extension)==0
    a.emit('version-caps-e000.bin',extension)
    monitor_source=(TARGET/'s/core/monitor-b0.asm').read_text()
    start=monitor_source.index('AP_TRY:');end=monitor_source.index('V2_SR_DISPATCH:',start)
    hooks=long_branches((HERE/'version-caps-mon.inc').read_text()).replace('P_LONG_','VX_LONG_')
    # Remove dead legacy AP/B29 implementations; their refusal entry points stay.
    monitor_source=monitor_source[:start]+hooks+'\nAP_CHECK: CLC\n        RTS\n\n'+monitor_source[end:]
    start=monitor_source.index('B29_LEGACY_DISABLED:');end=monitor_source.index('B29_GATE_IMAGE:',start)
    monitor_source=monitor_source[:start]+monitor_source[end:]
    monitor_source=monitor_source.replace('V2_RESERVED2_ENTRY:     JMP     V2_RESERVED','V2_RESERVED2_ENTRY:     JMP     VX_DISCOVER')
    assert 'JMP     VX_DISCOVER' in monitor_source
    monitor_source=monitor_source.replace('        INCLUDE "app-fixed-symbols.inc"','        INCLUDE "app-fixed-symbols.inc"\n        INCLUDE "version-caps-public.inc"')
    sy=b.r.read(TARGET/'symbols.json');monitors=[]
    vs=sy['core/str8n-v2-vectors']
    for page in (0xa0,0xb0):
        name=f'monitor-{page:02x}'
        (core/(name+'.asm')).write_text(monitor_source.replace('V2_IMAGE_PAGE EQU $B0',f'V2_IMAGE_PAGE EQU ${page:02X}'))
        body,ms=a.link('core',name,page*256+128,'V2_END')
        # Shorten only measured local hook trampolines; preserve old code paths.
        for _ in range(8):
            text=(core/(name+'.asm')).read_text()
            inverse=dict(BEQ='BNE',BNE='BEQ',BCC='BCS',BCS='BCC',BMI='BPL',BPL='BMI',BVC='BVS',BVS='BVC')
            def compact(match):
                branch,label,dest=match.groups()
                return '        '+inverse[branch]+' '+dest+'\n' if label in ms and dest in ms and -128<=ms[dest]-(ms[label]-3)<=127 else match[0]
            updated=re.sub(r'        (BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS) (VX_LONG_\d+)\n        JMP (\w+)\n\2:\n',compact,text)
            if updated==text:break
            (core/(name+'.asm')).write_text(updated);body,ms=a.link('core',name,page*256+128,'V2_END')
        assert ms['V2_END']<=page*256+0xfc0,'MON metadata footer overlaps code'
        slot=bytearray(monitor_slot(body,ms,page,b.GENERATION,int.from_bytes(b'PR04','little')))
        # Retain b15's default BRK vector and relocated harmless trampoline.
        header=slot[72:128].replace(bytes.fromhex('9D817B'),bytes.fromhex('9D507C')).replace(bytes.fromhex('A9818D027EA97B8D037E'),bytes([0xA9,vs['V2V_DEFAULT']&255,0x8D,2,0x7e,0xA9,vs['V2V_DEFAULT']>>8,0x8D,3,0x7e]))
        slot[72:128]=header;slot[0xfc0:]=footer('MON',page,'2.0proto b15vx1')
        slot[0xfdc:0xffc]=normalized(slot,'MON');slot[18:20]=crc(slot[:18]+slot[32:]).to_bytes(2,'little')
        assert b.wire.slot_valid(slot,page)
        a.emit(name+'-version-caps.bin',slot);a.emit(name+'-offline-component.bin',slot)
        sy['core/'+name]=ms;monitors.append(bytes(slot))
    client,cs=a.link('core','version-caps-client',0x200,'VQ_END');a.emit('version-caps-query-RAM.bin',client)
    shutil.copy2(TARGET/'payload/f-offline-component.bin',out/'payload/f-offline-component.bin')
    shutil.copy2(TARGET/'prototype-report.json',out/'prototype-report.json')
    sy['extension']=es;sy['client']=cs;save(out/'symbols.json',sy)
    # Exact current-state transaction. E first is ignored by old MONs; each new
    # MON sees only a complete committed VX1 provider. Default remains S.
    state=list(map(bytearray,source));counts=wear['counts'].copy();seq=wear['sequence'];ops=[]
    for n,(address,data) in enumerate(((0xe000,bytes(extension)),(0xa000,monitors[0]),(0xb000,monitors[1]))):
        index=24+(address>>12)-8;assert counts[index]<0xffffff;counts[index]+=1;seq+=1
        row=bytearray(latest);row[8:12]=seq.to_bytes(4,'little');row[64:160]=b''.join(c.to_bytes(3,'little') for c in counts)
        row[30:32]=crc(row[:30]).to_bytes(2,'little');row[252:254]=crc(row[:252]).to_bytes(2,'little');latest=bytes(row)
        for target,body,erase,commit,kind in ((0xc300+256*n,latest,False,255,'wear reservation'),(address,data,True,31,'component')):
            off=target-0x8000;before=b.r.hashes(state)
            if not erase:assert state[3][off:off+len(body)]==b'\xff'*len(body)
            state[3][off:off+len(body)]=body;ops.append(dict(address=target,pages=len(body)//256,erase=erase,commit=commit,kind=kind,body=body,before_sha256=before,after_sha256=b.r.hashes(state)))
    expected=list(map(bytes,state));build_installer(out,a,source,expected,counts,wear,ops)
    for n in range(4):(out/f'source-b{n}.bin').write_bytes(source[n]);(out/f'expected-b{n}.bin').write_bytes(expected[n])
    for n,op in enumerate(ops):(out/f'action-{n:02d}.bin').write_bytes(op.pop('body'))
    sy['installer']=a.symbols['core/version-caps-installer'];save(out/'symbols.json',sy)
    plan=dict(passed=True,board='2609',hardware=False,board_access=False,serial_access=False,flashed=False,
        source_sha256=b.r.hashes(source),expected_sha256=b.r.hashes(expected),counts_before=wear['counts'],counts_after=counts,
        sequence_before=wear['sequence'],sequence_after=seq,config=wear['config'],unknown_history_mask='ffffffff',
        default='S',enabled_banks=0,F_unchanged=True,B0_backup_sha256=b.WDC_SHA,F_sha256=b.F_SHA,
        erase_order=['B3:E000','B3:A000','B3:B000'],operations=ops,confirmation='INSTALL VERSION',
        BIN='2609-VERSION-CAPS-RAM.bin',discovery='B3:E000 ROM descriptor; MON reserved facade +AE; RAM client preserves caller PCR',
        identities={name:dict(sha256=b.r.sha(data),build_id=data[0xfdc:0xffc].hex()) for name,data in [('E',bytes(extension)),('MON A',monitors[0]),('MON B',monitors[1])]},
        bytes=(out/'payload/2609-VERSION-CAPS-RAM.bin').stat().st_size,
        inputs=inputs,artifacts={str(p.relative_to(out)):b.bind(p) for p in [*list((out/'payload').glob('*.bin')),out/'symbols.json',*out.glob('*-b*.bin'),*out.glob('action-*.bin')]})
    save(out/'plan.json',plan);return plan


def build_installer(out,a,source,expected,counts,wear,ops):
    core=out/'s/core';common=(HERE/'ram-journal-init-2609.asm').read_text().split('JI_PREFLIGHT:\n',1)[1].split('JI_TITLE:',1)[0]
    common='JI_PREFLIGHT:\n'+common.replace('CMP JI_BANK_HASHES,X','JSR MI_COMPARE_BANK')
    (core/'component-common.inc').write_text(long_branches(common).replace('P_LONG_','MC_LONG_'))
    params='MI_ACTION_COUNT EQU 6\n'+b.db('JI_TITLE',b'2609 RAM VERSION/CAPS INSTALL / b15 F / USB only\r\n\0')
    params+=b.db('JI_PROMPT',b'RAM MINSTALL ? V W I Q> \0')+b.db('JI_CONFIRM',b'Type INSTALL VERSION then Enter> \0')+b.db('JI_CONFIRM_WORD',b'INSTALL VERSION\0')
    ranges=[]
    for name in ('worker','vectors'):
        cells=read_s19(TARGET/f's/core/str8n-v2-{name}.s19');ranges.append((min(cells),max(cells)+1,bytes(cells[k] for k in range(min(cells),max(cells)+1))))
    params+=b.db('JI_RAM_RANGES',b''.join(lo.to_bytes(2,'little')+hi.to_bytes(2,'little') for lo,hi,data in ranges))
    params+=b.db('JI_RAM_HASHES',b''.join(b.wire.fnv(data).to_bytes(4,'little') for lo,hi,data in ranges))
    for name,banks in (('JI_BANK_HASHES',source),('JI_POST_HASHES',expected)):params+=b.db(name,b''.join(b.wire.fnv(data).to_bytes(4,'little') for data in banks))
    text='Tracked lower bounds; prior lifetime UNKNOWN FFFFFFFF\r\n'
    for bank in range(4):
        text+=f'B{bank} before: '+' '.join(map(str,wear['counts'][bank*8:bank*8+8]))+'\r\n'
        text+=f'B{bank} planned: '+' '.join(map(str,counts[bank*8:bank*8+8]))+'\r\n'
    params+=b.db('JI_WEAR_TEXT',text.encode()+b'\0')+'MI_ACTIONS:\n'
    for n,op in enumerate(ops):params+=f' DB ${op["address"]>>8:02X},{op["pages"]},{int(op["erase"])},{op["commit"]},<MI_DATA_{n},>MI_DATA_{n}\n'
    for n,op in enumerate(ops):params+=b.db(f'MI_DATA_{n}',op['body'])
    (core/'mon-install-params.inc').write_text(params)
    (core/'version-caps-installer.asm').write_text(long_branches((HERE/'ram-mon-install-2609.asm').read_text()))
    raw,sy=a.link('core','version-caps-installer',0x200,'JI_END');assert sy['JI_END']<0x6200
    a.emit('2609-VERSION-CAPS-RAM.bin',raw[:-4]+b.wire.fnv(raw[:-4]).to_bytes(4,'little'))


def verify(out):
    out=Path(out).resolve();plan=b.r.read(out/'plan.json')
    for name,info in plan['inputs'].items():b.r.require(b.digest(name)==info['sha256'],'Changed input '+name)
    for name,info in plan['artifacts'].items():b.r.require(b.digest(out/name)==info['sha256'],'Changed artifact '+name)
    b.r.require(plan['F_unchanged'] and plan['erase_order']==['B3:E000','B3:A000','B3:B000'],'Wrong scope')
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=build(args.out) if args.command=='prepare' else verify(args.out)
    print(json.dumps({k:result[k] for k in ('passed','bytes','erase_order','counts_after','F_unchanged')}),flush=True)
