"""Owner-private exact WDCMONV2/beta4 fixtures and direct v1g trial plans.

Vendor bytes, owner metadata, full-bank/RAM escrows and plans NEVER ship. No
ports. Source staging is qualification apparatus, not an end-user upgrade hop.
Generation49 is never installed or used as a rollback intermediate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('run','kit','backup'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--board',choices=('2604','2609'),required=True);a=ap.parse_args()
    run,kit,backup=a.run.resolve(),a.kit.resolve(),a.backup.resolve();assert run.is_relative_to(Q)
    auth=READ(run/'owner-authorization.json');assert auth['fixture_staging_authorized'] and auth['physical_RESET_assistance_confirmed'] and a.board in auth['boards']
    proof=READ(backup/'report.json');assert proof['passed'] and proof['flash_repeat_verified'] and proof['eeprom_repeat_verified'] and proof['SRAM_repeat_verified'] and proof['RAM_restored']
    sys.path[:0]=[str(kit),str(kit/'engine')]
    import uniform_upgrade as u
    import bootstrap_routes as b
    import runtime as r
    from rc1_uniform_cpu_model import execute
    u.package(kit);out=run/a.board/'trials';assert not out.exists();out.mkdir();(out/'.gitignore').write_text('*\n')
    identity,original=u.read_capture(backup/'capture');assert identity['board']==a.board
    assert r.hashes(original)==proof['all_four_bank_sha256'] and original[0]==b'\xff'*32768
    assert u.identify(kit,u.package(kit),original)=='v1g'
    ram=(backup/'capture/application-ram.bin').read_bytes()
    def capture(path,banks):
        path.mkdir();files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
        for name,body in [('application-ram.bin',ram),('restore-application-ram.s19',r.migration.s19(dict(enumerate(ram,0x200)),0x200))]:
            (path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=r.sha(body))
        u.legacy.save(path/'capture.json',dict(schema=1,board=a.board,usb_serial=identity['usb_serial'],repeat_verified=True,model_fixture=True,files=files))
    metadata=out/'private-metadata-escrow.bin';metadata.write_bytes(original[3][0x1c00:0x2000])
    vendor=(Q/'board-2512-layout-2026-09-24/b0-final.bin' if a.board=='2604' else Q/'bf1-2609-windows-offline-2026-10-18-r1/model-only-WDC-capture/b3.bin').read_bytes()
    desired=[original[0],b'\xff'*32768,b'\xff'*32768,vendor]
    assert b.identify(kit,desired)==('wdcmonv2-65C02' if a.board=='2604' else 'wdcmonv2-65C816')
    seq,offset,row,valid=r.clean_journal(original);cfg=row[8:24];retained=offset//4096+8;other=25-retained
    free=next(i for i in range((retained-8)*4096,(retained-7)*4096,128) if original[3][i:i+128]==b'\xff'*128)
    lower=[(bank,sector) for bank in (1,2) for sector in range(15,7,-1) if original[bank][(sector-8)*4096:(sector-7)*4096]!=b'\xff'*4096]
    order=[(3,other)]+lower+[(3,n) for n in (8,9,10,11,14)]+[(3,retained),(3,15)]
    assert len(order)<=24 and len(order)==len(set(order))
    before=[max(int.from_bytes(v[24+3*i:27+3*i],'little') for _,_,v in valid) for i in range(32)];counts=list(before)
    for bank,sector in order:
        index=bank*8+sector-8;assert counts[index]<0xffffff;counts[index]+=1
    state=list(map(bytearray,original));ops=[];data=[]
    def append(kind,bank,address,body,commit=None):
        old=r.hashes(state);off=address-0x8000;state[bank][off:off+len(body)]=body
        ops.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,source_sha256=old,after_sha256=r.hashes(state),data_sha256=r.sha(body)));data.append(body)
    append('reserve-private-fixture-attempts',3,free+0x8000,r.record(cfg,counts,seq+1),free+0x807f)
    for bank,sector in order:append('private-fixture-sector',bank,sector<<12,desired[bank][(sector-8)*4096:(sector-7)*4096])
    assert list(map(bytes,state))==desired
    tx=dict(label='Private owner qualification WDC fixture',source_sha256=r.hashes(original),expected_sha256=r.hashes(desired),operations=ops,
        counts_before=before,reserved_counts=counts,sequence_before=seq,sequence_after=seq+1,reservation_offset=free,
        retained_journal_sector=retained,planned_erase_order=[list(v) for v in order],source_config=cfg.hex(),target_config=cfg.hex(),model_only=True,installation_permitted=False)
    info=r.compose(kit/'engine/template',out/'stage-wdc',original,tx,data,desired)
    info.update(board=a.board,usb_serial=identity['usb_serial'],private_vendor_payload=True,public_distribution_permitted=False)
    u.legacy.save(out/'stage-wdc/plan.json',info)
    history=out/'tracked-history.json';u.legacy.save(history,dict(schema=1,board=a.board,config=cfg.hex(),counts=counts,sequence=seq+1,
        origin='Private escrow carries every reserved fixture erase; no lifetime-wear claim'))
    capture(out/'wdc-source',desired)
    wdc=u.prepare(kit,out/'wdc-source',out/'migrate-wdc',history=history,metadata_escrow=metadata)
    after_wdc=[(out/'migrate-wdc'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    # Reconstruct the published beta4 core while restoring original user extents
    # outside the declared provider/debugger destinations from the fresh escrow.
    beta=list(map(bytearray,original));b4=ROOT/'BUILD/v2-beta4/kit'
    for s in r.read(kit/'migration/layout.json')['segments']:
        if s['bank'] in (1,2):
            off=s['address']-0x8000;beta[s['bank']][off:off+s['bytes']]=b'\xff'*s['bytes']
    beta[3][:]=b'\xff'*32768;beta[3][:8192]=(b4/'str8n-v2-b4-maint-8000-9fff.bin').read_bytes()
    for off,name in [(0x2000,'slot-a'),(0x3000,'slot-b'),(0x6000,'e000-efff'),(0x7000,'f000-ffff')]:beta[3][off:off+4096]=(b4/f'str8n-v2-b4-{name}.bin').read_bytes()
    tx2,data2,expected_beta=r.transaction(after_wdc,list(map(bytes,beta)),r.preference(cfg,cfg[8] if cfg[7]==ord('P') else 0xb0,13),'Private owner qualification beta4 fixture')
    info2=r.compose(kit/'engine/template',out/'stage-beta4',after_wdc,tx2,data2,expected_beta);info2.update(board=a.board,usb_serial=identity['usb_serial'])
    u.legacy.save(out/'stage-beta4/plan.json',info2);capture(out/'beta4-source',expected_beta)
    final=u.prepare(kit,out/'beta4-source',out/'migrate-beta4',metadata_escrow=metadata)
    target=[(out/'migrate-beta4'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert all(target[n]==original[n] for n in (0,1,2))
    assert target[3][:0x4000]==original[3][:0x4000] and target[3][0x6000:]==original[3][0x6000:]
    assert r.latest(target)[2][8:24]==cfg
    checks=[]
    for name,initial,stock,fixture in [('stage-wdc',original,False,True),('migrate-wdc',desired,True,False),('stage-beta4',after_wdc,False,False),('migrate-beta4',expected_beta,False,False)]:
        result=execute(kit,out/name,initial,is816=a.board=='2609',stock=stock,private_fixture=fixture)
        checks.append(dict(name=name,plan_sha256=SHA(out/name/'plan.json'),installer_sha256=SHA(out/name/'installer-model-only.s19'),**result));print('PASS',a.board,name,'exact private CPU trial',flush=True)
        u.legacy.save(out/'progress.json',checks)
    u.legacy.save(out/'report.json',dict(passed=True,board=a.board,checks=checks,board_access=False,
        original_backup_report_sha256=SHA(backup/'report.json'),uniform_manifest_sha256=SHA(kit/'uniform-manifest.json'),
        source_sha256={str(p):SHA(p) for p in (Path(__file__),ROOT/'tools/rc1_uniform_cpu_model.py')},
        final_original_flash_except_wear_journals=True,final_original_settings=True,native_debugging=False,RTC_drift_in_release_qualification=False,
        intermediate_generation49=False,private_vendor_fixture=True,public_distribution_permitted=False))


if __name__=='__main__':main()
