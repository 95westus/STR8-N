"""2609 Windows beta4 tools, with owner-requested host readbacks disabled."""
import argparse,json,hashlib,time,traceback,sys
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',required=True,type=Path);p.add_argument('--plans',required=True,type=Path)
    p.add_argument('--phase',required=True,choices=('stage-beta4','beta4-to-bf1'))
    p.add_argument('--prior-boot',required=True,type=Path);p.add_argument('--prior-install',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    sys.path.insert(0,str(a.kit.resolve()));import migrate;import legacy_transport as wire
    migrate.verify_kit(a.kit)
    proof=read(a.plans/'CPU-report.json');prep=read(a.plans/'preparation.json')
    assert proof['passed'] and proof['cases']==2 and proof['preparation_sha256']==sha(a.plans/'preparation.json')
    assert prep['kit_manifest_sha256']==sha(a.kit/'kit-manifest.json')
    folder=a.plans/a.phase;plan=read(folder/'plan.json')
    case=next(c for c in proof['checks'] if c['name']==a.phase)
    assert case['passed'] and case['fresh_CPU_execution'] and case['plan_sha256']==sha(folder/'plan.json')
    assert case['installer_sha256']==sha(folder/'installer-model-only.s19')==plan['installer_sha256']
    for n in range(4):
        assert sha(folder/f'source-b{n}.bin')==plan['source_sha256'][n]
        assert sha(folder/f'expected-b{n}.bin')==plan['expected_sha256'][n]
    if a.phase=='beta4-to-bf1':migrate.validate_beta4_plan(folder,a.kit)
    prior=read(a.prior_boot/'report.json');installed=read(a.prior_install/'report.json')
    assert prior['passed'] and prior['boot_identity_verified'] and prior['board']=='2609'
    assert installed['passed'] and installed['transaction_device_verified'] and prior['install_report_sha256']==sha(a.prior_install/'report.json')
    rebase=None
    if installed['expected_hashes']!=plan['source_sha256']:
        assert a.phase=='stage-beta4'
        rebase=read(Q/'bf1-2609-BA-metadata-rebase-2026-10-18-r1/report.json')
        assert rebase['passed'] and rebase['all_sector_CRCs_match'] and rebase['normal_wear_counts_unchanged']
        assert rebase['base_expected_sha256']==installed['expected_hashes']
        assert rebase['derived_expected_sha256']==plan['source_sha256']
        assert rebase['append_bytes']==32 and rebase['new_stage']==3
        # The existing complete bank FNV preflight is retained. This narrow
        # candidate never waives a mismatch before the first flash mutation.
    version='2.0bf1' if a.phase=='stage-beta4' else '2.0b4'
    assert prior['version']==version
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['block_snapshot']
    if rebase:
        assert guard['state']=='inspection-required' and guard['rtc_continuity_broken']
        assert read(Q/'bf1-2609-normal-status-2026-10-18-r1/report.json')['passed']
    else:
        assert guard['state']=='windows-flash-boot-checked' and Path(guard['run']).resolve()==a.prior_boot.resolve()
    assert set(read(Q/'active-rtc-campaign.json')['powered_off_boards'])=={'2205','2512'}
    assert read(Q/'bf1-2609-windows-flash-only-owner-instruction-2026-10-18-r1.json')['extra_host_readbacks'] is False
    transfers=[]
    for n,op in enumerate(plan['transaction']['operations'][1:]):
        data=(folder/f'transfer-{n:02d}.bin').read_bytes();assert len(data)==4096
        body=bytearray(data)
        if op['commit_address'] is not None:body[op['commit_address']-op['address']]=(folder/f"expected-b{op['bank']}.bin").read_bytes()[op['commit_address']-0x8000]
        assert hashlib.sha256(body).hexdigest()==op['data_sha256'];transfers.append(data)
    cells,entry=wire.read_s19(folder/'installer-model-only.s19');assert entry==min(cells)==0x2000 and max(cells)<0x3800
    if a.check_only:print('PASS exact model, prior boot/device result, plan and local payload pins; no port opened');return
    assert not a.out.exists();a.out.mkdir(parents=True)
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']];assert len(ports)==1
    report=dict(board='2609',phase='A',case=a.phase,port=ports[0].device,passed=False,
        expected_hashes=plan['expected_sha256'],plan_sha256=sha(folder/'plan.json'),CPU_proof_sha256=sha(a.plans/'CPU-report.json'),
        kit_manifest_sha256=sha(a.kit/'kit-manifest.json'),host_memory_readbacks=False,protocol_acknowledgments=True,
        device_verification_retained=True,physical_reset_pending=False,transfers_completed=0,
        clock_trim_settings_changes=False,EEPROM_SRAM_written=False,application_RAM_restoration_pending=True,
        started_utc=datetime.now(timezone.utc).isoformat(),publication_permitted=False)
    def save():publish(a.out/'report.json',report)
    save();publish(marker,dict(board='2609',state='windows-migration-installing',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
    original=Q/'2609-windows-migration-backup-2026-10-18-r1/application-ram-original.bin'
    publish(a.out/'restore-needed.json',dict(needed=True,verified=False,source=str(original.resolve()),sha256=sha(original)))
    with (a.out/'serial.jsonl').open('x') as log:
        link=wire.Link(ports[0].device,log)
        try:
            establish_b3(link);text=link.command('P' if version=='2.0b4' else 'VERSION')
            if version=='2.0b4':assert b'Preferred A 0000000D' in text
            else:assert version.encode() in text and b'65C816' in text and b'Board: 2609' in text
            link.command('L',b'S19')
            for line in (folder/'installer-model-only.s19').read_bytes().splitlines():
                link.send(line+b'\r\n');time.sleep(.04)
            link.until(b'\r\nB3> ')
            # No dump/readback command: the owner explicitly disabled it.
            link.send(f'G {entry:04X}\r'.encode())
            report['execution_may_have_started']=True;save()
            link.until(b'Y then Enter> ');link.send(b'Y\r');report['transaction_started']=True;save()
            for n,(op,data) in enumerate(zip(plan['transaction']['operations'][1:],transfers)):
                link.until(f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode(),90)
                for offset in range(0,4096,64):link.send(data[offset:offset+64]);time.sleep(.01)
                report['transfers_completed']=n+1;save();print('TRANSFER',a.phase,n+1,op['bank'],hex(op['address']),flush=True)
            (a.out/'result.txt').write_bytes(link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET',90))
            report.update(passed=True,transaction_device_verified=True,physical_reset_pending=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
            publish(marker,dict(board='2609',state='windows-migration-reset-required',phase=a.phase,run=str(a.out.resolve()),block_snapshot=True))
            print('PASS',a.phase,'tool completed; host readbacks disabled; physical RESET required',flush=True)
        except BaseException:
            report['failure']=traceback.format_exc();save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()

if __name__=='__main__':main()
