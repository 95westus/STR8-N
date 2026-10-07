"""Build runnable read-only calendar example; no serial or flash operations."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from beta4_migration import s19

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-time-example'

def main():
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'tools/v2-rtc/kernel-rtc-api.inc',stage/'kernel-rtc-api.inc')
    (stage/'time-example.asm').write_text(long_branches((ROOT/'tools/v2-rtc/time-example.asm').read_text()))
    compiler.OUT,compiler.SOURCE=OUT,stage
    memory,symbols=compiler.assemble('time-example',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    body=compiler.dense_image(memory,0x2000,symbols['APP_END']);assert symbols['APP_END']<0x2400
    (OUT/'time-example.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(entry=0x2000,bytes=len(body),end=symbols['APP_END'],sha256=hashlib.sha256(body).hexdigest(),symbols=symbols,read_only=True),indent=2)+'\n')
    print('Read-only time example:',len(body),'bytes; G 2000')

if __name__=='__main__':main()
