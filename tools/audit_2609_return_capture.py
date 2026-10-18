"""Audit preserved 2609 snapshot/backup bytes and actual serial TX allowlist."""
import argparse,hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);a=ap.parse_args()
    folder=a.backup;r=read(folder/'report.json');s=read(a.snapshot);assert r['passed'] and r['application_ram_restored'] and s['passed'] and s['ports_released']
    assert r['board']=='2609' and all(r[k] is False for k in ('clock_set','trim_changed','persistent_writes','reset'))
    assert sha(a.snapshot)==r['snapshot_sha256']
    for name,info in r['files'].items():assert (folder/name).stat().st_size==info['bytes'] and sha(folder/name)==info['sha256']
    for name,size in [('b0',32768),('b1',32768),('b2',32768),('b3',32768),('eeprom',137),('sram',131072)]:
        body=(folder/(name+'.bin')).read_bytes();assert len(body)==size and body==(folder/(name+'-repeat.bin')).read_bytes()
    for repeat in range(2):assert b''.join((folder/f'sram-{repeat}-{n:02d}.bin').read_bytes() for n in range(16))==(folder/('sram'+('-repeat' if repeat else '')+'.bin')).read_bytes()
    original=folder/'application-ram-original.bin';assert original.read_bytes()==(folder/'application-ram-restored.bin').read_bytes()
    restore=read(folder/'restore-needed.json');assert not restore['needed'] and restore['verified'] and restore['sha256']==sha(original)
    recovery=read(folder/'restoration-recovery.json');assert recovery['passed'] and recovery['sha256']==sha(original) and sha(folder/'restoration-recovery.json')==r['restoration_recovery_report_sha256']
    issue=read(folder/'capture-harness-issue.json');assert sha(folder/'report-before-restoration-recovery.json')==issue['historical_report_sha256'] and sha(folder/'capture-source.py')==issue['source_sha256']
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    baseline=next(v for v in read(Path(active['baseline_index']))['boards'] if v['board']=='2609')
    eui=':'.join(f'{v:02X}' for v in (folder/'eeprom.bin').read_bytes()[-6:]);assert eui==baseline['eui']
    item=next(v for v in s['boards'] if v['board']=='2609');rp=Path(item['report']);m=read(rp)
    assert sha(rp)==item['report_sha256'] and m['passed'] and item['trim_steps']==baseline['trim_steps'] and item['control_register']==baseline['control_register']
    tol=m['reference_uncertainty_s']+m['final_reference_check']['estimated_reference_uncertainty_s'];assert abs(m['final_reference_difference_s'])<=tol
    for f in rp.parent.parent.glob('ram-*-before.bin'):assert f.read_bytes()==f.with_name(f.name.replace('-before','-restored')).read_bytes()
    transmissions=0;ram_edits=0;executions=[];logs={}
    for name in ('serial.jsonl','restoration-recovery-serial.jsonl'):
        path=folder/name;logs[name]=sha(path)
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if row['direction']!='TX':continue
            transmissions+=1;text=bytes.fromhex(row['hex']).decode('ascii').strip()
            if text in ('','VERSION','TIME','APPS','B0','B1','B2','B3','L'):continue
            if re.fullmatch(r'S[019][0-9A-F]+',text):
                raw=bytes.fromhex(text[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
                if text[1]=='1':
                    address=int.from_bytes(raw[1:3],'big');assert 0x200<=address and address+len(raw[3:-1])<=0x6500
                continue
            match=re.fullmatch(r'D ([0-9A-F]+) ([0-9A-F]+)',text)
            if match:
                start,end=(int(v,16) for v in match.groups());assert 0x200<=start<=end<=0x7eff or 0x8000<=start<=end<=0xffff;continue
            match=re.fullmatch(r'M ([0-9A-F]+)((?: [0-9A-F]{2})+)',text)
            if match:
                address=int(match[1],16);length=len(match[2].split());assert 0x200<=address and address+length<=0x6500;ram_edits+=1;continue
            if text in ('G 2000','G 2003'):executions.append(text);continue
            raise AssertionError('Unrecognized serial TX: '+repr(text))
    assert executions.count('G 2000')==2 and executions.count('G 2003')==32
    result=dict(passed=True,observed_utc=datetime.now(timezone.utc).isoformat(),board='2609',backup_report_sha256=sha(folder/'report.json'),snapshot_summary_sha256=sha(a.snapshot),fresh_eui=eui,baseline_eui_match=True,baseline_sha256=active['baseline_index_sha256'],flash_bytes=131072,eeprom_bytes=137,sram_bytes=131072,application_ram_bytes=25344,application_ram_restored=True,serial_TX_frames=transmissions,ordinary_RAM_edit_commands=ram_edits,read_only_probe_executions=len(executions),serial_log_sha256=logs,ntp_final_difference_s=m['final_reference_difference_s'],ntp_final_tolerance_s=tol,drift_interval_s=item['drift_seconds_interval'],clock_trim_settings_changed=False,persistent_writes=False,reset=False,capture_harness_issue_retained=True)
    (folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
