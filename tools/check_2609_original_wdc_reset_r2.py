"""Arm the private original-816 debugger before owner RESET; no EXEC or persistent writes."""
import argparse
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime,timezone
from pathlib import Path
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from atomic_json import publish
from bf1_816_stock_safe_ram import restore_safe as restore

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.kit.resolve()));import migrate;import legacy_transport as wire
    migrate.verify_kit(a.kit)
    installed=read(a.stage/'report.json');assert installed['passed'] and installed['transaction_device_verified'] and installed['physical_reset_pending'] and installed['board']=='2609'
    assert installed['expected_hashes'][3]=='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
    marker=Q/'device-operations/2609.json';assert read(marker)['state']=='inspection-required'
    backup=Q/'2609-windows-migration-backup-2026-10-18-r1';assert read(backup/'report.json')['passed']
    original=(backup/'application-ram-original.bin').read_bytes();assert hashlib.sha256(original).hexdigest()==read(backup/'report.json')['files']['application-ram-original.bin']['sha256']
    assert not a.out.exists();a.out.mkdir(parents=True)
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']];assert len(ports)==1
    report=dict(board='2609',pid=os.getpid(),port=ports[0].device,passed=False,state='opening',
        started_utc=datetime.now(timezone.utc).isoformat(),clock_set=False,trim_changed=False,
        persistent_writes=False,EXEC_requested=False,native_application_tests=False,
        original_image_private_only=True,stage_report_sha256=sha(a.stage/'report.json'),packaged_transport_sha256=sha(Path(wire.__file__)))
    def save():publish(a.out/'report.json',report)
    save();link=None
    with (a.out/'serial.jsonl').open('x') as log:
      try:
        link=wire.Link(ports[0].device,log,stock=True)
        assert not link.serial.rtscts and link.serial.rts and not link.serial.dtr
        report.update(state='armed-for-owner-reset',cts=link.serial.cts);save()
        print('ARMED 2609 original-816 read-only debugger probe for 240 seconds; owner RESET required now',flush=True)
        identity=link.stock_info_after_reset(seconds=240);assert len(identity)==12 and identity[:3]==b'SXB';(a.out/'identity.bin').write_bytes(identity)
        report.update(state='debugger-identity-verified',identity_hex=identity.hex());save()
        for repeat in range(2):
            data=link.stock_read(0x8000,32768);(a.out/f'b3-{repeat}.bin').write_bytes(data)
            assert hashlib.sha256(data).hexdigest()==installed['expected_hashes'][3],'Original WDC source differs'
        report['original_B3_double_read_verified']=True;save()
        receipt=restore(link,original);assert receipt['passed'] and not receipt['execution_requested']
        report.update(application_ram_restored=False,application_ram_safe_ranges_restored=True,RAM_restoration=receipt,passed=True,state='private-original-816-WDC-verified',finished_utc=datetime.now(timezone.utc).isoformat());save()
        publish(a.out/'restore-needed.json',dict(needed=True,verified=False,deferred_first=0x700,deferred_last=0x7ff,sha256=receipt['original_sha256'],reason='Original 816 debugger live stack; full restoration deferred until bf1'))
        publish(a.stage/'restore-needed.json',dict(needed=True,verified=False,deferred_first=0x700,deferred_last=0x7ff,sha256=receipt['original_sha256'],reason='Original 816 debugger live stack; full restoration deferred until bf1'))
        publish(marker,dict(board='2609',state='private-original-816-WDC-verified',run=str(a.out.resolve()),block_snapshot=True,
            application_ram_restored=False,application_ram_safe_ranges_restored=True,deferred_RAM_page=0x700,reason='Original WDC debugger active; normal bf1 RTC collector is incompatible'))
        print('PASS original-816 identity, exact double B3 read and safe RAM restoration; page0700 deferred; no EXEC',flush=True)
      except BaseException:
        report.update(state='inspection-required',failure=traceback.format_exc());save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:
        if link:link.serial.close()


if __name__=='__main__':main()
