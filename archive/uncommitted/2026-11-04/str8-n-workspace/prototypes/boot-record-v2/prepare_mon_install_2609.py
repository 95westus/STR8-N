"""Offline exact-plan MON-only and combined C/D+MON RAM BINs for 2609.

No serial/live execution path. Keep F and all opaque image sectors unchanged.
The combined route binds the archived F-only checkpoint; it is not for replay
on the current F+C/D board. Both routes produce the same final flash image.
"""
import argparse,json,shutil,sys
from pathlib import Path
import prepare_journal_init_2609 as base
from str8build.assemble import Assembly
from str8build.formats import read_s19
from build import long_branches
from installer.common import save

ROOT,HERE,TARGET=base.ROOT,base.HERE,base.TARGET
SESSION=base.SESSION


def seal(row,counts,seq):
    row=bytearray(row);row[8:12]=seq.to_bytes(4,'little')
    row[64:160]=b''.join(n.to_bytes(3,'little') for n in counts)
    row[30:32]=base.wire.crc(row[:30]).to_bytes(2,'little')
    row[252:254]=base.wire.crc(row[:252]).to_bytes(2,'little');row[255]=0
    return bytes(row)


def provenance(session):
    session=Path(session);state=base.r.read(session/'session.json')
    run=Path(state['step05_report']).parent;report=base.r.read(run/'report.json');audit=base.r.read(run/'audit.json')
    history_path=Path(state['wear_history']);history=base.r.read(history_path)
    base.r.require(state['journals_initialized'] and not state['MON_installed'] and report['passed'] and audit['passed'], 'Verified F+C/D without MON required')
    base.r.require(history['execution_report_sha256']==base.digest(run/'report.json') and history['onboard_journal_initialized'], 'Verified actual wear history required')
    current=[]
    for n in range(4):
        first,second=run/f'after-r1-b{n}.bin',run/f'after-r2-b{n}.bin'
        data=first.read_bytes();base.r.require(len(data)==32768 and data==second.read_bytes(),'Repeated actual bank capture required');current.append(data)
    base.r.require(base.r.hashes(current)==report['expected_sha256'] and base.r.sha(current[0])==base.WDC_SHA, 'Changed hardware postimage/B0 backup')
    records=base.snbt_records(current);newest=max(records)[2]
    base.r.require(len(records)==2 and int.from_bytes(newest[8:12],'little')==history['sequence']==1015 and newest[32:48].hex()==history['config'], 'Current journal/config binding differs')
    base.r.require([int.from_bytes(newest[64+3*n:67+3*n],'little') for n in range(32)]==history['counts'] and newest[160:164]==bytes.fromhex(history['history_unknown_mask']), 'Current journal wear differs')
    prior=Path(state['step04_plan']).parent;old=base.verify(prior)
    bare=[(prior/f'source-b{n}.bin').read_bytes() for n in range(4)]
    oldhistory=base.r.read(session/'step03-F-only-install/host-wear-after.json')
    base.r.require(oldhistory['counts']==old['counts_before'] and oldhistory['sequence']==1013 and not base.snbt_records(bare),'Archived F-only history differs')
    qualification=base.r.read(TARGET/'b15-qualification.json')
    mon=[]
    for page in (0xa0,0xb0):
        name=f'monitor-{page:02x}-offline-component.bin';data=(TARGET/'payload'/name).read_bytes()
        base.r.require(base.digest(TARGET/'payload'/name)==qualification['reproducible_payload_sha256'][name] and base.wire.slot_valid(data,page), 'Exact qualified b15 MON required')
        base.r.require(int.from_bytes(data[8:12],'little')==base.GENERATION and data[20:24]==b'PR04', 'MON generation/contract differs')
        mon.append(data)
    base.r.require(base.r.sha(current[3][-4096:])==base.F_SHA and bare[:3]==current[:3] and bare[3][:0x4000]==current[3][:0x4000] and bare[3][0x6000:]==current[3][0x6000:], 'Routes differ outside C/D')
    files=[run/'report.json',run/'audit.json',history_path,session/'step03-F-only-install/host-wear-after.json',prior/'plan.json',TARGET/'b15-qualification.json',
           TARGET/'payload/f-offline-component.bin',*[TARGET/f'payload/monitor-{page:02x}-offline-component.bin' for page in (0xa0,0xb0)],
           Path(__file__),HERE/'ram-mon-install-2609.asm',HERE/'ram-journal-init-2609.asm']
    return current,bare,history,oldhistory,newest,mon,{str(p.resolve()):base.bind(p) for p in files}


def derive(source,history,mode,existing,mon):
    base.r.require(mode in ('mon-only','cd-mon'),'Unknown route')
    state=list(map(bytearray,source));counts=list(history['counts']);seq=history['sequence'];ops=[]
    base.r.require(all(type(n) is int and 0<=n<=0xffffff for n in counts) and len(counts)==32,'Invalid wear history')
    base.r.require(1<=seq<=0xfffffff9,'Sequence exhausted')
    def add(address,body,erase,commit,kind):
        before=base.r.hashes(state);off=address-0x8000
        if not erase:base.r.require(state[3][off:off+len(body)]==b'\xff'*len(body),'Reservation page is not blank')
        state[3][off:off+len(body)]=body
        ops.append(dict(address=address,pages=len(body)//256,erase=erase,commit=commit,kind=kind,
                        before_sha256=before,after_sha256=base.r.hashes(state),body=body,counts_at_commit=counts.copy()))
    if mode=='cd-mon':
        reserved,cfg,rows=base.rows(history)
        counts=reserved;seq+=2
        for address,row in zip((0xd000,0xc000),rows):add(address,row+b'\xff'*3840,True,255,'initialize journal')
        existing=rows[1]
    else:
        base.r.require(len(base.snbt_records(state))==2,'Existing two-record journal required')
    for n,address in enumerate((0xa000,0xb000)):
        index=26+n;base.r.require(counts[index]<0xffffff,'Wear counter exhausted');counts[index]+=1;seq+=1
        existing=seal(existing,counts,seq)
        add(0xc100+n*256,existing,False,255,'durable MON erase reservation')
        add(address,mon[n],True,31,'install MON '+('A' if n==0 else 'B'))
    return list(map(bytes,state)),counts,seq,ops


def build(out,mode,source,history,existing,mon,inputs):
    out=Path(out).resolve();base.r.require(not out.exists(),'Fresh output required')
    expected,counts,seq,ops=derive(source,history,mode,existing,mon)
    (out/'s/core').mkdir(parents=True);(out/'payload').mkdir();core=out/'s/core'
    for name in ('str8n-v2-eq.inc','service-eq.inc'):shutil.copy2(TARGET/'s/include'/name,core/name)
    shutil.copy2(TARGET/'s/core/worker-public-symbols.inc',core/'worker-public-symbols.inc')
    common=(HERE/'ram-journal-init-2609.asm').read_text().split('JI_PREFLIGHT:\n',1)[1].split('JI_TITLE:',1)[0]
    common='JI_PREFLIGHT:\n'+common
    base.r.require(common.count('CMP JI_BANK_HASHES,X')==1,'Guard extraction changed')
    common=common.replace('CMP JI_BANK_HASHES,X','JSR MI_COMPARE_BANK')
    (core/'component-common.inc').write_text(long_branches(common).replace('P_LONG_','MC_LONG_'))
    params=f'MI_ACTION_COUNT EQU {len(ops)}\n'
    title='2609 RAM MON A/B INSTALL' if mode=='mon-only' else '2609 RAM C/D + MON A/B INSTALL'
    confirm='INSTALL MON' if mode=='mon-only' else 'INSTALL CD MON'
    params+=base.db('JI_TITLE',(title+' / b15 F / USB only\r\n').encode()+b'\0')
    params+=base.db('JI_PROMPT',b'RAM MINSTALL ? V W I Q> \0')
    params+=base.db('JI_CONFIRM',(f'Type {confirm} then Enter> ').encode()+b'\0')
    params+=base.db('JI_CONFIRM_WORD',confirm.encode()+b'\0')
    helpers=[read_s19(TARGET/f's/core/str8n-v2-{name}.s19') for name in ('worker','vectors')]
    ranges=[(min(c),max(c)+1,bytes(c[a] for a in range(min(c),max(c)+1))) for c in helpers]
    params+=base.db('JI_RAM_RANGES',b''.join(a.to_bytes(2,'little')+b.to_bytes(2,'little') for a,b,_ in ranges))
    params+=base.db('JI_RAM_HASHES',b''.join(base.wire.fnv(data).to_bytes(4,'little') for _,_,data in ranges))
    for name,banks in (('JI_BANK_HASHES',source),('JI_POST_HASHES',expected)):
        params+=base.db(name,b''.join(base.wire.fnv(data).to_bytes(4,'little') for data in banks))
    text=f'{mode}; tracked lower bounds, prior lifetime UNKNOWN FFFFFFFF\r\n'
    for bank in range(4):
        text+=f'B{bank} before: '+' '.join(map(str,history['counts'][8*bank:8*bank+8]))+'\r\n'
        text+=f'B{bank} planned: '+' '.join(map(str,counts[8*bank:8*bank+8]))+'\r\n'
    params+=base.db('JI_WEAR_TEXT',text.encode()+b'\0')
    params+='MI_ACTIONS:\n'
    for i,op in enumerate(ops):params+=f'        DB ${op["address"]>>8:02X},{op["pages"]},{int(op["erase"])},{op["commit"]},<MI_DATA_{i},>MI_DATA_{i}\n'
    for i,op in enumerate(ops):params+=base.db(f'MI_DATA_{i}',op['body'])
    (core/'mon-install-params.inc').write_text(params)
    (core/'ram-mon-install.asm').write_text(long_branches((HERE/'ram-mon-install-2609.asm').read_text()))
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    image,sy=a.link('core','ram-mon-install',0x200,'JI_END')
    base.r.require(sy['JI_END']<0x6200 and sy['JI_SELF_HASH']==sy['JI_END']-4,'RAM image overlaps scratch')
    image=image[:-4]+base.wire.fnv(image[:-4]).to_bytes(4,'little')
    name='2609-MON-AB-RAM.bin' if mode=='mon-only' else '2609-CD-MON-AB-RAM.bin';a.emit(name,image);save(out/'symbols.json',sy)
    for n in range(4):
        (out/f'source-b{n}.bin').write_bytes(source[n]);(out/f'expected-b{n}.bin').write_bytes(expected[n])
    for i,op in enumerate(ops):
        (out/f'action-{i:02d}.bin').write_bytes(op['body']);op['body_sha256']=base.r.sha(op.pop('body'))
    plan=dict(schema=1,board='2609',mode=mode,hardware=False,serial_access=False,flashed=False,
        starting_state='Current verified F+C/D' if mode=='mon-only' else 'Archived F-only checkpoint; not current board state',
        source_sha256=base.r.hashes(source),expected_sha256=base.r.hashes(expected),counts_before=history['counts'],counts_after=counts,
        sequence_before=history['sequence'],sequence_after=seq,unknown_history_mask='ffffffff',config=history['config'],
        default='S',enabled_banks=0,generation='8000000F',F_sha256=base.F_SHA,B0_backup_sha256=base.WDC_SHA,
        BIN=name,bytes=len(image),load_address='0200',end_exclusive=f'{sy["JI_END"]:04X}',BIN_sha256=base.r.sha(image),confirmation=confirm,
        operations=ops,erase_order=[f'B3:{op["address"]:04X}' for op in ops if op['erase']],
        host_wear_updated=False,inputs=inputs,
        artifacts={p.relative_to(out).as_posix():base.bind(p) for p in [out/'payload'/name,out/'symbols.json',*out.glob('*-b*.bin'),*out.glob('action-*.bin')]},
        limits=['Offline only; no board access', 'Host reservation/log needed before first erase; first combined D erase has no prior onboard journal',
                'Changed/interrupted/completed states require a new plan; no blind replay', 'USB models only; ACIA remains not board-tested'])
    save(out/'plan.json',plan);verify(out);return plan


def verify(out):
    out=Path(out).resolve();plan=base.r.read(out/'plan.json')
    base.r.require(plan['board']=='2609' and plan['mode'] in ('mon-only','cd-mon') and not plan['flashed'],'Unsupported plan')
    for path,info in plan['inputs'].items():base.r.require(base.digest(path)==info['sha256'],'Changed input '+path)
    for name,info in plan['artifacts'].items():
        path=(out/name).resolve();base.r.require(path.is_relative_to(out) and base.digest(path)==info['sha256'],'Changed artifact '+name)
    source=[(out/f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected=[(out/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    base.r.require(base.r.hashes(source)==plan['source_sha256'] and base.r.hashes(expected)==plan['expected_sha256'],'Changed bank metadata')
    base.r.require(source[:3]==expected[:3] and source[3][:0x2000]==expected[3][:0x2000] and source[3][0x6000:]==expected[3][0x6000:] and base.r.sha(source[0])==base.WDC_SHA,'Opaque/B0/F bytes changed')
    current,bare,hist,oldhist,existing,mon,_=provenance(SESSION)
    history=hist if plan['mode']=='mon-only' else oldhist
    base.r.require(source==(current if plan['mode']=='mon-only' else bare) and plan['counts_before']==history['counts'] and plan['sequence_before']==history['sequence'] and plan['config']==history['config'],'Wrong source/history profile')
    desired,counts,seq,ops=derive(source,history,plan['mode'],existing,mon)
    base.r.require(desired==expected and counts==plan['counts_after'] and seq==plan['sequence_after'],'Wrong transaction result')
    base.r.require(len(plan['operations'])==len(ops),'Wrong operation count')
    for i,(op,want) in enumerate(zip(plan['operations'],ops)):
        body=want.pop('body');want['body_sha256']=base.r.sha(body)
        base.r.require(op==want and (out/f'action-{i:02d}.bin').read_bytes()==body,'Changed operation')
    image=(out/'payload'/plan['BIN']).read_bytes()
    base.r.require(base.wire.fnv(image[:-4])==int.from_bytes(image[-4:],'little') and base.r.sha(image)==plan['BIN_sha256'],'Bad RAM checksum')
    base.r.require(plan['erase_order']==(['B3:A000','B3:B000'] if plan['mode']=='mon-only' else ['B3:D000','B3:C000','B3:A000','B3:B000']),'Wrong erase scope')
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if args.command=='prepare':
        current,bare,hist,oldhist,existing,mon,inputs=provenance(SESSION)
        for mode,source,history in (('mon-only',current,hist),('cd-mon',bare,oldhist)):
            result=build(out/mode,mode,source,history,existing,mon,inputs)
            print(json.dumps({k:result[k] for k in ('mode','bytes','BIN_sha256','erase_order','counts_after')}),flush=True)
        assert (out/'mon-only/expected-b3.bin').read_bytes()==(out/'cd-mon/expected-b3.bin').read_bytes()
    else:print(json.dumps(verify(out),indent=2))
