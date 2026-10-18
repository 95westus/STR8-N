"""Complete exact saved 2609 RAM restoration after capture-loader range refusal."""
import argparse,hashlib,json,re,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def saved_ram_image(path):
    cells={};entry=None
    for line in path.read_text(encoding='ascii').splitlines():
        assert entry is None and re.fullmatch(r'S[019][0-9A-F]+',line)
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        address=int.from_bytes(raw[1:3],'big')
        if line[1]=='1':
            for n,v in enumerate(raw[3:-1],address):assert n not in cells;cells[n]=v
        elif line[1]=='9':assert len(raw)==4;entry=address
    return cells,entry
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--backup',type=Path,required=True);a=ap.parse_args();folder=a.backup
    report_path=folder/'report.json';report=json.loads(report_path.read_text());marker=ROOT/'output/qualification/device-operations/2609.json'
    assert report['board']=='2609' and not report['passed'] and all(report[x] for x in ('flash_repeat_verified','eeprom_repeat_verified','sram_repeat_verified'))
    need=json.loads((folder/'restore-needed.json').read_text());original=(folder/'application-ram-original.bin').read_bytes();assert need['needed'] and need['sha256']==sha(original) and len(original)==0x6300
    cells,entry=saved_ram_image(folder/'restore-application-ram.s19');assert entry==0x200 and set(cells)==set(range(0x200,0x6500)) and bytes(cells[n] for n in range(0x200,0x6500))==original
    active=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text());assert '2609' not in active['powered_off_boards'] and active['powered_off_boards']==['2205']
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==report['port']
    historical=folder/'report-before-restoration-recovery.json';assert not historical.exists();historical.write_bytes(report_path.read_bytes())
    (folder/'capture-source.py').write_bytes((ROOT/'tools/capture_2609_return_backup.py').read_bytes())
    issue=dict(reason='Capture harness attempted application-only loader on saved RAM at $0200; validation refused before any restore transfer',historical_report_sha256=sha(historical.read_bytes()),source_sha256=sha((folder/'capture-source.py').read_bytes()),all_repeated_reads_passed=True,original_ram_sha256=sha(original))
    publish(folder/'capture-harness-issue.json',issue)
    recovery=dict(passed=False,board='2609',port=port,started_utc=datetime.now(timezone.utc).isoformat(),clock_set=False,trim_changed=False,persistent_writes=False,reset=False)
    with (folder/'restoration-recovery-serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);link.command('L',b'S19')
            for row in (folder/'restore-application-ram.s19').read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
            reply=link.until(b'\r\nB3> ');assert not any(v in reply for v in (b'Bad',b'Protected',b'Wrap',b'Error')),reply
            actual=b''.join(link.dump(n,min(n+4095,0x64ff)) for n in range(0x200,0x6500,4096))
            assert actual==original,'Restored RAM mismatch';(folder/'application-ram-restored.bin').write_bytes(actual)
            recovery.update(passed=True,bytes=len(actual),sha256=sha(actual),application_ram_restored=True,finished_utc=datetime.now(timezone.utc).isoformat())
            publish(folder/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(actual)))
        except BaseException:
            recovery['failure']=traceback.format_exc();raise
        finally:link.serial.close();publish(folder/'restoration-recovery.json',recovery)
    report['files']['application-ram-restored.bin']=dict(bytes=len(original),sha256=sha(original))
    report.update(passed=True,application_ram_restored=True,ports_released=True,finished_utc=datetime.now(timezone.utc).isoformat(),capture_harness_issue=issue,restoration_recovery_report_sha256=sha((folder/'restoration-recovery.json').read_bytes()))
    publish(report_path,report);publish(marker,dict(board='2609',state='return-backup-complete',backup=str(folder.resolve()),report_sha256=sha(report_path.read_bytes()),block_snapshot=False))
    print('PASS exact RAM restoration and completed 2609 backup',sha(original),flush=True)
if __name__=='__main__':main()
