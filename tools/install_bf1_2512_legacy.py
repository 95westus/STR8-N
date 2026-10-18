"""Receipt-bound 2512 historical source staging. Halts for owner RESET; no automatic reset."""
import argparse,json,time,traceback,hashlib
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def validate(source,backup,checkpoint):
    cp=read(checkpoint);assert cp['offline_qualified'] and cp['board']=='2512'
    for item in cp['evidence'].values():assert sha(Path(item['path']))==item['sha256'] and read(Path(item['path']))['passed']
    provenance=Path(cp['source_provenance']);assert sha(provenance)==cp['source_provenance_sha256']
    for name,digest in read(provenance)['files'].items():assert sha(Path(name))==digest
    assert sha(Path(cp['hardware_review']))==cp['hardware_review_sha256']
    review=read(Path(cp['hardware_review']));phase=next(p for p in review['phases'] if p['phase']=='wdcmonv2-stage-source')
    assert str((source/'plan.json').resolve())==phase['plan'] and sha(source/'plan.json')==phase['plan_sha256']
    plan=read(source/'plan.json');assert sha(source/'installer-model-only.s19')==plan['installer_sha256']==phase['installer_sha256']
    b=read(backup/'report.json');assert b['passed'] and b['application_ram_restored'] and b['flash_repeat_verified'] and b['eeprom_repeat_verified'] and b['sram_repeat_verified']
    assert not read(backup/'restore-needed.json')['needed']
    for name,item in b['files'].items():assert sha(backup/name)==item['sha256']
    assert [sha(backup/f'b{n}.bin') for n in range(4)]==plan['source_sha256']
    assert all(sha(source/f'source-b{n}.bin')==plan['source_sha256'][n] and sha(source/f'expected-b{n}.bin')==plan['expected_sha256'][n] for n in range(4))
    transfers=[]
    for n,op in enumerate(plan['transaction']['operations'][1:]):
        data=(source/f'transfer-{n:02d}.bin').read_bytes();assert len(data)==4096
        committed=bytearray(data)
        if op['commit_address'] is not None:committed[op['commit_address']-op['address']]=(source/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(committed).hexdigest()==op['data_sha256'];transfers.append(data)
    cells,entry=read_s19(source/'installer-model-only.s19');assert min(cells)==entry==0x2000 and max(cells)==0x36ff
    return plan,transfers
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    source=Q/'bf1-2512-legacy-offline-2026-10-17-r6/wdcmonv2-stage-source';cp=Q/'bf1-2512-legacy-offline-checkpoint-2026-10-17-r1.json'
    plan,transfers=validate(source,a.backup,cp)
    auth=read(Q/'bf1-2512-hardware-owner-authorization-2026-10-17-r1.json');assert auth['hardware_qualification_authorized'] and auth['board']=='2512' and auth['offline_checkpoint_sha256']==sha(cp)
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and active['baseline_index_sha256']==read(cp)['baseline_sha256']
    if a.check_only:print('PASS fresh full backup, exact qualified source/installer/transfers and owner authorization; no port opened');return
    assert (datetime.now(timezone.utc)-datetime.fromisoformat(read(a.backup/'report.json')['finished_utc'])).total_seconds()<1800, 'Take a fresh preserving backup'
    assert not a.out.exists();a.out.mkdir(parents=True);marker=Q/'device-operations/2512.json'
    with serial_lease('bf1-register-2512',timeout=600,priority=True):
        assert not read(marker).get('block_snapshot');publish(marker,dict(board='2512',state='installing-historical-source',run=str(a.out.resolve()),block_snapshot=True))
    report=dict(board='2512',phase='wdcmonv2-stage-source',passed=False,owner_authorized=True,authorization_sha256=sha(Q/'bf1-2512-hardware-owner-authorization-2026-10-17-r1.json'),offline_checkpoint_sha256=sha(cp),plan=str(source/'plan.json'),plan_sha256=sha(source/'plan.json'),fresh_backup=str(a.backup.resolve()),fresh_backup_sha256=sha(a.backup/'report.json'),clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,started_utc=datetime.now(timezone.utc).isoformat(),transfers_completed=0)
    def save():publish(a.out/'report.json',report)
    save();link=None
    with (a.out/'serial.jsonl').open('x') as log:
      try:
        ports=[p for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1;link=Link(ports[0].device,log);establish_b3(link)
        version=link.command('VERSION');assert b'2.0b35' in version and b'Board: 2512' in version;(a.out/'version-before.txt').write_bytes(version)
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'preflight-b{bank}.bin').write_bytes(data)
            assert hashlib.sha256(data).hexdigest()==plan['source_sha256'][bank],f'B{bank} changed: execution forbidden';print('PASS current source',bank,flush=True)
        link.command('B3');original=(a.backup/'application-ram-original.bin').read_bytes();actual=b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096));assert actual==original
        publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest(),source=str((a.backup/'application-ram-original.bin').resolve()),first=512,last=0x64ff))
        link.monitor_load(source/'installer-model-only.s19');link.until(b'Y then Enter> ');link.send(b'Y\r');report['transaction_started']=True;save()
        for n,(op,data) in enumerate(zip(plan['transaction']['operations'][1:],transfers)):
            link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
            for off in range(0,4096,64):link.send(data[off:off+64]);time.sleep(.01)
            report['transfers_completed']=n+1;save();print('TRANSFER',n+1,op['bank'],hex(op['address']),flush=True)
        (a.out/'result.txt').write_bytes(link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90))
        report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save();publish(marker,dict(board='2512',state='reset-required-historical-wdc',run=str(a.out.resolve()),block_snapshot=True));print('PASS historical WDC source staged; RESET requires armed stock debugger',flush=True)
      except BaseException:
        report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:
        if link:link.serial.close()
if __name__=='__main__':main()
