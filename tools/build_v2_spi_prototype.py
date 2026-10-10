"""Build size-optimized W65C02S SPI/SRAM RAM prototype; no hardware access."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from build_v2_recovery import relax_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-spi-phase2'
SOURCE=ROOT/'tools/v2-spi'

def main():
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    compiler.OUT=OUT;compiler.SOURCE=stage
    provider=ROOT/'BUILD/v2-rtc-trim/split/build.json';pm=json.loads(provider.read_text())
    (stage/'provider-private.inc').write_text(''.join(f'{name} EQU ${pm["provider_symbols"][symbol]:04X}\n' for name,symbol in (('BUFFER','BUFFER_VALID'),('VALIDATE_SHAPE','ADDRESS_OK'))))
    text=long_branches((SOURCE/'spi-prototype.asm').read_text()).replace('BM_LONG_','SP_LONG_')
    (stage/'spi-prototype.asm').write_text(text)
    def assemble():return compiler.assemble('spi-prototype',0x3000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    cells,symbols=assemble();cells,symbols=relax_branches(stage/'spi-prototype.asm',cells,symbols,assemble)
    end=symbols['CORE_END'];body=compiler.dense_image(cells,0x3000,end)
    assert end<0x3DF0
    (OUT/'spi-prototype.bin').write_bytes(body)
    initialized={a:cells.get(a,0) for a in range(0x3000,0x3DF1)}
    (OUT/'spi-prototype.s19').write_bytes(s19(initialized,0x3000))
    meta=dict(entry=0x3000,end=end,bytes=len(body),core_bytes=end-symbols['CORE_BEGIN'],bridge_bytes=symbols['CORE_BEGIN']-0x3000,
              sha256=hashlib.sha256(body).hexdigest(),symbols=symbols,hardware_tested=False,flash_written=False,
              provider_sha256=pm['provider_sha256'],private_validator_reused=True)
    meta['s19_sha256']=hashlib.sha256((OUT/'spi-prototype.s19').read_bytes()).hexdigest();meta['initialized_image_bytes']=len(initialized)
    helpers=(end-symbols['INIT'])+(symbols['MEMORY_FRAME']-symbols['READ_MODE'])+(symbols['INIT']-symbols['NEXT_RX'])
    meta['size_groups']=dict(gpio_byte=end-symbols['INIT'],mode_helpers=symbols['MEMORY_FRAME']-symbols['READ_MODE'],pointer_helpers=symbols['INIT']-symbols['NEXT_RX'],
        probe=symbols['PROBE_ADDRESS']-symbols['PROBE'],shared_helpers=helpers,main=end-symbols['CORE_BEGIN']-helpers)
    assert meta['size_groups']['main']<=640 and helpers<=237,meta['size_groups']
    client_text=long_branches((SOURCE/'spi-client.asm').read_text()).replace('BM_LONG_','CLIENT_LONG_')
    (stage/'spi-client.asm').write_text(client_text)
    def client_assemble():return compiler.assemble('spi-client',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    cc,cs=client_assemble();cc,cs=relax_branches(stage/'spi-client.asm',cc,cs,client_assemble)
    client=compiler.dense_image(cc,0x2000,cs['APP_END']);assert cs['APP_END']<0x3000
    (OUT/'spi-client.bin').write_bytes(client);(OUT/'spi-client.s19').write_bytes(s19(cc,0x2000))
    meta['client']=dict(bytes=len(client),end=cs['APP_END'],sha256=hashlib.sha256(client).hexdigest(),symbols=cs)
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('SPI RAM prototype:',len(body),'bytes; core',meta['core_bytes'],'bridge',meta['bridge_bytes'],'at 3000-'+f'{end-1:04X}')

if __name__=='__main__':main()
