"""Build CLOCK 1.6 with confirmed fixed-offset records; no board access."""
import json,shutil
import build_v2_clock as base

def main(build='BUILD/v2-local-time'):
    root=base.ROOT;out=root/build/'clock';source=out/'input';source.mkdir(parents=True,exist_ok=True)
    meta=json.loads((root/build/'build.json').read_text())
    for name in ('kernel-rtc-api.inc','journal-eq.inc','outage-format.inc'):shutil.copyfile(root/'tools/v2-rtc'/name,source/name)
    text=(root/'tools/v2-rtc/clock-trim.asm').read_text().replace('CLOCK 1.5','CLOCK 1.6')
    text=text.replace('        JSR EUI_SHOW\n        JMP HELP','        JSR EUI_SHOW\n        JSR OFFSET_SHOW\n        JMP HELP',1)
    text=text.replace('        LDX #<CMD_TRIM\n','        JSR OFFSET_TRY\n        LDX #<CMD_TRIM\n',1)
    text=text.replace('        JSR FORMAT_TIME\n        JSR NL\n','        JSR FORMAT_TIME\n        JSR TZ_SHOW_LOCAL\n        JSR NL\n',1)
    marker='SET_REPORT:\n        LDX #<SET_DONE_TEXT\n        LDY #>SET_DONE_TEXT\n        JSR PRINT\n        JSR READ_CLOCK\n'
    assert text.count(marker)==1
    text=text.replace(marker,marker+'        JSR OFFSET_SETUP\n',1)
    text=text.replace('TRIM [-127..+127]','OFFSET +/-HH:MM (display only; YES required)",13,10,"TRIM [-127..+127]')
    worker=meta['worker']['V2W_BYTE']
    extra=f'OFFSET_FLASH_BYTE EQU ${worker:04X}\n'+(root/'tools/v2-rtc/local-time.inc').read_text()+'\n'+(root/'tools/v2-rtc/clock-offset.inc').read_text()
    text=text.replace('APP_END:\n',extra+'\nAPP_END:\n')
    (source/'clock-offset.asm').write_text(text)
    base.OUT=out;base.SOURCE=source;base.SOURCE_NAME='clock-offset.asm';base.VERSION='1.6';base.MAX_END=0x4400;base.main()

if __name__=='__main__':main()
