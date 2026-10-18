"""Fresh A-install/committed-header cut/recovery models after recovered bf1 B."""
import argparse,json,hashlib
from pathlib import Path
import plan_bf1_2609_route as route
import bf1_offline_recovery_model as harness
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    backup=read(a.backup/'report.json');cp=G/'power-cut-1/checkpoint.json';assert backup['passed'] and read(cp)['passed'] and backup['parent_checkpoint_sha256']==sha(cp)
    assert backup['application_ram_restored'] and not read(a.backup/'restore-needed.json')['needed']
    for name,item in backup['files'].items():assert sha(a.backup/name)==item['sha256']
    source=[(a.backup/f'b{i}.bin').read_bytes() for i in range(4)]
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json');image=ROOT/'tmp/bfx5/payload/str8n-v2-recovery-slot-a0.bin'
    assert sha(image)==pin['artifacts']['str8n-v2-recovery-slot-a0.bin']['sha256']
    desired=list(map(bytearray,source));desired[3][0x2000:0x3000]=image.read_bytes()
    cfg=route.c.latest(source)[2][8:24]
    tx,data,target=route.transaction(source,desired,fallback_page=0xb0,target_config=route.j.preference(cfg,0xa0,48),label='A bf1 after physically recovered and checked B bf1')
    assert len(tx['planned_erase_order'])==3
    assert not a.out.exists();a.out.mkdir()
    harness.route=route;harness.c=route.c;harness.p=route.p;harness.j=route.j
    d=harness.Driver(a.out,a.backup,ROOT/'tmp/bfr2')
    complete,info=d.execute('install-A-after-recovered-B',source,tx,data,target)
    erases=[i for i,e in enumerate(complete.events) if e[0]=='erase'];assert len(erases)==3
    prefix=[list(e) for e in complete.events[:erases[2]]]
    cut,_=d.execute('committed-A-before-activation-cut',source,tx,data,target,cut=len(prefix));current=list(map(bytes,cut.banks))
    assert route.p.bank_hashes(current)==tx['operations'][-2]['proposed_bank_sha256']
    assert route.c.latest(current)[2][16]==0xb0 and current[3][0x2000:0x3000]==image.read_bytes()
    route.attest_recovery(current,source,events=prefix,info=info,certificate=route.p.bank_hashes(current))
    recovery_tx,recovery_data,recovered=route.transaction(current,target,fallback_page=0xb0,target_config=route.c.latest(target)[2][8:24],label='Recover committed A bf1 with B bf1 retained',attestation=route.p.bank_hashes(current))
    assert not any(op['kind']=='payload-sector' for op in recovery_tx['operations'])
    d.execute('committed-A-boundary-recovery',current,recovery_tx,recovery_data,recovered)
    for i,b in enumerate(current):(a.out/f'expected-cut-b{i}.bin').write_bytes(b)
    sources={str(p.resolve()):sha(p) for p in (Path(__file__),Path(route.__file__),Path(route.c.__file__),Path(harness.__file__))}
    route_report=dict(passed=True,phase='A',cases=3,backup_report_sha256=sha(a.backup/'report.json'),first_hardware_case_checkpoint_sha256=sha(cp),
                      source_sha256=route.p.bank_hashes(source),expected_complete_sha256=route.p.bank_hashes(target),sources=sources,
                      scope='Three fresh exact-current-byte CPU transactions: complete A, committed A before activation cut, and wear-aware journal-only recovery. Prior unchanged utility/BATCH/ABI checks are reused explicitly.',model_processor='W65C02',board_access=False,release_qualified=False)
    (a.out/'route-report.json').write_text(json.dumps(route_report,indent=2)+'\n')
    result=dict(passed=True,phase='A',board='2609',route_report_sha256=sha(a.out/'route-report.json'),backup_report_sha256=sha(a.backup/'report.json'),
                installer_sha256=info['installer_sha256'],transfer_sha256=info['transfer_sha256'][:2],
                cut_boundary='After second transfer and A48 header commit, awaiting final journal activation; no final transfer bytes sent',
                next_send_token=f"SEND 4096 BYTES FOR B{info['steps'][2][0]}:{info['steps'][2][1]:X}\r\n",
                expected_cut_hashes=route.p.bank_hashes(current),prefix_events=len(prefix),prefix_events_sha256=sha(a.out/'committed-A-before-activation-cut/events.json'),
                fallback_page=0xb0,A48_committed_before_cut=True,recovery_model_passed=True,recovery_reerases_A_payload=False,
                model_processor='W65C02',fresh_transactions=3,physical_interruption_performed=False,physical_interruption_qualified=False,
                no_board_access=True,release_qualified=False,installation_permitted=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS fresh A48 commit-boundary and journal-only recovery models',flush=True)
if __name__=='__main__':main()
