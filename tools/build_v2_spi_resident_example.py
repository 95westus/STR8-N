"""Build the resident SRAM client example; no board access."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from build_v2_recovery import relax_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident/example'

def main():
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    (stage/'spi-resident-example.asm').write_text(long_branches((ROOT/'tools/v2-spi/spi-resident-example.asm').read_text()))
    compiler.OUT=OUT;compiler.SOURCE=stage
    def run():return compiler.assemble('spi-resident-example',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    cells,symbols=run();cells,symbols=relax_branches(stage/'spi-resident-example.asm',cells,symbols,run)
    body=compiler.dense_image(cells,0x2000,symbols['APP_END']);assert symbols['APP_END']<0x2300
    (OUT/'example.bin').write_bytes(body);(OUT/'example.s19').write_bytes(s19(cells,0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(bytes=len(body),end=symbols['APP_END'],sha256=hashlib.sha256(body).hexdigest(),symbols=symbols),indent=2)+'\n')
    print('Resident SRAM example:',len(body),'bytes; READ default, caller-prepared operations at 2003')

if __name__=='__main__':main()
