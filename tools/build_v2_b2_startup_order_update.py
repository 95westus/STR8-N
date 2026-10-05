"""Build the exact installed autoload -> dots-first B/E/F update; no device I/O."""
import argparse
import json
from pathlib import Path
import build_v2_b2_autoload_update as updater
import build_v2_b2 as firmware

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--named',action='store_true')
    args=parser.parse_args()
    folder=args.evidence
    before=(folder/'before-b3.bin').read_bytes()
    previous=firmware.ROOT/'output/qualification/b2-2205-2026-10-04'/('startup-order-install-4013' if args.named else 'autoload-install-1791128505967075700')
    assert before==(previous/'after-b3.bin').read_bytes()
    qualification=json.loads((firmware.OUT/'autoload-qualification.json').read_text())
    assert qualification['host_check_groups']==(41 if args.named else 37) and qualification['core_bytes']==(4039 if args.named else 4013)
    for path,digest in qualification['images'].items():
        assert updater.update.sha((firmware.ROOT/path).read_bytes())==digest
    c=(firmware.ROOT/'BUILD/v2-b2-command-example/str8n-v2-b2-h-x-c000-cfff.bin').read_bytes()
    if not args.named:assert c==before[0x4000:0x5000]
    assert updater.valid_boot_pocket(before[0x7FD0:0x7FE0]) and before[0x7FD1]==0
    ef=(firmware.OUT/(firmware.STEM+'-e000-ffff.bin')).read_bytes()
    assert len(ef)==8192
    desired=dict(b=(firmware.OUT/(firmware.STEM+'-b000-bfff.bin')).read_bytes(),
                 e=ef[:4096],f=ef[4096:0x1FD0]+before[0x7FD0:0x7FE0]+ef[0x1FE0:])
    if args.named:desired['c']=c
    phases=('b','c','e','f') if args.named else ('b','e','f')
    assert desired['e'][:4]==b'EM\x01\x01'
    binding=firmware.crc16(desired['f'][:0xFD0]+desired['f'][0xFE0:])
    assert int.from_bytes(desired['e'][4:6],'little')==binding
    for row in updater.build(before,folder,desired=desired,phases=phases):
        print(row['artifact'])
    for phase in phases:
        path=folder/(phase+'-updater/manifest.json')
        meta=json.loads(path.read_text())
        meta.update(source_version='b2-startup-order-4013' if args.named else 'b2-autoload-4001',
                    baseline_sha256=updater.update.sha(updater.update.normalized(before[-4096:])))
        path.write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
