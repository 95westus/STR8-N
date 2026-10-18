"""Stage committed A48 before activation; retain proven bf1 B; owner operates power."""
import argparse,hashlib,json,shutil,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from qualify_v2_spi_install import load_image
from atomic_json import publish
import bf1_2609_readonly as live
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--route',type=Path,required=True);ap.add_argument('--boundary',type=Path,required=True)
    ap.add_argument('--rtc-boot-proof',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    assert read(G/'owner-authorization.json')['owner_power_and_reset_actions_only']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    checkpoint=read(G/'original-restoration-checkpoint.json');assert checkpoint['passed'] and checkpoint['original_payload_restoration_hardware_passed']
    route_report_path=a.route/'route-report.json';route_report=read(route_report_path);assert route_report['passed'] and route_report['cases']==3 and route_report['phase']=='A'
    first_case=G/'power-cut-1/checkpoint.json';assert read(first_case)['passed'] and route_report['first_hardware_case_checkpoint_sha256']==sha(first_case)
    for name,digest in route_report['sources'].items():assert sha(Path(name))==digest
    proof=read(a.boundary/'report.json');assert proof['passed'] and proof['recovery_model_passed'] and proof['fallback_page']==0xb0 and proof['A48_committed_before_cut']
    assert proof['route_report_sha256']==sha(route_report_path) and proof['backup_report_sha256']==sha(a.backup/'report.json')
    rtc_proof=read(a.rtc_boot_proof);assert rtc_proof['passed'] and rtc_proof['boundary_report_sha256']==sha(a.boundary/'report.json')
    snap=read(a.snapshot);assert snap['passed'] and len(snap['boards'])==1 and snap['boards'][0]['board']=='2609' and snap['boards'][0]['application_ram_restored']
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(snap['boards'][0]['reference_utc'].replace('Z','+00:00'))).total_seconds();assert 0<=age<14400
    backup=read(a.backup/'report.json');assert backup['passed'] and backup['application_ram_restored'] and not read(a.backup/'restore-needed.json')['needed']
    for name,item in backup['files'].items():assert sha(a.backup/name)==item['sha256']
    source=a.route/'install-A-after-recovered-B';plan=read(source/'plan.json')
    assert [sha(a.backup/f'b{i}.bin') for i in range(4)]==plan['source_sha256']
    assert sha(source/'installer-model-only.s19')==proof['installer_sha256']==plan['installer_sha256']
    bodies=[]
    for i,digest in enumerate(proof['transfer_sha256']):
        path=source/f'transfer-{i:02d}.bin';assert path.stat().st_size==4096 and sha(path)==digest==plan['transfer_sha256'][i];bodies.append(path.read_bytes())
    assert len(bodies)==2 and proof['next_send_token']==f"SEND 4096 BYTES FOR B{plan['steps'][2][0]}:{plan['steps'][2][1]:X}\r\n"
    for bank,digest in enumerate(proof['expected_cut_hashes']):assert sha(a.boundary/f'expected-cut-b{bank}.bin')==digest
    if a.check_only:print('PASS exact stable-boundary staging inputs; no board opened');return
    marker=Q/'device-operations/2609.json';guard=read(marker);assert guard['state']=='power-boundary-authorized' and guard['block_snapshot']
    assert guard['boundary_proof_sha256']==sha(a.boundary/'report.json')
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==snap['boards'][0]['port']
    a.out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,a.out/'pinned-model-inputs');shutil.copyfile(Path(__file__),a.out/'staging-runner.py')
    result=dict(board='2609',passed=False,state='staging',port=port,started_utc=datetime.now(timezone.utc).isoformat(),
                authorization_sha256=sha(G/'owner-authorization.json'),route_report_sha256=sha(route_report_path),
                boundary_proof=str((a.boundary/'report.json').resolve()),boundary_proof_sha256=sha(a.boundary/'report.json'),
                backup=str(a.backup.resolve()),backup_report_sha256=sha(a.backup/'report.json'),snapshot_sha256=sha(a.snapshot),rtc_boot_proof_sha256=sha(a.rtc_boot_proof),
                source_hashes=plan['source_sha256'],expected_cut_hashes=proof['expected_cut_hashes'],
                cut_hashes_predicted_not_yet_read_back=True,physical_power_interruption_performed=False,
                clock_trim_changed=False,EEPROM_SRAM_written=False,automatic_reset=False,release_qualified=False)
    save=lambda:publish(a.out/'report.json',result)
    save();publish(marker,dict(board='2609',state='installing',run=str(a.out.resolve()),block_snapshot=True))
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);version=link.command('VERSION');(a.out/'version-before.txt').write_bytes(version)
            assert b'2.0bf1' in version and b'Running: MONITOR B' in version and b'65C816' in version and b'Board: 2609' in version
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert hashlib.sha256(data).hexdigest()==plan['source_sha256'][bank];print('PASS current preimage',bank,flush=True)
            link.command('B3');original=(a.backup/'application-ram-original.bin').read_bytes()
            actual=b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096));assert actual==original
            publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest(),source=str((a.backup/'restore-application-ram.s19').resolve())))
            result['cpu_mode_before']=live.cpu_mode(link,a.out,'cpu-mode-before');save()
            cells,entry=read_s19(source/'installer-model-only.s19');assert entry==0x2000
            assert load_image(link,source/'installer-model-only.s19')==hashlib.sha256(bytes(cells[n] for n in range(min(cells),max(cells)+1))).hexdigest()
            (a.out/'title.txt').write_bytes(link.command('G 2000',b'Y then Enter> '));link.send(b'Y\r');result['transaction_started']=True;save()
            for i,body in enumerate(bodies):
                bank,sector=plan['steps'][i];link.until(f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode(),90)
                for off in range(0,4096,64):link.send(body[off:off+64]);time.sleep(.01)
                result['transfers_completed']=i+1;save();print('TRANSFER A',i+1,bank,sector,flush=True)
            token=link.until(proof['next_send_token'].encode(),90);(a.out/'committed-A-boundary-token.txt').write_bytes(token)
            result.update(passed=True,state='awaiting-owner-power-off',transfers_completed=2,next_transfer_bytes_sent=0,
                          protocol_boundary_reached=True,awaiting_owner_action=True,boundary_reached_utc=datetime.now(timezone.utc).isoformat())
            save();publish(marker,dict(board='2609',state='awaiting-power-off',run=str(a.out.resolve()),block_snapshot=True))
            print('PASS A48 commit boundary reached; final activation transfer not sent; OWNER POWER-OFF REQUIRED',flush=True)
        except BaseException:
            result.update(failure=traceback.format_exc(),needs_inspection=True);save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()
if __name__=='__main__':main()
