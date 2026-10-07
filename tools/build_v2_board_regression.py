"""Build RAM-only hardware regression probes against the current public ABI."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-board-regression'

def main():
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'src/v2-beta4/str8n-v2-public.inc',stage/'str8n-v2-public.inc')
    probes={}
    snapshot='''        MODULE IO_SNAPSHOT
        XDEF START
        XDEF PROBE_END
        CODE
START:  LDA $7FCE
        STA $2400
        LDA $7FCB
        STA $2401
        LDA $7FC6
        STA $2402
        LDA $7FC7
        STA $2403
        LDA $7FC3
        STA $2404
        LDA $7FCF
        STA $2405
        JMP $7E67
PROBE_END:
        ENDMOD
        END
'''
    (stage/'snapshot.asm').write_text(snapshot)
    compiler.OUT,compiler.SOURCE=OUT,stage
    cells,symbols=compiler.assemble('snapshot',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    (OUT/'snapshot.s19').write_bytes(s19(cells,0x2000))
    shutil.copyfile(ROOT/'tools/v2-rtc/i2c-api.inc',stage/'i2c-api.inc')
    text=(ROOT/'tools/v2-rtc/kernel-client.asm').read_text()
    marker='        JSR I2C_TRANSFER\n        PHA\n'
    assert text.count(marker)==1
    text=text.replace(marker,'''        JSR I2C_TRANSFER
        PHA
        LDX #3
SAVE_BUS_RESULT:
        LDA $6658,X
        STA $2458,X
        DEX
        BPL SAVE_BUS_RESULT
''')
    (stage/'service.asm').write_text(long_branches(text))
    cells,symbols=compiler.assemble('service',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    body=compiler.dense_image(cells,0x2000,symbols['CLIENT_END'])
    (OUT/'service.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'service-build.json').write_text(json.dumps(dict(bytes=len(body),symbols=symbols,sha256=hashlib.sha256(body).hexdigest()),indent=2)+'\n')
    for key,source in (('abi','tools/v2-ram-abi-test/str8n-v2-ram-abi-test-2000.asm'),('irq','tools/v2-interrupt-test/str8n-v2-interrupt-probe-2000.asm'),('nmi','tools/v2-interrupt-test/str8n-v2-nmi-probe-2000.asm'),('native','tools/v2-interrupt-test/str8n-v2-native-probe-2000.asm')):
        text=(ROOT/source).read_text()
        if key in ('nmi','native'):
            # About one minute at the board's 8 MHz clock; normal cleanup on expiry.
            text=text.replace('                        STZ     TIME2','                        STZ     TIME2\n                        LDA     #$02\n                        STA     TIME3',1)
            text=text.replace('                        INC     TIME2\n                        BNE     WAIT_NMI', '                        INC     TIME2\n                        BNE     WAIT_NMI\n                        DEC     TIME3\n                        BNE     WAIT_NMI',1)
            text=text.replace('TIME2:                  DB      $00','TIME2:                  DB      $00\nTIME3:                  DB      $00',1)
        if 'MODULE' not in text:text='        MODULE BOARD_PROBE\n        XDEF START\n        XDEF PROBE_END\n        CODE\n'+text.replace('                        END','        ENDMOD\n        END')
        (stage/(key+'.asm')).write_text(long_branches(text))
        compiler.OUT,compiler.SOURCE=OUT,stage
        cells,symbols=compiler.assemble(key,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
        end=symbols.get('PROBE_END',symbols.get('NATIVE_END'));assert end and end<0x3000
        body=compiler.dense_image(cells,0x2000,end);(OUT/(key+'.s19')).write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
        probes[key]=dict(bytes=len(body),end=end,sha256=hashlib.sha256(body).hexdigest(),symbols=symbols)
    (OUT/'build.json').write_text(json.dumps(dict(probes=probes,flash_written=False),indent=2)+'\n')
    print('RAM-only regression probes',[(key,p['bytes']) for key,p in probes.items()])
if __name__=='__main__':main()
