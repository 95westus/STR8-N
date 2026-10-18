"""Private owner-authorized empty-bank fixtures and complete bf1 targets; offline."""
import hashlib,inspect,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
KIT=ROOT/'tmp/bf1-distribution-r13/migration';OUT=Q/'bf1-empty-bank-tests-2026-10-18-r1'
sys.path.insert(0,str(KIT));import runtime as r;import factory_wdc as f;import migrate as m
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def banks(folder):return [(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
def capture(folder,source,board):
    folder.mkdir();files={}
    for n,body in enumerate(source):
        for suffix in ('','-repeat'):
            name=f'b{n}{suffix}.bin';(folder/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
    save(folder/'capture.json',dict(schema=1,board=board,repeat_verified=True,model_fixture=True,files=files))

def stock_fixture(source,stock,out):
    seq,offset,row,valid=r.clean_journal(source);cfg=row[8:24]
    old=[max(int.from_bytes(v[24+i*3:27+i*3],'little') for _,_,v in valid) for i in range(32)]
    retained=offset//4096+8;other=25-retained;start=(retained-8)*4096
    free=next(i for i in range(start,start+4096,128) if source[3][i:i+128]==b'\xff'*128)
    erase=[(b,s) for b in range(3) for s in range(8,16) if source[b][(s-8)*4096:(s-7)*4096]!=b'\xff'*4096]
    erase += [(3,s) for s in [other,8,9,10,11,14,retained,15]]
    assert len(erase)<=24
    counts=list(old)
    for bank,sector in erase:counts[bank*8+sector-8]+=1
    state=list(map(bytearray,source));ops=[];data=[]
    def append(kind,bank,address,body,commit=None):
        before=r.hashes(state);off=address-0x8000;state[bank][off:off+len(body)]=body
        ops.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,source_sha256=before,after_sha256=r.hashes(state),data_sha256=r.sha(body)));data.append(body)
    append('reserve-owner-empty-bank-fixture',3,free+0x8000,r.record(cfg,counts,seq+1),free+0x807f)
    for bank,sector in erase:append('private-fixture-sector',bank,sector<<12,b'\xff'*4096 if bank<3 else stock[(sector-8)*4096:(sector-7)*4096])
    expected=list(map(bytes,state));assert expected[:3]==[b'\xff'*32768]*3 and expected[3]==stock
    tx=dict(source_sha256=r.hashes(source),expected_sha256=r.hashes(expected),operations=ops,planned_erase_order=[list(v) for v in erase],counts_before=old,reserved_counts=counts,sequence_before=seq,sequence_after=seq+1,reservation_offset=free,source_config=cfg.hex(),target_config=cfg.hex(),model_only=True,installation_permitted=False)
    info=r.compose(KIT/'template',out,source,tx,data,expected);info.update(board='2609',route='private-empty-banks-WDC-fixture');save(out/'plan.json',info)
    return info,expected,cfg,counts,seq+1

def main():
    assert not OUT.exists();OUT.mkdir();m.verify_kit(KIT)
    auth=Q/'bf1-empty-bank-hardware-owner-authorization-2026-10-18-r1.json';assert r.read(auth)['owner_authorized']
    source=banks(Q/'bf1-2609-windows-beta4-offline-2026-10-18-r2/beta4-to-bf1')
    stock=(Q/'board-2609-restore-2026-09-30/b0-source.bin').read_bytes()
    assert r.sha(stock)=='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
    info,staged,cfg,counts,seq=stock_fixture(source,stock,OUT/'2609-stage-empty-WDC')
    cap=OUT/'2609-WDC-source';capture(cap,staged,'2609')
    history=OUT/'2609-history.json';save(history,dict(schema=1,board='2609',config=cfg.hex(),counts=counts,sequence=seq))
    meta=OUT/'2609-metadata.bin';meta.write_bytes(source[3][0x1c00:0x2000])
    full=f.prepare(cap,KIT,OUT/'2609-WDC-to-full-bf1',history,meta);f.validate_plan(OUT/'2609-WDC-to-full-bf1',KIT)
    # The private staging operation alone is allowed to erase B0. Public upgrades preserve B0.
    text=inspect.getsource(r.transaction).replace('def transaction(', 'def fixture_transaction(')
    text=text.replace("    require(banks[0] == destination[0], 'B0 replacement forbidden')\n",'')
    assert text.count('for bank in range(1, 4):')==1;text=text.replace('for bank in range(1, 4):','for bank in range(0, 4):')
    scope=dict(r.__dict__);exec(text,scope);fixture_transaction=scope['fixture_transaction']
    source=[(Q/f'bf1-2604-hardware-2026-10-17/A-checks/after-checks-b{n}.bin').read_bytes() for n in range(4)]
    receipt=r.read(Q/'bf1-2604-hardware-2026-10-17/A-checks/report.json');assert r.hashes(source)==receipt['expected_hashes']
    desired=list(source);desired[0]=b'\xff'*32768;row=r.clean_journal(source)[2]
    tx,data,empty0=fixture_transaction(source,desired,row[8:24],'Private owner-authorized B0 erase on 2604')
    inf=r.compose(KIT/'template',OUT/'2604-empty-B0',source,tx,data,empty0);inf.update(board='2604',route='private-empty-B0-fixture');save(OUT/'2604-empty-B0/plan.json',inf)
    desired=[b'\xff'*32768]*3+[b'\xff'*32768];desired=list(map(bytearray,desired))
    from beta4_migration import maintenance_storage
    desired[3][:8192]=maintenance_storage(ROOT/'BUILD/v2-beta4/kit')
    archive=ROOT/'output/release/str8n-v2-b4.zip';assert sha(archive)=='4c25bc576cbc32efd04aeea4fe80c68544a50b80685d12bfcf1e44122bacbc14'
    with zipfile.ZipFile(archive) as z:
        for off,name in ((0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')):desired[3][off:off+4096]=z.read(f'str8n-v2-b4-{name}.bin')
    row=r.clean_journal(empty0)[2]
    tx,data,staged=r.transaction(empty0,list(map(bytes,desired)),r.preference(row[8:24],0xa0,13),'Private beta4 B3 with empty B0/B1/B2')
    inf=r.compose(KIT/'template',OUT/'2604-stage-empty-beta4',empty0,tx,data,staged);inf.update(board='2604',route='private-empty-beta4-fixture');save(OUT/'2604-stage-empty-beta4/plan.json',inf)
    assert staged[:3]==[b'\xff'*32768]*3
    cap=OUT/'2604-beta4-source';capture(cap,staged,'2604')
    meta=OUT/'2604-metadata.bin';meta.write_bytes(source[3][0x1c00:0x2000])
    final=m.prepare_beta4(cap,KIT,OUT/'2604-beta4-to-full-bf1',meta);m.validate_beta4_plan(OUT/'2604-beta4-to-full-bf1',KIT)
    for name in ['2609-WDC-to-full-bf1','2604-beta4-to-full-bf1']:
        target=banks(OUT/name)
        assert target[0]==b'\xff'*32768 and target[1][:4]==b'SR\1?' and b'UCHESS\0' in target[1]
        for seg in r.read(KIT/'layout.json')['segments']:
            off=seg['address']-0x8000;body=(KIT/'payload'/seg['file']).read_bytes()[seg['offset']:seg['offset']+seg['bytes']]
            assert target[seg['bank']][off:off+len(body)]==body
    names=['2609-stage-empty-WDC','2609-WDC-to-full-bf1','2604-empty-B0','2604-stage-empty-beta4','2604-beta4-to-full-bf1']
    save(OUT/'preparation.json',dict(passed=True,board_access=False,kit=str(KIT),kit_manifest_sha256=sha(KIT/'kit-manifest.json'),owner_authorization_sha256=sha(auth),plans={n:sha(OUT/n/'plan.json') for n in names},empty_bank_sources_verified=True,UCHESS_and_all_layout_segments_verified=True,CPU_execution_qualified=False,hardware_qualified=False))
    print('PASS five prepared exact empty-bank staging/full-system plans; fresh CPU tests required')

if __name__=='__main__':main()
