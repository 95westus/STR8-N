"""Build beta6 UTC/status banner without changing the qualified beta5 outputs."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_rtc_kernel as base
import build_v2_config as compiler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'BUILD/v2-rtc-banner'
VERSION = '2.0b6'
GENERATION = 15
BANNER_SOURCE = 'rtc-banner.asm'
SOURCE_HOOK = None
POST_HOOK = None
EXTRA_SOURCE_FILES = []


def profile(source):
    eq = source/'service-eq.inc'
    eq.write_text(eq.read_text()+'\nSVC_BANNER_PTR EQU $7D0F\n')
    path = source/'service-kernel.inc'
    text = path.read_text()
    first = text.index('        LDA $8000\n')
    last = text.index('        JSR AP_CRC_INIT\n',first)
    text = text[:first]+'''        LDX #3
SVC_HEADER_LOOP
        LDA $8000,X
        CMP SVC_HEADER_MAGIC,X
        BNE SVC_DONE
        DEX
        BPL SVC_HEADER_LOOP
'''+text[last:]
    text = text.replace('\nSVC_DONE\n', '''
        LDX #3
SVC_BANNER_CHECK
        LDA $8900,X
        CMP SVC_BANNER_MAGIC,X
        BNE SVC_DONE
        DEX
        BPL SVC_BANNER_CHECK
        JSR $8904
SVC_DONE
''',1)
    text += '\nSVC_HEADER_MAGIC DB "RC",1,5\nSVC_BANNER_MAGIC DB "BT",1,2\n'
    path.write_text(text)
    path = source/'str8n-v2.asm'
    text = path.read_text().replace('                        STZ SVC_DESC\n',
        '                        STZ SVC_DESC\n                        STZ SVC_BANNER_PTR+1\n',1)
    marker = 'V2_PROMPT:              LDA     $7DF9'
    assert text.count(marker)==1
    text = text.replace(marker,'''                        LDA SVC_BANNER_PTR+1
                        BEQ V2_CLOCK_BANNER_DONE
                        JSR V2_CLOCK_BANNER
V2_CLOCK_BANNER_DONE:
'''+marker)
    text = text.replace('V2_END:', 'V2_CLOCK_BANNER: JMP (SVC_BANNER_PTR)\nV2_END:')
    path.write_text(text)


def component(sector):
    source = OUT/'banner-source'
    source.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'tools/v2-rtc'/BANNER_SOURCE,source/'rtc-banner.asm')
    for name in ('kernel-rtc-api.inc','outage-format.inc'):
        shutil.copyfile(ROOT/'tools/v2-rtc'/name,source/name)
    for name in EXTRA_SOURCE_FILES:
        shutil.copyfile(ROOT/'tools/v2-rtc'/name,source/name)
    from build_bank_maint_v2 import long_branches
    path=source/'rtc-banner.asm'
    path.write_text(long_branches(path.read_text()).replace('BM_LONG_','BN_LONG_'))
    path=source/'outage-format.inc'
    path.write_text(long_branches(path.read_text()).replace('BM_LONG_','OF_LONG_'))
    previous_out,previous_source = compiler.OUT,compiler.SOURCE
    try:
        compiler.OUT,compiler.SOURCE = OUT/'banner',source
        (compiler.OUT/'asm').mkdir(parents=True,exist_ok=True)
        cells,symbols = compiler.assemble('rtc-banner',0x8900,shutil.which('wdc02as'),shutil.which('wdcln'),source=source)
        body = compiler.dense_image(cells,0x8900,symbols['BANNER_END'])
    finally:
        compiler.OUT,compiler.SOURCE = previous_out,previous_source
    assert symbols['START']==0x8900 and symbols['BANNER_END']<0x8FFE
    assert sector[0x900:0x900+len(body)]==bytes([255])*len(body)
    sector[0x900:0x900+len(body)] = body
    (OUT/'banner/build.json').write_text(json.dumps(dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),symbols=symbols),indent=2)+'\n')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'BUILD/v2-rtc-kernel/str8n-maint-1.6-b1-8000-9fff.bin',OUT/'str8n-maint-1.6-b1-8000-9fff.bin')
    base.OUT,base.VERSION,base.GENERATION = OUT,VERSION,GENERATION
    base.split.OUT = OUT/'split'
    base.PROFILE_HOOK,base.COMPONENT_HOOK = profile,component
    if SOURCE_HOOK:
        def combined(source):
            profile(source)
            SOURCE_HOOK(source)
        base.PROFILE_HOOK=combined
    base.main()
    if POST_HOOK:
        POST_HOOK()
    meta = json.loads((OUT/'build.json').read_text())
    meta.update(banner_address=0x8900,banner_entry=0x8907,
        banner_bytes=json.loads((OUT/'banner/build.json').read_text())['bytes'],
        banner_pointer=0x7D0F,banner_reads_rtc=True)
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    shutil.copyfile(ROOT/'BUILD/v2-rtc-kernel/str8n-maint-1.6-b1-8000-9fff.bin',OUT/'str8n-maint-1.6-b1-8000-9fff.bin')
    assert meta['monitor_bytes']['a0']<=3968 and meta['monitor_bytes']['b0']<=3968
    print('Banner installed at 8900; E',meta['launcher_bytes'],'bytes; slots',meta['monitor_bytes'])


if __name__=='__main__':
    main()
