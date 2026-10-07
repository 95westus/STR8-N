"""Build standalone CLOCK 1.0 for the integrated optional RTC service."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from beta4_migration import s_record, read_s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-clock'
SOURCE = ROOT / 'tools/v2-rtc'
SOURCE_NAME = 'clock.asm'
VERSION = '1.0'
MAX_END = 0x2F00


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    for name in ('build.json','test-results.json','clock.s19'):
        (OUT/name).unlink(missing_ok=True)
    stage = OUT / 'source'
    stage.mkdir(exist_ok=True)
    shutil.copyfile(SOURCE/'kernel-rtc-api.inc',stage/'kernel-rtc-api.inc')
    shutil.copyfile(SOURCE/'journal-eq.inc',stage/'journal-eq.inc')
    shutil.copyfile(SOURCE/'outage-format.inc',stage/'outage-format.inc')
    expanded = long_branches((SOURCE/'outage-format.inc').read_text()).replace('BM_LONG_','OF_LONG_')
    (stage/'outage-format.inc').write_text(expanded)
    text = long_branches((SOURCE/SOURCE_NAME).read_text()).replace('BM_LONG_','CLOCK_LONG_')
    (stage/'clock.asm').write_text(text,encoding='ascii')
    compiler.OUT,compiler.SOURCE = OUT,stage
    cells,symbols = compiler.assemble('clock',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    end = symbols['APP_END']
    assert symbols['START']==0x2000 and end<=MAX_END
    body = compiler.dense_image(cells,0x2000,end)
    (OUT/'clock.bin').write_bytes(body)
    lines = [s_record('0',0,('STR8-N CLOCK '+VERSION+' optional RTC').encode())]
    lines += [s_record('1',a,body[a-0x2000:a-0x2000+32]) for a in range(0x2000,end,32)]
    lines.append(s_record('9',0x2000))
    (OUT/'clock.s19').write_text('\n'.join(lines)+'\n',encoding='ascii')
    loaded,entry = read_s19(OUT/'clock.s19')
    assert entry==0x2000 and bytes(loaded.values())==body
    (OUT/'build.json').write_text(json.dumps(dict(version=VERSION,entry=0x2000,end=end,bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),s19_sha256=hashlib.sha256((OUT/'clock.s19').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256((SOURCE/SOURCE_NAME).read_bytes()).hexdigest(),symbols=symbols),indent=2)+'\n')
    print('CLOCK '+VERSION+':',len(body),'bytes at 2000-'+f'{end-1:04X}'+'; service RAM untouched by loader')


if __name__=='__main__':
    main()
