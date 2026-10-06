"""Build beta4 monitor firmware and unchanged, separately loadable MAINT.

No serial access. No application implementations or board backups are included.
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import build_v2_recovery as recovery
import build_v2_beta4_launcher as apps
import build_bank_maint_recovery as maintenance

ROOT=recovery.ROOT
OUT=ROOT/'BUILD/v2-beta4'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation',type=int,default=13)
    args=parser.parse_args()
    if not 1<=args.generation<0xffffffff:parser.error('generation must be 1..4294967294')
    # The frozen F contract and S/R/T extension come from the recovery builder.
    saved=sys.argv
    try:
        recovery.SOURCE=ROOT/'src/v2-beta4'
        recovery.OUT=ROOT/'BUILD/v2-beta4-base'
        apps.BASE_SOURCE=recovery.SOURCE
        apps.BASELINE_DIR=recovery.OUT
        apps.SOURCE=ROOT/'src/v2-beta4-launcher'
        sys.argv=[saved[0],'--generation','9']
        recovery.main()
        # Empty descriptor table: optional applications are developed separately.
        apps.NAMES=()
        sys.argv=[saved[0],'--generation',str(args.generation),'--out',str(OUT)]
        apps.main()
        maintenance.OUT=OUT/'maintenance'
        maintenance.main()
    finally:sys.argv=saved
    kit=OUT/'kit';kit.mkdir(exist_ok=True)
    sources={
        'str8n-v2-b4-slot-a.bin':OUT/(recovery.STEM+'-slot-a0.bin'),
        'str8n-v2-b4-slot-b.bin':OUT/(recovery.STEM+'-slot-b0.bin'),
        'str8n-v2-b4-e000-efff.bin':OUT/(recovery.STEM+'-e000-efff.bin'),
        'str8n-v2-b4-f000-ffff.bin':OUT/(recovery.STEM+'-f000-ffff.bin'),
        'str8n-bank-maint-1.5-2000.s19':maintenance.OUT/(maintenance.NAME+'.s19'),
        'STR8N_V2_BETA4.md':ROOT/'docs/STR8N_V2_BETA4.md',
        'STR8N_V2_BETA4_RST.md':ROOT/'docs/STR8N_V2_BETA4_RST.md',
        'STR8N_BANK_MAINT_RECOVERY.md':ROOT/'docs/STR8N_BANK_MAINT_RECOVERY.md',
    }
    artifacts={}
    for name,source in sources.items():
        target=kit/name;shutil.copyfile(source,target)
        artifacts[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    ram,entry=recovery.link.read_s19(kit/'str8n-bank-maint-1.5-2000.s19')
    body=bytes(ram[a] for a in range(min(ram),max(ram)+1))
    if hashlib.sha256(body).hexdigest()!='57a21e4076aeda84cad2fff920d282311f0a65ef2a254f966396484409b437db':
        raise ValueError('Beta4 must retain the installed BANK MAINT 1.5 program unchanged')
    header=b'SR\x01\x3f'+entry.to_bytes(2,'little')+len(body).to_bytes(2,'little')+b'MAINT'.ljust(16,b'\0')
    storage=header+body+b'\xff'*(8192-24-len(body))
    name='str8n-v2-b4-maint-8000-9fff.bin'
    (kit/name).write_bytes(storage);sources[name]=kit/name;artifacts[name]=hashlib.sha256(storage).hexdigest()
    manifest=dict(version='2.0b4',generation=args.generation,maint_version='1.5',
        maint_entry=entry,maint_end=max(ram),maint_bytes=len(body),
        maint_program_sha256=hashlib.sha256(body).hexdigest(),
        installed_applications=[],artifacts=artifacts,
        maintenance_record=dict(label='MAINT',bank=3,flash=0x8000,end=0x9d6b,ram_start=entry,ram_end=max(ram)),
        installation='Slot BIN files use U A/B on a compatible recovery board. E/F are reference firmware; do not load through L.',
        board_backups_included=False)
    (kit/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    release=ROOT/'output/release/str8n-v2-b4.zip';release.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(release,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted([*sources,'manifest.json']):
            assert 'prior-' not in name and 'backup' not in name.lower()
            archive.write(kit/name,name)
    with zipfile.ZipFile(release) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(sources)|{'manifest.json'}
    print(json.dumps(manifest,indent=2))
    print(f'Prepared local beta4 kit: {release}; no board access or publication.')

if __name__=='__main__':main()
