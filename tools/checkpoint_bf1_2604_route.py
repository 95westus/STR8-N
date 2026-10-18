"""Close preserving return capture and offline route evidence; never opens serial."""
import argparse,hashlib,json,re,shutil,tomllib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--model',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    result=read(a.model/'report.json');backup=read(a.backup/'report.json');restore=read(a.backup/'restore-needed.json')
    assert result['passed'] and backup['passed'] and backup['ports_released'] and not restore['needed'] and restore['verified']
    assert all(backup[k] for k in ['flash_repeat_verified','eeprom_repeat_verified','sram_repeat_verified','application_ram_restored'])
    for name,v in backup['files'].items():assert sha(a.backup/name)==v['sha256'] and (a.backup/name).stat().st_size==v['bytes']
    for stem in ['b0','b1','b2','b3','eeprom','sram']:assert (a.backup/(stem+'.bin')).read_bytes()==(a.backup/(stem+'-repeat.bin')).read_bytes()
    assert (a.backup/'application-ram-original.bin').read_bytes()==(a.backup/'application-ram-restored.bin').read_bytes()
    commands=0;executions=0;ram_writes=0
    for line in (a.backup/'serial.jsonl').read_text().splitlines():
      d=json.loads(line)
      if d['direction']!='TX':continue
      text=bytes.fromhex(d['hex']).decode('ascii').strip();commands+=1
      if not text:continue
      if text in ['VERSION','TIME','APPS','Q','L','B0','B1','B2','B3']:continue
      if text in ['G 2000','G 2003']:executions+=1;continue
      if re.fullmatch(r'D [0-9A-F]{4} [0-9A-F]{4}',text):continue
      if text.startswith('M '):
        fields=text.split();first=int(fields[1],16);assert 0x200<=first and first+len(fields)-2<=0x6500;assert all(len(x)==2 and 0<=int(x,16)<=255 for x in fields[2:]);ram_writes+=1;continue
      if re.fullmatch(r'S[019][0-9A-Fa-f]+',text):
        raw=bytes.fromhex(text[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if text[1]=='1':first=int.from_bytes(raw[1:3],'big');assert 0x200<=first and first+len(raw)-4<=0x6500
        continue
      raise AssertionError('Unexpected serial TX: '+repr(text))
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256'] and set(active['powered_off_boards'])=={'2205','2609'}
    registered=next(b for b in read(Path(active['baseline_index']))['boards'] if b['board']=='2604');eui=':'.join(f'{v:02X}' for v in (a.backup/'eeprom.bin').read_bytes()[-6:]);assert eui==registered['eui'],'2604 fresh EUI differs from registered baseline identity'
    freeze=read(ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');frozen=Path(freeze['frozen_source_directory'])/'BUILD/v2-beta35-candidate'
    for name,digest in freeze['artifact_hashes'].items():assert sha(frozen/name)==digest
    pin=read(ROOT/'output/qualification/batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,v in pin['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==v['sha256']
    assert sha(ROOT/'output/releases/str8n-2.0b35-review.zip')=='dc7c854f71852a853eac48dbf0070560feb64c8c47df0441d496a5062d7afa1f'
    assert sha(ROOT/'output/releases/str8n-2.0b35-B-target-review-2026-10-17-r2.zip')=='2333a9deade33c6b00064625454e62d43c0057b9e0c9b1985526aed3dcee031a'
    for path,digest in result['sources'].items():assert sha(Path(path))==digest
    assert (ROOT/'tmp/bfr2/reservation.bin').read_bytes()==(ROOT/'tmp/bfr3/reservation.bin').read_bytes()
    assert sha(ROOT/'tmp/bfr2/reservation.bin')=='d4ef9554eb66a240b10906b68a9bddb1e57e9f4b6954bf2ea2acc224fcb63b7d'
    figures=read(a.report/'manifest.json')
    for name,digest in figures['files'].items():assert sha(a.report/name)==digest
    for path,digest in read(a.report/'report.json')['sources'].items():assert sha(Path(path))==digest
    schedules={}
    for name in ['2512-nist-snapshot-every-three-hours','2512-powered-soak-and-rtc-drift']:
      config=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text());assert config['status']=='ACTIVE';schedules[name]=dict(status=config['status'],rrule=config['rrule'],includes_2604='2604' in config['prompt'])
    out=a.model/'closure';out.mkdir(exist_ok=False);shutil.copytree(ROOT/'tmp/bfr2',out/'helper-build')
    for path in [Path(__file__),ROOT/'tools/verify_bf1_2604_route.py',ROOT/'tools/plan_bf1_2604_route.py',ROOT/'tools/capture_2604_return_backup.py',ROOT/'tools/build_bf1_route_helper.py',ROOT/'tools/report_2512_2604_drift.py']:
        shutil.copyfile(path,out/path.name)
    checkpoint=dict(passed=True,status='return_capture_and_bf1_route_offline_models_complete',candidate_id='batchfix-r1',board='2604',created_utc=datetime.now(timezone.utc).isoformat(),fresh_eui=eui,fresh_eui_matches_registered_baseline=True,backup=str(a.backup.resolve()),backup_report_sha256=sha(a.backup/'report.json'),backup_serial_sha256=sha(a.backup/'serial.jsonl'),backup_commands_audited=commands,read_probe_executions=executions,ordinary_ram_write_commands=ram_writes,full_flash_bytes=131072,retained_sram_bytes=131072,eeprom_inventory_bytes=137,application_ram_restored=True,route_report=str((a.model/'report.json').resolve()),route_report_sha256=sha(a.model/'report.json'),route_checks=result['cases'],separate_helper_bytes=585,separate_helper_sha256=sha(ROOT/'tmp/bfr2/reservation.bin'),helper_independently_reproduced=True,combined_drift_report=str((a.report/'report.html').resolve()),combined_drift_data_sha256=sha(a.report/'report.json'),immutable_baseline_sha256=active['baseline_index_sha256'],frozen_beta35_artifacts_verified=len(freeze['artifact_hashes']),bf1_artifacts_verified=len(pin['artifacts']),automations=schedules,powered_off_boards=active['powered_off_boards'],clocks_trims_changed=False,firmware_installed=False,persistent_devices_written=False,installation_permitted=False,release_qualified=False,physical_route_qualified=False,remaining_gates=['Review exact generated hardware installation/recovery procedure and explicitly authorize device installation','Actual hardware/native CPU acceptance and full post-install readback','Broader A-phase/interrupted-restoration cuts and electrical interruption/physical recovery acceptance; current cuts are representative B-phase models','Continue long-term powered-on drift collection for 2512 and 2604'],deferred=['ACIA','crypto'])
    cp=a.model/'checkpoint.json';cp.write_text(json.dumps(checkpoint,indent=2)+'\n');(ROOT/'output/qualification/bf1-2604-route-current.json').write_text(json.dumps(dict(checkpoint=str(cp.resolve()),checkpoint_sha256=sha(cp),installation_permitted=False,release_qualified=False),indent=2)+'\n')
    statepath=Path(active['campaign_state']);state=read(statepath);state['2604_return_snapshot']=backup['snapshot'];state['2604_return_backup']=str(a.backup.resolve());state['2604_bf1_offline_route_checkpoint']=str(cp.resolve());state['combined_drift_report_pointer']=str(ROOT/'output/qualification/rtc-combined-report-current.json');state['snapshot_boards']=['2512','2604'];statepath.write_text(json.dumps(state,indent=2)+'\n')
    print(json.dumps(checkpoint,indent=2))
if __name__=='__main__':main()
