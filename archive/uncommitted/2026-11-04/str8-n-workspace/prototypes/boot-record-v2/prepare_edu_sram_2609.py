"""File-only ES1 read-only provider/client and exact-current-state RAM installer."""
import argparse,shutil
from pathlib import Path
import prepare_ram_config_2609 as base
import prepare_ram_maint_ro_2609 as prior
import prepare_journal_init_2609 as jb
from prepare_mon_install_2609 import seal
from str8build.assemble import Assembly
from str8build.formats import crc,read_s19

ROOT,HERE,TARGET,SESSION=base.ROOT,base.HERE,base.TARGET,base.SESSION
PROVIDER='2609-EDU-SRAM-B3-8.bin'
CLIENT='2609-EDU-SRAM-RAM.bin'
INSTALLER='2609-EDU-SRAM-INSTALL-RAM.bin'


def build(out):
    out=Path(out).resolve();assert out.is_relative_to(ROOT/'output/qualification') and not out.exists()
    banks,baseline,inputs=prior.source()
    paths=[Path(__file__),HERE/'edu-sram-ro-provider.asm',HERE/'edu-sram-ro-client.asm',
           HERE/'ram-mon-install-2609.asm',HERE/'ram-journal-init-2609.asm',HERE/'prepare_mon_install_2609.py',
           HERE/'prepare_ram_maint_ro_2609.py',HERE/'prepare_journal_init_2609.py']
    inputs.update({str(p.resolve()):base.binding(p) for p in paths})
    marker=ROOT/'output/qualification/device-operations/2609.json';marker_sha=base.digest(marker)
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');shutil.copytree(TARGET/'s',out/'s');(out/'payload').mkdir()
    core=out/'s/core';fcrc=crc(banks[3][-4096:])
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled=[];a.symbols=base.read(TARGET/'symbols.json')
    (core/'edu-sram-params.inc').write_text(f'ES_F_CRC_LO EQU ${fcrc&255:02X}\nES_F_CRC_HI EQU ${fcrc>>8:02X}\n')
    (core/'edu-sram.asm').write_text(base.long_branches((HERE/'edu-sram-ro-provider.asm').read_text()).replace('P_LONG_','ES_LONG_'))
    body,sy=a.link('core','edu-sram',0x8040,'ES_END');assert sy['ES_END']<=0x8ffe
    provider=bytearray(b'\xff'*4096);provider[:4]=b'ES\x01\x40'
    for offset,label in ((4,'ES_INIT'),(7,'ES_QUERY'),(10,'ES_READ'),(13,'ES_PREP')):
        provider[offset:offset+3]=b'\x4c'+sy[label].to_bytes(2,'little')
    provider[16:20]=base.GENERATION.to_bytes(4,'little');provider[20:24]=bytes((0,0,2,1))
    provider[24:32]=bytes((0,0x65,0,1,1,32,1,0))
    provider[64:64+len(body)]=body;provider[-2:]=crc(provider[:-2]).to_bytes(2,'big');assert crc(provider)==0
    a.emit(PROVIDER,provider)
    guards=bytearray()
    for name in ('worker','vectors'):
        path=TARGET/f's/core/str8n-v2-{name}.s19';cells=read_s19(path);start=min(cells)
        data=bytes(cells[n] for n in range(start,max(cells)+1))
        guards+=start.to_bytes(2,'little')+len(data).to_bytes(2,'little')+crc(data).to_bytes(2,'little')
        inputs[str(path.resolve())]=base.binding(path)
    (core/'edu-client-params.inc').write_text(f'EC_F_CRC_LO EQU ${fcrc&255:02X}\nEC_F_CRC_HI EQU ${fcrc>>8:02X}\n')
    (core/'edu-client-guards.inc').write_text(jb.db('EC_GUARD_BYTES',guards))
    (core/'edu-client-header.inc').write_text(jb.db('EC_HEADER_BYTES',provider[:64]))
    old=(HERE/'ram-maint-ro-b15.asm').read_text();routines='MA_RAW_CRC:\n'+old.split('MA_RAW_CRC:\n',1)[1].split('MA_MAP:',1)[0]
    routines+='''MA_NEXT_PTR:
        INC MA_PTR
        BNE MA_NEXT_DONE
        INC MA_PTR+1
MA_NEXT_DONE:
        RTS
MA_DEC_COUNT:
        LDA MA_COUNT
        BNE MA_DEC_LOW
        DEC MA_COUNT+1
MA_DEC_LOW:
        DEC MA_COUNT
        LDA MA_COUNT
        ORA MA_COUNT+1
        RTS
'''
    (core/'edu-client-crc.inc').write_text(base.long_branches(routines.replace('MA_','EC_')).replace('P_LONG_','EC_CRC_LONG_'))
    (core/'edu-client.asm').write_text(base.long_branches((HERE/'edu-sram-ro-client.asm').read_text()).replace('P_LONG_','EC_LONG_'))
    client,cs=a.link('core','edu-client',0x200,'EC_END');client=bytearray(client)
    assert cs['EC_END']<0x2000
    off=cs['EC_IMAGE_CRC']-0x200;client[off:off+2]=crc(client[:off]).to_bytes(2,'big')
    assert crc(client[:cs['EC_IMM_END']-0x200])==0;a.emit(CLIENT,client)
    counts=list(baseline['counts']);assert counts[24]==26;counts[24]+=1
    newest=max(base.snbt_records(banks))[2];row=seal(newest,counts,1021)
    assert banks[3][0x4600:0x4700]==b'\xff'*256
    expected=list(map(bytearray,banks));ops=[]
    for address,data,erase,commit,kind in ((0xc600,row,False,255,'durable B3:8 erase reservation'),(0x8000,bytes(provider),True,31,'install read-only ES1 provider')):
        before=list(map(base.sha,expected));expected[3][address-0x8000:address-0x8000+len(data)]=data
        ops.append(dict(address=address,pages=len(data)//256,erase=erase,commit=commit,kind=kind,
            before_sha256=before,after_sha256=list(map(base.sha,expected)),body=data,counts_at_commit=counts))
    expected=list(map(bytes,expected))
    common='JI_PREFLIGHT:\n'+(HERE/'ram-journal-init-2609.asm').read_text().split('JI_PREFLIGHT:\n',1)[1].split('JI_TITLE:',1)[0]
    assert common.count('CMP JI_BANK_HASHES,X')==1
    common=common.replace('CMP JI_BANK_HASHES,X','JSR MI_COMPARE_BANK')
    (core/'component-common.inc').write_text(base.long_branches(common).replace('P_LONG_','ESC_LONG_'))
    params='MI_ACTION_COUNT EQU 2\n'
    for name,text in (('JI_TITLE','2609 RAM EDU/SRAM READ-ONLY INSTALL / b15 F / USB only\r\n'),
                      ('JI_PROMPT','RAM MINSTALL ? V W I Q> '),('JI_CONFIRM','Type INSTALL EDU then Enter> '),('JI_CONFIRM_WORD','INSTALL EDU')):
        params+=jb.db(name,text.encode()+b'\0')
    ranges=[]
    for name in ('worker','vectors'):
        c=read_s19(TARGET/f's/core/str8n-v2-{name}.s19');lo,hi=min(c),max(c)+1
        ranges.append((lo,hi,bytes(c[n] for n in range(lo,hi))))
    params+=jb.db('JI_RAM_RANGES',b''.join(lo.to_bytes(2,'little')+hi.to_bytes(2,'little') for lo,hi,_ in ranges))
    params+=jb.db('JI_RAM_HASHES',b''.join(jb.wire.fnv(data).to_bytes(4,'little') for _,_,data in ranges))
    for name,data in (('JI_BANK_HASHES',banks),('JI_POST_HASHES',expected)):
        params+=jb.db(name,b''.join(jb.wire.fnv(row).to_bytes(4,'little') for row in data))
    wear='EDU/SRAM; tracked lower bounds, prior lifetime UNKNOWN FFFFFFFF\r\n'
    for n in range(4):
        wear+=f'B{n} before: '+' '.join(map(str,baseline['counts'][8*n:8*n+8]))+'\r\n'
        wear+=f'B{n} planned: '+' '.join(map(str,counts[8*n:8*n+8]))+'\r\n'
    params+=jb.db('JI_WEAR_TEXT',wear.encode()+b'\0');params+='MI_ACTIONS:\n'
    for i,op in enumerate(ops):params+=f' DB ${op["address"]>>8:02X},{op["pages"]},{int(op["erase"])},{op["commit"]},<MI_DATA_{i},>MI_DATA_{i}\n'
    for i,op in enumerate(ops):params+=jb.db(f'MI_DATA_{i}',op['body'])
    (core/'mon-install-params.inc').write_text(params)
    (core/'ram-mon-install.asm').write_text(base.long_branches((HERE/'ram-mon-install-2609.asm').read_text()))
    image,ins=a.link('core','ram-mon-install',0x200,'JI_END');assert ins['JI_END']<0x6200 and ins['JI_SELF_HASH']==ins['JI_END']-4
    image=image[:-4]+jb.wire.fnv(image[:-4]).to_bytes(4,'little');a.emit(INSTALLER,image)
    a.emit('f-offline-component.bin',banks[3][-4096:])
    for i,op in enumerate(ops):
        data=op.pop('body');(out/f'action-{i:02d}.bin').write_bytes(data);op['body_sha256']=base.sha(data)
    for n in range(4):
        (out/f'source-b{n}.bin').write_bytes(banks[n]);(out/f'expected-b{n}.bin').write_bytes(expected[n])
    base.save(out/'symbols.json',a.symbols);shutil.copy2(TARGET/'prototype-report.json',out/'prototype-report.json');base.save(out/'baseline.json',baseline)
    artifacts=[*out.glob('*.bin'),*out.glob('*.json'),*out.glob('payload/*.bin'),*out.glob('s/core/edu-*'),
               core/'mon-install-params.inc',core/'component-common.inc',core/'ram-mon-install.asm']
    assert not base.ATTEMPTS and base.digest(marker)==marker_sha
    plan=dict(passed=True,board='2609',hardware=False,board_access=False,serial_access=False,flashed=False,RAM_uploaded=False,
        saved_setting_writes=False,host_wear_updated=False,BIN=INSTALLER,BIN_sha256=base.sha(image),bytes=len(image),
        provider=PROVIDER,provider_body_bytes=len(body),provider_body_end=f'{sy["ES_END"]:04X}',provider_sha256=base.sha(provider),
        client=CLIENT,client_bytes=len(client),client_sha256=base.sha(client),load_address='0200',
        confirmation='INSTALL EDU',source_sha256=list(map(base.sha,banks)),expected_sha256=list(map(base.sha,expected)),
        operations=ops,erase_order=['B3:8000'],counts_before=baseline['counts'],counts_after=counts,sequence_before=1020,sequence_after=1021,
        default='S',enabled_banks=0,config=baseline['config'],history_unknown_mask='ffffffff',
        SRAM_writes=False,SRAM_mode_writes=False,presence_proven=False,workspace='6500-65FF',request='6000-601F',
        F_sha256=base.F_SHA,B0_sha256=base.WDC_SHA,marker_sha256=marker_sha,inputs=inputs,
        artifacts={p.relative_to(out).as_posix():base.binding(p) for p in artifacts if p.is_file()})
    base.save(out/'plan.json',plan);verify(out)
    print('BUILT ES1 provider',len(body),'body bytes; client',len(client),'installer',len(image),'NO DEVICE ACCESS',flush=True)
    return plan


def verify(out):
    out=Path(out).resolve();p=base.read(out/'plan.json')
    for path,info in p['inputs'].items():assert base.digest(path)==info['sha256'],'Changed input '+path
    for path,info in p['artifacts'].items():assert base.digest(out/path)==info['sha256'],'Changed artifact '+path
    before=[(out/f'source-b{n}.bin').read_bytes() for n in range(4)]
    after=[(out/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert list(map(base.sha,before))==p['source_sha256'] and list(map(base.sha,after))==p['expected_sha256']
    assert before[:3]==after[:3] and before[3][0x1000:0x4600]==after[3][0x1000:0x4600] and before[3][0x4700:]==after[3][0x4700:]
    assert p['counts_after']==[v+(n==24) for n,v in enumerate(p['counts_before'])] and p['sequence_after']==p['sequence_before']+1
    seq,offset,row=max(base.snbt_records(after));assert seq==1021 and offset==0x4600 and row[7]==ord('S') and row[13]==0
    assert row[32:48].hex()==p['config'] and row[160:164]==b'\xff'*4
    for i,op in enumerate(p['operations']):assert base.digest(out/f'action-{i:02d}.bin')==op['body_sha256']
    provider=(out/'payload'/PROVIDER).read_bytes();assert crc(provider)==0 and len(provider)==4096
    image=(out/'payload'/INSTALLER).read_bytes();assert jb.wire.fnv(image[:-4])==int.from_bytes(image[-4:],'little')
    assert p['erase_order']==['B3:8000'] and not base.ATTEMPTS
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('build','verify'));parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build(args.out) if args.command=='build' else verify(args.out)
