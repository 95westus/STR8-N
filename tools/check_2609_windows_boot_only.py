"""Owner-requested brief boot check, without flash/RAM readbacks."""
import argparse,json,hashlib
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
    p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--install',type=Path,required=True)
    p.add_argument('--reset-confirmation',type=Path,required=True)
    p.add_argument('--version',choices=('2.0bf1','2.0b4'),required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    import sys;sys.path.insert(0,str(a.kit.resolve()));import migrate;import legacy_transport as wire
    migrate.verify_kit(a.kit)
    install=read(a.install/'report.json');reset=read(a.reset_confirmation)
    assert install['passed'] and install['transaction_device_verified'] and install['physical_reset_pending']
    assert reset['board']=='2609' and reset['user_confirmed_physical_reset'] and reset['install_report_sha256']==sha(a.install/'report.json')
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['state']=='windows-migration-reset-required' and Path(guard['run']).resolve()==a.install.resolve()
    active=read(Q/'active-rtc-campaign.json');assert set(active['powered_off_boards'])=={'2205','2512'}
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']];assert len(ports)==1 and ports[0].device==install['port']
    assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board='2609',passed=False,host_memory_readbacks=False,checks_scope='VERSION/identity only, per owner instruction',
        application_RAM_restoration_pending=True,full_hardware_qualification=False,clock_trim_settings_changes=False,
        install_report_sha256=sha(a.install/'report.json'),reset_confirmation_sha256=sha(a.reset_confirmation))
    with (a.out/'serial.jsonl').open('x') as log:
        link=wire.Link(ports[0].device,log)
        try:
            establish_b3(link);text=link.command('P' if a.version=='2.0b4' else 'VERSION');(a.out/'version.txt').write_bytes(text)
            if a.version=='2.0b4':
                assert b'Preferred A 0000000D' in text,'Historical generation-13 selection not reported'
                report['version_evidence']='Pinned published beta4 installer/device verification and live generation-13 P query; historical VERSION command absent'
                report['CPU_field_live_observed']=False
            else:
                assert a.version.encode() in text and b'65C816' in text and b'Board: 2609' in text,'Unexpected bf1 version/CPU/board'
                report['CPU_field_live_observed']=True
            # Published beta4 predates the friendly board-number field. The
            # exact USB serial/port pin remains mandatory for both versions.
            report['board_identity_method']='Exact USB serial pin; bf1 board field where supported'
            report.update(passed=True,version=a.version,boot_identity_verified=True,finished_utc=datetime.now(timezone.utc).isoformat())
        finally:
            link.serial.close();publish(a.out/'report.json',report)
    publish(marker,dict(board='2609',state='windows-flash-boot-checked',version=a.version,run=str(a.out.resolve()),
        block_snapshot=True,application_RAM_restoration_pending=True,reason='Owner requested sequential Windows migration flashes; full RAM restoration deferred until final bf1'))
    print('PASS boot identity',a.version,'on2609; no memory readbacks; full RAM restoration remains pending')

if __name__=='__main__':main()
