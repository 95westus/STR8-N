"""Build RAM timing probe + stock worker with timer sampling in poll loop."""
import json,shutil
from pathlib import Path
from build_v2_spi_resident import assemble,equs,ROOT
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
OUT=ROOT/'BUILD/v2-storage/timing'

def main():
    src=OUT/'source';src.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    for p in (ROOT/'BUILD/v2-storage/source').glob('*.inc'):shutil.copyfile(p,src/p.name)
    firmware=json.loads((ROOT/'BUILD/v2-storage/build.json').read_text())
    equs(src/'timing-links.inc',{k:firmware['worker'][k] for k in ('V2W_MUTATE','V2W_SELECT','V2W_ERASE_RAW','V2W_ACCOUNT')})
    (src/'storage-timing.asm').write_text(long_branches((ROOT/'tools/v2-spi/storage-timing.asm').read_text()))
    probe,ps,_=assemble(src,'storage-timing',0x2000,'APP_END',0x2000)
    (OUT/'probe.s19').write_bytes(s19(dict(enumerate(probe,0x2000)),0x2000));(OUT/'probe.bin').write_bytes(probe)
    (OUT/'build.json').write_text(json.dumps(dict(probe_bytes=len(probe),symbols=ps,worker=firmware['worker'],firmware_artifacts=firmware['artifacts'],worker_modified=False),indent=2)+'\n')
    print('RAM-only timing probe',len(probe),'bytes; unmodified installed worker; no firmware flash')

if __name__=='__main__':main()
