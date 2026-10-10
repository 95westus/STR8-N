"""Build an isolated beta21 fixed-offset candidate; no ports or flashing."""
import hashlib,json
import build_v2_status as status
from build_v2_trim_display import main as firmware
from build_v2_clock_offset import main as clock

def main(build='BUILD/v2-local-time',version='2.0b21',generation=30):
    root=status.ROOT;status.WEEKDAY_DISPLAY=True;status.LOCAL_TIME=True
    firmware(out=build,version=version,generation=generation)
    out=status.OUT
    source=out/'local-display/source';source.mkdir(parents=True,exist_ok=True)
    for name in ('str8n-v2-eq.inc',):
        (source/name).write_bytes((out/'source'/name).read_bytes())
    header='''        MODULE LOCAL_DISPLAY
        XDEF START
        XDEF APP_END
        CODE
START:  DB "LT",1,1
        JMP LOCAL_ENTRY
LOCAL_ENTRY:
        STA KIND
        JSR TRIM_DISPLAY
        JSR TZ_SHOW_LOCAL
        RTS
PRINT:  JMP TZ_PRINT
KIND DB 0
'''
    local=(root/'tools/v2-rtc/local-time.inc').read_text()
    if status.COMPACT_BOOT_LOCAL:
        header=header.replace('        JSR TRIM_DISPLAY\n','        LDA KIND\n        BEQ LOCAL_BOOT_DISPLAY\n        JSR TRIM_DISPLAY\nLOCAL_BOOT_DISPLAY:\n',1)
        marker='        LDX #<TZ_LOCAL_TEXT\n        LDY #>TZ_LOCAL_TEXT\n        JSR TZ_PRINT\n'
        assert local.count(marker)==1
        local=local.replace(marker,'''        LDA KIND
        BNE TZ_DETAIL_PREFIX
        LDX #<TZ_BOOT_TEXT
        LDY #>TZ_BOOT_TEXT
        BRA TZ_PREFIX_READY
TZ_DETAIL_PREFIX:
        LDX #<TZ_LOCAL_TEXT
        LDY #>TZ_LOCAL_TEXT
TZ_PREFIX_READY:
        JSR TZ_PRINT
''',1)
        local+='\nTZ_BOOT_TEXT DB "RTCC: ",0\n'
    text=header+local+'\n'+(root/'tools/v2-spi/trim-display.inc').read_text()+'\nAPP_END:\n        ENDMOD\n'
    from build_bank_maint_v2 import long_branches
    (source/'local-display.asm').write_text(long_branches(text).replace('BM_LONG_','LT_LONG_'))
    body,s,_=status.spi.assemble(source,'local-display',0x6800,'APP_END',0x6807)
    assert len(body)<=1534,('local helper',len(body))
    asset=body+b'\xff'*(1534-len(body));asset+=status.crc(asset).to_bytes(2,'big');assert status.crc(asset)==0
    (out/'local-display/asset.bin').write_bytes(asset)
    meta=json.loads((out/'build.json').read_text());meta.update(local_symbols=s,local_code_bytes=len(body),local_asset_sha256=hashlib.sha256(asset).hexdigest())
    (out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    clock(build)
    meta=json.loads((out/'build.json').read_text());meta['clock_version']='1.6'
    meta['clock_sha256']=json.loads((out/'clock/build.json').read_text())['sha256']
    (out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('UNFLASHED local-time candidate:',len(body),'helper bytes; OFFSET saved separately, RTC UTC retained')

if __name__=='__main__':main()
