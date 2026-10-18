"""Run only the admitted actual-cut recovery; halt for owner's physical RESET."""
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
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1';CUT=G/'power-cut-1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    admission_path=CUT/'recovery-admission.json';admission=read(admission_path);assert admission['passed'] and admission['actual_interrupted_flash_matches_exact_model']
    assert read(CUT/'owner-power-on-confirmation.json')['event']=='controlled_power_on_user_confirmed'
    capture=CUT/'return-capture';receipt=read(capture/'report.json');assert receipt['passed'] and receipt['application_ram_restored'] and receipt['ports_released']
    assert sha(capture/'report.json')==admission['capture_report_sha256'] and not read(capture/'restore-needed.json')['needed']
    for name,item in receipt['files'].items():assert sha(capture/name)==item['sha256']
    plan_path=Path(admission['recovery_plan']);assert sha(plan_path)==admission['recovery_plan_sha256'];plan=read(plan_path);source=plan_path.parent
    assert plan['source_sha256']==admission['source_hashes'] and plan['expected_sha256']==admission['expected_recovery_hashes']
    assert [sha(capture/f'b{i}.bin') for i in range(4)]==plan['source_sha256']
    proof=read(G/'stable-boundary-proof-r2/report.json');assert proof['passed'] and proof['recovery_model_passed']
    snap=read(a.snapshot);assert snap['passed'] and len(snap['boards'])==1 and snap['boards'][0]['board']=='2609' and snap['boards'][0]['application_ram_restored']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    assert sha(source/'installer-model-only.s19')==plan['installer_sha256']
    transfers=[]
    for i,digest in enumerate(plan['transfer_sha256']):
        p=source/f'transfer-{i:02d}.bin';assert sha(p)==digest and p.stat().st_size==4096;transfers.append(p.read_bytes())
    cells,entry=read_s19(source/'installer-model-only.s19');assert entry==0x2000
    if a.check_only:print('PASS actual-cut capture, PF journal, exact recovery model and fresh RTC snapshot admitted; no port opened');return
    marker=Q/'device-operations/2609.json';guard=read(marker);assert guard['state']=='cut-recovery-authorized' and guard['block_snapshot'] and guard['admission_sha256']==sha(admission_path)
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==snap['boards'][0]['port']
    a.out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,a.out/'pinned-model-inputs');shutil.copyfile(Path(__file__),a.out/'recovery-runner.py')
    report=dict(board='2609',case='power-cut-1-recovery-to-bf1-B',port=port,passed=False,started_utc=datetime.now(timezone.utc).isoformat(),
                admission_sha256=sha(admission_path),capture_report_sha256=sha(capture/'report.json'),snapshot_sha256=sha(a.snapshot),
                source_hashes=plan['source_sha256'],expected_hashes=plan['expected_sha256'],installer_sha256=plan['installer_sha256'],
                transfers_completed=0,clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,automatic_reset=False,
                physical_interruption_recovery_completed=False,release_qualified=False)
    save=lambda:publish(a.out/'report.json',report)
    save();publish(marker,dict(board='2609',state='installing',case=report['case'],run=str(a.out.resolve()),block_snapshot=True))
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);text=link.command('VERSION');(a.out/'version-before.txt').write_bytes(text)
            assert b'65C816' in text and b'Board: 2609' in text and b'Running: MONITOR A, gen 00000028' in text
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
                assert hashlib.sha256(data).hexdigest()==plan['source_sha256'][bank];print('PASS actual recovery preimage',bank,flush=True)
            link.command('B3');original=(capture/'application-ram-original.bin').read_bytes()
            actual=b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096));assert actual==original
            restore_source=G/'post-restoration-backup/restore-application-ram.s19'
            publish(a.out/'restore-needed.json',dict(needed=True,first=512,last=0x64ff,source=str(restore_source.resolve()),sha256=sha(G/'post-restoration-backup/application-ram-original.bin'),cold_boot_RAM_backup=str((capture/'application-ram-original.bin').resolve())))
            report['cpu_mode_before']=live.cpu_mode(link,a.out,'cpu-mode-before');save()
            assert load_image(link,source/'installer-model-only.s19')==hashlib.sha256(bytes(cells[n] for n in range(min(cells),max(cells)+1))).hexdigest()
            (a.out/'title.txt').write_bytes(link.command('G 2000',b'Y then Enter> '));link.send(b'Y\r');report['transaction_started']=True;save()
            for i,((bank,sector),body) in enumerate(zip(plan['steps'],transfers)):
                link.until(f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode(),90)
                for off in range(0,4096,64):link.send(body[off:off+64]);time.sleep(.01)
                report['transfers_completed']=i+1;save();print('TRANSFER recovery',i+1,bank,sector,flush=True)
            text=link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90);(a.out/'result.txt').write_bytes(text)
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
            publish(marker,dict(board='2609',state='reset-required',case=report['case'],run=str(a.out.resolve()),block_snapshot=True));print('PASS cut-state recovery transaction verified; PHYSICAL RESET REQUIRED',flush=True)
        except BaseException:
            report.update(failure=traceback.format_exc(),needs_inspection=True);save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()
if __name__=='__main__':main()
