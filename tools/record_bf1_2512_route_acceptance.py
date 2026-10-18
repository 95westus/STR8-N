"""Offline closure of a completed exact 2512 migration route; requires real hardware and restoration receipts."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';H=Q/'bf1-2512-hardware-2026-10-17-r1';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',choices=['wdcmonv2','v2.0b4'],required=True);a=ap.parse_args();wdc=a.route=='wdcmonv2';prefix='wdc' if wdc else 'beta4';route='2512-'+a.route+'-to-bf1'
    hw=H/(prefix+'-bf1-hardware/report.json');restored=H/(prefix+'-original-checked/report.json');source=H/('wdc-source-verified/report.json' if wdc else 'beta4-source-checked/report.json');historical=H/('wdc-restored-source-verified/report.json' if wdc else 'beta4-restored-source-checked/report.json');offline=Q/'bf1-2512-legacy-offline-checkpoint-2026-10-17-r1.json'
    hardware=read(hw);restoration=read(restored);initial=read(source);history=read(historical);off=read(offline)
    for r in (hardware,restoration,initial,history):assert r['passed'] and r['board']=='2512' and r['application_ram_restored']
    assert hardware['route_id']==route and hardware['target_version']=='2.0bf1' and hardware['full_flash_verified'] and hardware['initial_checks_passed'] and hardware['retained_storage_preserved'] and hardware['clocks_trims_unchanged']
    assert restoration['original_payload_restored'] and restoration['conservative_wear_retained'] and restoration['retained_storage_preserved'] and restoration['clocks_trims_unchanged'] and restoration['full_flash_verified']
    expected_phase=('wdcmonv2' if wdc else 'v2-0b4')+'-restore-original';assert restoration['phase']==expected_phase
    phase=Q/'bf1-2512-legacy-offline-2026-10-17-r6'/expected_phase/'plan.json';assert restoration['expected_hashes']==read(phase)['expected_sha256']
    backup=Q/'bf1-2512-pre-migration-backup-2026-10-17-r2';assert read(backup/'report.json')['passed'];original_hash=sha(backup/'application-ram-original.bin')
    for path in (hw.parent,restored.parent):
        ram=read(path/'restore-needed.json');assert not ram['needed'] and ram['verified'] and ram['sha256']==original_hash
    if wdc:
        for path in (H/'wdc-stage',H/'wdc-restore-historical'):
            ram=read(path/'restore-needed.json');assert not ram['needed'] and ram['verified'] and ram['sha256']==original_hash
    else:
        for path in (source.parent,historical.parent):
            ram=read(path/'restore-needed.json');assert not ram['needed'] and ram['verified'] and ram['sha256']==original_hash
    active=read(Q/'active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==off['baseline_sha256'];assert off['offline_qualified'] and route in off['routes']
    for item in off['evidence'].values():assert sha(Path(item['path']))==item['sha256'] and read(Path(item['path']))['passed']
    children=dict(offline=off['evidence']['model']['path'],hardware=str(hw),restoration=str(restored),source=str(source),historical_source_restoration=str(historical))
    if wdc:children.update(source_wire=str(H/'wdc-source-wire-audit.json'),historical_wire=str(H/'wdc-restored-source-wire-audit.json'))
    evidence={}
    for key,value in children.items():
        path=Path(value);assert read(path)['passed'];evidence[key]=dict(path=str(path.resolve()),sha256=sha(path))
    cp=Q/(route+'-acceptance-2026-10-17-r1.json');pointer=Q/(route+'-acceptance-current.json');assert not cp.exists() and not pointer.exists()
    receipt=dict(route_id=route,board='2512',target_version='2.0bf1',passed=True,offline_qualified=True,hardware_qualified=True,original_RAM_restored=True,clocks_trims_unchanged=True,retained_storage_preserved=True,conservative_wear_retained=True,baseline_sha256=active['baseline_index_sha256'],evidence=evidence,scope='Exact staged private WDC diagnostic/monitor with WC sidecar' if wdc else 'Exact published beta4 generation-13 MON A source profile',both_bf1_monitor_slots_exercised=True,original_beta35_payload_restored=True,full_release_qualified=False,generic_installation_permitted=False,recorded_utc=datetime.now(timezone.utc).isoformat(),closure_source_sha256=sha(Path(__file__)))
    cp.write_text(json.dumps(receipt,indent=2)+'\n');pointer.write_text(json.dumps(dict(checkpoint=str(cp.resolve()),sha256=sha(cp)),indent=2)+'\n');print('PASS exact route offline/hardware/restoration acceptance:',route,flush=True)
if __name__=='__main__':main()
