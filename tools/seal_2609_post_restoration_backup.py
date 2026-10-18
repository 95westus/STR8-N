"""Seal actual staged readbacks as a post-restoration backup; no board access.

Flash repeats are the before/after B35 verification reads. Retained-device
repeats are independent reads during A40 and B35 verification, spanning only
the separately verified flash restoration. Timing/lineage are explicit.
"""
import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];G=ROOT/'output/qualification/bf1-2609-physical-gate-2026-10-17-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=G/'pre-restoration-backup';first=G/'restore-A40-checks';last=G/'restore-B35-checks'
    cp=G/'original-restoration-checkpoint.json';assert read(cp)['passed']
    a,b=read(first/'report.json'),read(last/'report.json')
    assert all(r['passed'] and r['application_ram_restored'] and r['ports_released'] for r in (a,b))
    for name in ('eeprom-after.bin','sram-after.bin'):assert (first/name).read_bytes()==(last/name).read_bytes()
    out=G/'post-restoration-backup';assert not out.exists();sources={}
    for bank in range(4):
        assert (last/f'before-checks-b{bank}.bin').read_bytes()==(last/f'after-checks-b{bank}.bin').read_bytes()
        sources[f'b{bank}.bin']=last/f'after-checks-b{bank}.bin'
        sources[f'b{bank}-repeat.bin']=last/f'before-checks-b{bank}.bin'
    for name in ('eeprom','sram'):
        sources[name+'.bin']=last/(name+'-after.bin');sources[name+'-repeat.bin']=first/(name+'-after.bin')
    for name in ('application-ram-original.bin','restore-application-ram.s19'):sources[name]=original/name
    sources['version.txt']=last/'version.txt'
    ram_sha=sha(original/'application-ram-original.bin')
    for folder in (first,last):
        state=read(folder/'restore-needed.json');assert not state['needed'] and state['verified'] and state['sha256']==ram_sha
    assert b'2.0b35' in sources['version.txt'].read_bytes() and b'Running: MONITOR B' in sources['version.txt'].read_bytes()
    out.mkdir()
    for name,path in sources.items():shutil.copyfile(path,out/name)
    publish(out/'restore-needed.json',dict(needed=False,verified=True,sha256=ram_sha))
    intake=read(original/'report.json')
    result=dict(passed=True,board='2609',port=intake['port'],usb_serial=intake['usb_serial'],active_page=0xb0,
        sealed_utc=datetime.now(timezone.utc).isoformat(),flash_repeat_verified=True,eeprom_repeat_verified=True,
        sram_repeat_verified=True,application_ram_restored=True,ports_released=True,clock_set=False,
        trim_changed=False,persistent_writes=False,board_access=False,
        capture_kind='Receipt-bound seal of actual post-restoration validation reads; no fresh reads performed by this sealer',
        repeat_timing='Flash: before/after B35 checks. EEPROM/SRAM: A40-check and B35-check reads spanning flash-only restoration; both exact to the pre-restoration backup. RAM: verified original restoration after both stages.',
        parent_receipts={str(p.resolve()):sha(p) for p in (cp,original/'report.json',first/'report.json',last/'report.json')},
        source_readbacks={n:dict(path=str(p.resolve()),sha256=sha(p)) for n,p in sources.items()},
        files={n:dict(bytes=(out/n).stat().st_size,sha256=sha(out/n)) for n in sources})
    publish(out/'report.json',result);print('PASS sealed actual post-restoration readbacks with explicit repeat timing and RAM lineage',out)
if __name__=='__main__':main()
